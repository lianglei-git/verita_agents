"""规划流水线输入解析 — 从多种上游 payload 提取契约对象。"""

from __future__ import annotations

import json
from typing import Any

from .contract import (
    normalize_gap_diagnosis,
    normalize_planning_profile,
    normalize_scenario_set,
    planning_profile_from_handoff,
)


def _parse_json_payload(user_input: str, kwargs: dict) -> dict:
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
    return {"text": user_input}


def resolve_planning_profile(payload: dict) -> dict[str, Any]:
    """从 payload 解析 PlanningProfile（支持 profile / handoff / 遗留字段）。"""
    if payload.get("profile"):
        return normalize_planning_profile(payload["profile"])
    if payload.get("planning_profile"):
        return normalize_planning_profile(payload["planning_profile"])
    if payload.get("handoff"):
        return planning_profile_from_handoff(payload["handoff"])

    profile = normalize_planning_profile(payload.get("profile"))
    if profile.get("anchors", {}).get("goal"):
        return profile

    twin = payload.get("twin") or {}
    growth = twin.get("growth") or {}
    ident = twin.get("identity") or {}
    goal = (
        payload.get("goal")
        or growth.get("goal")
        or payload.get("goal_text")
        or ""
    )
    current = payload.get("current") or payload.get("current_text") or ""
    if not current and ident:
        parts = [p for p in (ident.get("occupation"), ident.get("age_range")) if p]
        current = "；".join(str(p) for p in parts)

    if goal or current:
        patch = normalize_planning_profile({
            "anchors": {"goal": str(goal), "current": str(current)},
            "readiness": {"status": "conditional", "allow_proceed_with_assumptions": True},
            "provenance": {"source_agent": "legacy"},
        })
        return patch

    return normalize_planning_profile(None)


def resolve_gap_diagnosis(payload: dict) -> dict[str, Any] | None:
    raw = payload.get("gap_diagnosis") or payload.get("gaps")
    if not raw:
        return None
    if isinstance(raw, dict) and raw.get("gaps") is not None:
        return normalize_gap_diagnosis(raw)
    if isinstance(raw, list):
        return normalize_gap_diagnosis({"gaps": raw})
    return None


def resolve_scenario_set(payload: dict) -> dict[str, Any] | None:
    raw = payload.get("scenario_set") or payload.get("scenarios")
    if not raw:
        return None
    if isinstance(raw, dict) and raw.get("scenarios") is not None:
        return normalize_scenario_set(raw)
    if isinstance(raw, list):
        return normalize_scenario_set({"scenarios": raw})
    return None


def selected_scenario(scenario_set: dict[str, Any] | None) -> dict[str, Any] | None:
    if not scenario_set:
        return None
    selected_id = str(scenario_set.get("selected_scenario_id") or "").strip()
    scenarios = scenario_set.get("scenarios") or []
    if selected_id:
        for s in scenarios:
            if s.get("id") == selected_id:
                return s
    for archetype in ("balanced", "conservative", "aggressive"):
        for s in scenarios:
            if s.get("archetype") == archetype:
                return s
    return scenarios[0] if scenarios else None


__all__ = [
    "_parse_json_payload",
    "resolve_planning_profile",
    "resolve_gap_diagnosis",
    "resolve_scenario_set",
    "selected_scenario",
]
