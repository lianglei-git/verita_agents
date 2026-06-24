"""PRD v2 — 放行判定（无题数硬顶）。"""

from __future__ import annotations

from typing import Any

from identity_baseline import baseline_ready, missing_baseline_fields
from meta_collection import META_STATUSES_CLOSED, blocking_closed, meta_progress, open_metas
from universal_model import anchors_ready, clarity_rank, current_is_resolved, goal_is_resolved


def evaluate_release_v2(universal: dict[str, Any], collection: dict[str, Any]) -> dict[str, Any]:
    anchors = universal.get("anchors") or {}
    turn = int(collection.get("turn_count") or 0)
    progress = meta_progress(collection)
    blocking_total = progress["blocking_total"]
    blocking_closed_n = progress["blocking_closed"]

    if not anchors_ready(universal):
        if not goal_is_resolved(universal):
            return {
                "status": "collecting",
                "reason": "学习目标尚未明确，需先确认你想用英语做什么",
                "confidence": 0.25,
            }
        if not current_is_resolved(universal):
            return {
                "status": "collecting",
                "reason": "现状信息尚不充分，需了解你的水平与可用时间等",
                "confidence": 0.28,
            }
        return {
            "status": "collecting",
            "reason": "目标或现状尚需进一步明确",
            "confidence": 0.3,
        }

    if not baseline_ready(universal):
        missing = missing_baseline_fields(universal)
        return {
            "status": "collecting",
            "reason": f"基础身份尚缺：{', '.join(missing)}",
            "confidence": 0.35,
        }

    journey_meta = collection.get("journey_meta") or []
    if not journey_meta:
        return {
            "status": "collecting",
            "reason": "正在规划本次 journey 必要信息",
            "confidence": 0.4,
        }

    if not blocking_closed(collection):
        conf = 0.4 + 0.4 * (blocking_closed_n / max(1, blocking_total))
        return {
            "status": "collecting",
            "reason": f"关键信息 {blocking_closed_n}/{blocking_total} 已闭合",
            "confidence": round(conf, 2),
        }

    important_open = len(open_metas(collection, "important"))
    goal_c = clarity_rank(anchors.get("goal_clarity") or "low")
    cur_c = clarity_rank(anchors.get("current_clarity") or "low")
    confidence = 0.55 + 0.1 * goal_c + 0.1 * cur_c
    if important_open == 0:
        confidence += 0.15
    elif important_open <= 1:
        confidence += 0.05
    confidence = min(0.95, confidence)

    if confidence >= 0.7 and important_open == 0:
        if not goal_is_resolved(universal):
            return {
                "status": "collecting",
                "reason": "学习目标尚未明确，需先确认核心目标",
                "confidence": round(confidence * 0.5, 2),
            }
        if not current_is_resolved(universal):
            return {
                "status": "collecting",
                "reason": "现状信息尚不充分",
                "confidence": round(confidence * 0.6, 2),
            }
        return {
            "status": "sufficient",
            "reason": "关键信息与重要信息均已闭合，可进入规划",
            "confidence": round(confidence, 2),
        }

    if important_open > 1:
        return {
            "status": "collecting",
            "reason": f"关键信息已齐，仍有 {important_open} 项重要信息待补充",
            "confidence": round(confidence, 2),
        }

    if turn > 20 or (turn > 15 and blocking_closed(collection)):
        return {
            "status": "conditional",
            "reason": "对话轮次较多，部分细节将基于假设补全",
            "confidence": round(confidence, 2),
        }

    if blocking_closed(collection) and important_open == 1:
        return {
            "status": "collecting",
            "reason": "关键信息已齐，建议再补充 1 项重要信息",
            "confidence": round(confidence, 2),
        }

    return {
        "status": "conditional",
        "reason": "核心信息足够，可条件放行",
        "confidence": round(confidence, 2),
    }


def is_released(release: dict[str, Any]) -> bool:
    return release.get("status") in ("sufficient", "conditional")


def phase_from_release_v2(status: str) -> str:
    return {
        "sufficient": "p0_sufficient",
        "conditional": "p0_conditional",
        "collecting": "p0_collecting",
    }.get(status, "p0_collecting")


def unresolved_meta_keys(collection: dict) -> list[str]:
    return [
        m.get("key")
        for m in collection.get("journey_meta") or []
        if m.get("status") == "open"
    ]
