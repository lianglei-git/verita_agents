"""Digital Twin Engine — PRD v2 Journey-First 采集"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_AGENTS_ROOT = Path(__file__).resolve().parents[1]
if str(_AGENTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_AGENTS_ROOT))

_AGENT_DIR = Path(__file__).resolve().parent
if str(_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENT_DIR))

from anchor_extractor import absorb_text  # noqa: E402
from anchor_sync import sync_anchors_from_metas  # noqa: E402
from flow import plan_collection_v2  # noqa: E402
from meta_answer import apply_target_answer  # noqa: E402
from identity_baseline import baseline_ready, missing_baseline_fields  # noqa: E402
from meta_collection import merge_collection_v2, meta_progress, record_turn  # noqa: E402
from release_v2 import (  # noqa: E402
    is_released,
    phase_from_release_v2,
    unresolved_meta_keys,
)
from twin_bridge import collection_from_legacy, twin_from_universal, universal_from_legacy  # noqa: E402
from universal_model import merge_universal, update_clarity  # noqa: E402

try:
    from _lib.llm import is_llm_available  # noqa: E402
except ImportError:

    def is_llm_available() -> bool:
        return False


def _parse_payload(user_input: str, kwargs: dict) -> dict:
    if kwargs:
        return kwargs
    if not user_input.strip():
        return {}
    try:
        data = json.loads(user_input)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    return {"story": user_input}


def _resolve_target(answers: dict) -> tuple[str, str]:
    """从 answers 解析 target 与文本。"""
    if not answers:
        return "", ""
    target = str(answers.get("target") or answers.get("field") or "").strip()
    if target and target in answers and not str(target).startswith("_"):
        text = answers[target]
        if isinstance(text, str) and text.strip():
            return target, text.strip()
    if target:
        for k, v in answers.items():
            if k.startswith("_") or k in ("target", "field"):
                continue
            if isinstance(v, str) and v.strip():
                return target, v.strip()
    for k, v in answers.items():
        if k.startswith("_") or k in ("target", "field"):
            continue
        if k == "batch_baseline":
            return "anchor:current", str(v).strip()
        if isinstance(v, str) and v.strip():
            t = answers.get("target") or answers.get("field") or k
            return str(t), v.strip()
    return "", ""


def _summary(universal: dict, collection: dict) -> str:
    anchors = universal.get("anchors") or {}
    ident = universal.get("identity") or {}
    goal = anchors.get("goal") or "待明确"
    current = anchors.get("current") or "待补充"
    occ = ident.get("occupation") or "用户"
    route = collection.get("route_sketch") or {}
    release = collection.get("release") or {}
    prog = meta_progress(collection)

    if is_released(release):
        return (
            f"{occ}，目标：{goal}。"
            f"路线：{route.get('title') or '已生成'}。"
            f"关键信息 {prog['blocking_closed']}/{prog['blocking_total']}，可进入规划。"
        )
    phase = collection.get("phase", "anchoring")
    if phase == "anchoring":
        return f"正在对齐目标与现状：{goal} / 现在：{current[:40]}…"
    return (
        f"{occ}，目标：{goal}。"
        f"路线：{route.get('title') or '生成中'}。"
        f"关键信息 {prog['blocking_closed']}/{prog['blocking_total']}。"
    )


def _build_handoff_v2(universal: dict, collection: dict) -> dict[str, Any]:
    release = collection.get("release") or {}
    return {
        "release_type": release.get("status", "collecting"),
        "universal": universal,
        "journey_meta": collection.get("journey_meta") or [],
        "route_sketch": collection.get("route_sketch"),
        "confidence": release.get("confidence", 0.0),
        "assumptions": collection.get("assumptions") or [],
        "unresolved_meta": unresolved_meta_keys(collection),
    }


def run(user_input: str, **kwargs) -> dict:
    payload = _parse_payload(user_input, kwargs)

    story = (payload.get("story") or "").strip()
    answers = payload.get("answers") or {}
    action = (payload.get("action") or "answer").strip().lower()

    universal = universal_from_legacy(payload)
    collection = collection_from_legacy(payload)

    inferred_fields: list[str] = []
    enrich_method = "none"

    if story:
        universal, inf = absorb_text(universal, story)
        inferred_fields.extend(inf)
        enrich_method = "story"

    if action == "skip":
        target = answers.get("_skip_field") or answers.get("target") or answers.get("field") or ""
        if target.startswith("meta:"):
            key = target.split(":", 1)[1]
            for m in collection.get("journey_meta") or []:
                if m.get("key") == key:
                    m["status"] = "waived"
                    m["value"] = "用户跳过"
        collection = record_turn(collection, target=target or "skip", question="(跳过)")

    elif answers:
        target, text = _resolve_target(answers)
        if not target and text:
            universal, inf = absorb_text(universal, text)
            inferred_fields.extend(inf)
        elif target and text:
            universal, collection, inf = apply_target_answer(universal, collection, target, text)
            inferred_fields.extend(inf)
            enrich_method = "target"
            collection = record_turn(
                collection,
                target=target,
                question=text[:80],
            )

    universal = update_clarity(universal)
    if collection.get("journey_meta"):
        universal = sync_anchors_from_metas(universal, collection)

    plan = plan_collection_v2(universal, collection)
    collection = merge_collection_v2(collection)
    if plan.get("release"):
        collection["release"] = plan["release"]

    next_question = plan.get("next_question")
    release = collection.get("release") or {}
    released = is_released(release) and not next_question

    if released:
        collection["phase"] = "sufficient" if release.get("status") == "sufficient" else "conditional"

    twin = twin_from_universal(universal, collection)
    phase = phase_from_release_v2(release.get("status", "collecting"))
    if next_question:
        phase = "p0_collecting"
    handoff = _build_handoff_v2(universal, collection) if released else None
    prog = meta_progress(collection)

    return {
        "output": _summary(universal, collection),
        "universal": universal,
        "twin": twin,
        "collection": collection,
        "handoff": handoff,
        "completeness": {
            "anchors": 1.0 if universal.get("anchors", {}).get("goal_clarity") in ("medium", "high") else 0.5,
            "baseline": (4 - len(missing_baseline_fields(universal))) / 4,
            "meta_blocking": (
                prog["blocking_closed"] / prog["blocking_total"] if prog["blocking_total"] else 1.0
            ),
            "overall": release.get("confidence", 0.0),
        },
        "missing_fields": unresolved_meta_keys(collection) if not released else [],
        "next_questions": [next_question] if next_question and not released else [],
        "phase": phase,
        "profile": {
            "persona_title": (
                f"{universal.get('identity', {}).get('occupation') or '用户'}"
                f" · {universal.get('anchors', {}).get('goal') or '目标待明确'}"
            ),
            "summary": _summary(universal, collection),
            "phase": phase,
            "path_title": (collection.get("route_sketch") or {}).get("title"),
        },
        "meta": {
            "agent": "user-profile",
            "version": "2.1.0",
            "engine": "Digital Twin Engine",
            "stage": "p0",
            "enrich_method": enrich_method,
            "inferred_fields": inferred_fields,
            "confident_fields": collection.get("confident_fields") or {},
            "llm_available": is_llm_available(),
            "planner_source": plan.get("source"),
            "release_status": release.get("status"),
            "inference_mode": "llm" if is_llm_available() else "fallback_raw_text",
        },
    }


if __name__ == "__main__":
    sample = {"story": "我在上海做前端，想赚美元，口语比较弱"}
    raw = sys.argv[1] if len(sys.argv) > 1 else json.dumps(sample, ensure_ascii=False)
    print(json.dumps(run(raw), ensure_ascii=False, indent=2))
