"""PRD v2 — goal + current → journey_meta + route_sketch（LLM 动态规划）。"""

from __future__ import annotations

import logging
from typing import Any

from llm_inference import plan_journey_via_llm

logger = logging.getLogger(__name__)


def _meta_item(
    key: str,
    label: str,
    why: str,
    priority: str,
    *,
    value: str | None = None,
    status: str = "open",
    source: str = "planner",
) -> dict[str, Any]:
    return {
        "id": f"meta_{key}",
        "key": key,
        "label": label,
        "why": why,
        "priority": priority,
        "status": status,
        "value": value,
        "confidence": 0.85 if value else 0.0,
        "source": source,
        "asked_count": 0,
    }


def _generic_fallback_plan(universal: dict[str, Any]) -> dict[str, Any]:
    """无 LLM 时的最小兜底：不猜测用户意图类型，只列开放性问题。"""
    anchors = universal.get("anchors") or {}
    goal = (anchors.get("goal") or "你的学习目标").strip()
    return {
        "journey_meta": [
            _meta_item(
                "goal_specifics",
                "目标细节",
                f"进一步厘清「{goal[:40]}」具体指什么、怎样算达成",
                "blocking",
            ),
            _meta_item(
                "current_situation",
                "现状与限制",
                "英语水平、可用时间、所处环境等",
                "blocking",
            ),
            _meta_item(
                "main_obstacle",
                "主要困难",
                "目前最大的阻碍是什么",
                "important",
            ),
        ],
        "route_sketch": {
            "title": "个性化英语学习路径",
            "summary": "将根据你的具体目标与现状定制",
            "milestones": ["了解需求", "制定计划", "阶段目标"],
        },
        "distance_summary": "需通过对话进一步了解你的目标与现状",
        "source": "fallback",
    }


def _parse_llm_plan(data: dict[str, Any]) -> dict[str, Any]:
    metas = []
    for i, m in enumerate(data.get("journey_meta") or []):
        status = m.get("status") or ("inferred" if m.get("value") else "open")
        metas.append(
            _meta_item(
                m.get("key", f"field_{i}"),
                m.get("label", m.get("key", "")),
                m.get("why", ""),
                m.get("priority", "important"),
                value=m.get("value"),
                status=status,
                source="llm" if status == "inferred" else "planner",
            )
        )
    return {
        "journey_meta": metas,
        "route_sketch": data.get("route_sketch") or {},
        "distance_summary": data.get("distance_summary", ""),
        "source": "llm",
    }


def needs_replan(universal: dict, collection: dict) -> bool:
    if not collection.get("journey_meta"):
        return True
    stored_goal = collection.get("_planned_goal") or ""
    stored_current = collection.get("_planned_current") or ""
    anchors = universal.get("anchors") or {}
    goal = (anchors.get("goal") or "").strip()
    current = (anchors.get("current") or "").strip()
    if goal and goal != stored_goal:
        return True
    if current and stored_current and current != stored_current and len(current) > len(stored_current) + 15:
        return True
    return False


def plan_journey_meta(universal: dict[str, Any], collection: dict) -> dict[str, Any]:
    raw_llm = plan_journey_via_llm(universal)
    result = _parse_llm_plan(raw_llm) if raw_llm else _generic_fallback_plan(universal)

    anchors = universal.get("anchors") or {}
    collection["_planned_goal"] = anchors.get("goal") or ""
    collection["_planned_current"] = anchors.get("current") or ""
    collection["meta_plan_version"] = int(collection.get("meta_plan_version") or 0) + 1
    collection["journey_meta"] = result.get("journey_meta") or []
    collection["route_sketch"] = result.get("route_sketch")
    collection["distance_summary"] = result.get("distance_summary", "")
    collection["phase"] = "collecting"
    result["journey_meta"] = collection["journey_meta"]
    result["collection_patch"] = collection
    return result
