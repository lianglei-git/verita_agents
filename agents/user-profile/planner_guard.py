"""规划器硬过滤 — 已答/已满足/高置信字段不再出题。"""

from __future__ import annotations

from typing import Any

from collection import baseline_missing, baseline_question_for, is_baseline_complete
from field_clusters import (
    assume_english_level_if_exhausted,
    cluster_ask_exhausted,
    is_field_satisfied,
    prune_path_against_twin,
)
from inference_confidence import should_skip_asking


def was_effectively_answered(collection: dict, field: str) -> bool:
    """该字段曾有效回答（含语义簇等效）。"""
    ledger = collection.get("answered_effective") or {}
    if field in ledger:
        return True
    from field_clusters import cluster_for_field, cluster_members

    cluster = cluster_for_field(field)
    if cluster:
        for member in cluster_members(cluster):
            if member in ledger:
                return True
    return False


def should_ask_field(twin: dict, collection: dict, field: str) -> bool:
    if field == "collection.path_confirmed":
        return not collection.get("path_confirmed") and "collection.path_confirmed" not in (
            collection.get("asked_fields") or []
        )
    if cluster_ask_exhausted(collection, field):
        assume_english_level_if_exhausted(twin, collection)
        return False
    if is_field_satisfied(twin, field):
        return False
    if should_skip_asking(collection, field, twin, field_satisfied_fn=is_field_satisfied):
        return False
    if was_effectively_answered(collection, field) and is_field_satisfied(twin, field):
        return False
    # 同簇已问过且仍未闭合 → 允许再问；否则同字段已有效回答则跳过
    if was_effectively_answered(collection, field):
        return not is_field_satisfied(twin, field)
    return True


def filter_question(twin: dict, collection: dict, question: dict | None) -> dict | None:
    if not question or not question.get("field"):
        return None
    if should_ask_field(twin, collection, question["field"]):
        return question
    return None


def _question_from_spec(field: str, spec: dict[str, Any], reason: str = "") -> dict[str, Any]:
    return {
        "field": field,
        "question": spec.get("question", f"请补充：{field}"),
        "hint": spec.get("hint", ""),
        "why": spec.get("why", reason or "完善路径所需信息"),
        "depth": spec.get("depth", 4),
        "phase": spec.get("phase", "path_blocking"),
        "skippable": spec.get("skippable", True),
        "choices": spec.get("choices") or [],
    }


def find_next_valid_question(twin: dict, collection: dict, path: dict) -> dict | None:
    """当规划器出题被过滤后，从真实缺口中选取下一题。"""
    from fallback_planner import FALLBACK_QUESTIONS, _path_confirm_question

    path_confirmed = bool(collection.get("path_confirmed"))

    if not is_baseline_complete(twin):
        for field in baseline_missing(twin):
            if should_ask_field(twin, collection, field):
                return baseline_question_for(field)

    if is_baseline_complete(twin) and not path_confirmed:
        if should_ask_field(twin, collection, "collection.path_confirmed"):
            return _path_confirm_question(path)

    for gap in path.get("blocking_gaps") or []:
        field = gap["field"] if isinstance(gap, dict) else gap
        reason = gap.get("reason", "") if isinstance(gap, dict) else ""
        if should_ask_field(twin, collection, field):
            spec = FALLBACK_QUESTIONS.get(field, {})
            return _question_from_spec(field, spec, reason)

    for field in path.get("required_fields") or []:
        if should_ask_field(twin, collection, field):
            spec = FALLBACK_QUESTIONS.get(field, {})
            return _question_from_spec(field, spec)

    for gap in path.get("optional_gaps") or []:
        field = gap["field"] if isinstance(gap, dict) else gap
        reason = gap.get("reason", "") if isinstance(gap, dict) else ""
        if should_ask_field(twin, collection, field):
            spec = FALLBACK_QUESTIONS.get(field, {})
            return _question_from_spec(field, spec)

    return None


def finalize_plan(twin: dict, collection: dict, plan: dict[str, Any]) -> dict[str, Any]:
    """修剪 path、过滤/重选 next_question。"""
    path = prune_path_against_twin(plan.get("path") or collection.get("path") or {}, twin)
    plan = {**plan, "path": path}

    question = filter_question(twin, collection, plan.get("next_question"))
    if not question:
        question = find_next_valid_question(twin, collection, path)
    plan["next_question"] = question

    plan["blocking_fields"] = [
        g["field"] if isinstance(g, dict) else g
        for g in (path.get("blocking_gaps") or [])
        if not is_field_satisfied(twin, g["field"] if isinstance(g, dict) else g)
    ]
    return plan
