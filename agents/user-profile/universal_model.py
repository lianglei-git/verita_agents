"""PRD v2 — Universal 固定 schema 与清晰度评估。"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Literal

from identity_baseline import missing_baseline_fields

Clarity = Literal["high", "medium", "low"]

GOAL_SIGNALS = re.compile(
    r"面试|留学|雅思|托福|赚|美元|海外|远程|工作|考试|移民|升职|沟通|offer|ielts|toefl",
    re.I,
)
CURRENT_SIGNALS = re.compile(
    r"岁|工程师|学生|前端|后端|口语|听力|阅读|写作|水平|在|来自|住在|公司|经验|分|弱|强|不会|可以",
    re.I,
)
VAGUE_ANCHOR_MARKERS = re.compile(
    r"未明确|未定|待明确|不清楚|可能为|通用提升|待细化|用户未|尚未明确|未知|不明确|待确认",
    re.I,
)


def empty_universal() -> dict[str, Any]:
    return {
        "anchors": {
            "goal": "",
            "current": "",
            "goal_clarity": "low",
            "current_clarity": "low",
        },
        "identity": {
            "age_range": "",
            "occupation": "",
            "region_anchor": "",
            "native_language": "",
            "role_anchor": "",
        },
        "capability_snapshot": {
            "self_assessed_level": "",
            "strongest": "",
            "weakest": "",
        },
    }


def _filled(val: Any) -> bool:
    if val is None:
        return False
    if isinstance(val, str):
        return bool(val.strip())
    return bool(val)


def _assess_goal_clarity(goal: str) -> Clarity:
    text = (goal or "").strip()
    if len(text) < 4:
        return "low"
    if VAGUE_ANCHOR_MARKERS.search(text) or text.startswith("用户"):
        return "low"
    if GOAL_SIGNALS.search(text):
        return "high" if len(text) >= 4 else "medium"
    if len(text) >= 12:
        return "medium"
    if len(text) >= 6:
        return "medium"
    return "low"


def _assess_current_clarity(current: str, universal: dict) -> Clarity:
    text = (current or "").strip()
    if VAGUE_ANCHOR_MARKERS.search(text) or text.startswith("用户"):
        return "low"
    ident = universal.get("identity") or {}
    score = 0
    if len(text) >= 20:
        score += 2
    elif len(text) >= 8:
        score += 1
    if CURRENT_SIGNALS.search(text):
        score += 1
    if _filled(ident.get("occupation")):
        score += 1
    if _filled(ident.get("region_anchor")):
        score += 1
    if score >= 3:
        return "high"
    if score >= 1:
        return "medium"
    return "low"


def update_clarity(universal: dict[str, Any]) -> dict[str, Any]:
    anchors = universal.setdefault("anchors", {})
    anchors["goal_clarity"] = _assess_goal_clarity(anchors.get("goal") or "")
    anchors["current_clarity"] = _assess_current_clarity(
        anchors.get("current") or "", universal
    )
    return universal


def merge_universal(existing: dict | None, patch: dict | None) -> dict[str, Any]:
    base = empty_universal()
    if existing:
        for section in ("anchors", "identity", "capability_snapshot"):
            if section in existing and isinstance(existing[section], dict):
                for k, v in existing[section].items():
                    if v is not None and (not isinstance(v, str) or v.strip()):
                        base[section][k] = v.strip() if isinstance(v, str) else v
    if patch:
        for section in ("anchors", "identity", "capability_snapshot"):
            sec = patch.get(section)
            if not isinstance(sec, dict):
                continue
            for k, v in sec.items():
                if v is None:
                    continue
                if isinstance(v, str) and not v.strip():
                    continue
                base[section][k] = v.strip() if isinstance(v, str) else v
    return update_clarity(base)


def merge_current_fragment(universal: dict[str, Any], fragment: str) -> dict[str, Any]:
    """逐步拼接 current。"""
    text = (fragment or "").strip()
    if not text:
        return universal
    anchors = universal.setdefault("anchors", {})
    existing = (anchors.get("current") or "").strip()
    if not existing:
        anchors["current"] = text
    elif text not in existing:
        anchors["current"] = f"{existing}；{text}"
    return update_clarity(universal)


def anchors_ready(universal: dict[str, Any]) -> bool:
    return goal_is_resolved(universal) and current_is_resolved(universal)


def goal_is_resolved(universal: dict[str, Any]) -> bool:
    """核心学习目标是否已明确（非「未明确/待定」类描述）。"""
    anchors = universal.get("anchors") or {}
    goal = (anchors.get("goal") or "").strip()
    if not goal:
        return False
    if VAGUE_ANCHOR_MARKERS.search(goal) or goal.startswith("用户"):
        return False
    clarity = anchors.get("goal_clarity") or _assess_goal_clarity(goal)
    if clarity == "low":
        return False
    if clarity == "high":
        return True
    return bool(GOAL_SIGNALS.search(goal))


def current_is_resolved(universal: dict[str, Any]) -> bool:
    """现状是否足以支撑规划（非空、非模糊描述）。"""
    anchors = universal.get("anchors") or {}
    current = (anchors.get("current") or "").strip()
    if VAGUE_ANCHOR_MARKERS.search(current) or (current and current.startswith("用户")):
        return False
    clarity = anchors.get("current_clarity") or _assess_current_clarity(current, universal)
    if clarity == "low" and not current:
        return False
    if clarity == "high":
        return True
    ident = universal.get("identity") or {}
    if _filled(ident.get("occupation")) and (current or _filled(ident.get("age_range"))):
        return clarity in ("medium", "high")
    return clarity in ("medium", "high") and bool(current)


def clarity_rank(level: str) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get(level, 0)


def missing_universal_fields(universal: dict[str, Any]) -> list[str]:
    """基础身份字段未齐时须追问（由 LLM 推断填充，不硬编码）。"""
    return missing_baseline_fields(universal)


def snapshot_for_planner(universal: dict[str, Any]) -> dict[str, Any]:
    u = deepcopy(universal)
    return u
