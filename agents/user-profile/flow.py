"""PRD v2 — 采集流程：锚点 → meta 规划 → 问题流。"""

from __future__ import annotations

from typing import Any

from identity_baseline import FIELD_PATH_LABELS
from meta_collection import PRIORITY_ORDER, open_metas, record_meta_presented
from meta_planner import needs_replan, plan_journey_meta
from question_composer import compose_anchor_question, compose_meta_question
from release_v2 import evaluate_release_v2, is_released
from universal_model import (
    anchors_ready,
    current_is_resolved,
    goal_is_resolved,
    missing_universal_fields,
)

ANCHOR_GOAL = "anchor:goal"
ANCHOR_CURRENT = "anchor:current"


def _anchor_target(universal: dict) -> str | None:
    if not goal_is_resolved(universal):
        return ANCHOR_GOAL
    if not current_is_resolved(universal):
        return ANCHOR_CURRENT
    return None


def _universal_target(universal: dict) -> str | None:
    missing = missing_universal_fields(universal)
    if missing:
        return f"universal:{missing[0]}"
    return None


def _next_meta_target(collection: dict) -> str | None:
    for pri in PRIORITY_ORDER:
        opens = open_metas(collection, pri)
        if opens:
            return f"meta:{opens[0]['key']}"
    return None


def _question_for_target(
    target: str,
    universal: dict,
    collection: dict,
) -> dict[str, Any]:
    if target == ANCHOR_GOAL:
        q = compose_anchor_question(universal, "goal")
    elif target == ANCHOR_CURRENT:
        q = compose_anchor_question(universal, "current")
    elif target.startswith("universal:"):
        field = target.split(":", 1)[1]
        question, hint = FIELD_PATH_LABELS.get(field, (f"请补充：{field}", ""))
        q = {"question": question, "why": "基础信息有助于制定适合你的学习路径", "hint": hint}
    elif target.startswith("meta:"):
        key = target.split(":", 1)[1]
        meta = next((m for m in collection.get("journey_meta") or [] if m.get("key") == key), {})
        q = compose_meta_question(universal, collection, meta)
    else:
        q = {"question": "请继续介绍", "why": "", "hint": ""}

    return {
        "target": target,
        "field": target,
        "question": q.get("question", ""),
        "why": q.get("why", ""),
        "hint": q.get("hint", ""),
        "phase": collection.get("phase", "anchoring"),
        "skippable": target.startswith("meta:"),
        "depth": 1 if target.startswith("anchor:") else (2 if target.startswith("universal:") else 3),
        "choices": [],
    }


def plan_collection_v2(universal: dict, collection: dict) -> dict[str, Any]:
    release = evaluate_release_v2(universal, collection)
    collection["release"] = release

    if is_released(release) and not open_metas(collection) and goal_is_resolved(universal):
        collection["phase"] = "sufficient"
        return {
            "next_question": None,
            "release": release,
            "source": "release_v2",
        }

    if not goal_is_resolved(universal) or not current_is_resolved(universal):
        collection["phase"] = "anchoring"
        target = _anchor_target(universal) or ANCHOR_GOAL
        question = _question_for_target(target, universal, collection)
        return {"next_question": question, "release": release, "source": "anchoring"}

    baseline_target = _universal_target(universal)
    if baseline_target:
        collection["phase"] = "baseline"
        question = _question_for_target(baseline_target, universal, collection)
        return {"next_question": question, "release": release, "source": "baseline"}

    if needs_replan(universal, collection):
        plan_journey_meta(universal, collection)
        collection["phase"] = "collecting"

    target = _next_meta_target(collection)
    if not target:
        target = _universal_target(universal)

    if not target:
        release = evaluate_release_v2(universal, collection)
        collection["release"] = release
        collection["phase"] = "sufficient" if is_released(release) else "collecting"
        return {"next_question": None, "release": release, "source": "done"}

    collection["phase"] = "collecting"
    question = _question_for_target(target, universal, collection)
    if target.startswith("meta:"):
        key = target.split(":", 1)[1]
        record_meta_presented(collection, key)
    return {"next_question": question, "release": release, "source": "meta_flow"}
