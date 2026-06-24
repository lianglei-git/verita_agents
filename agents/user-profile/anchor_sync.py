"""PRD v2 — 将 journey_meta 闭合项同步回 anchors（避免 meta 已答但锚点仍模糊）。"""

from __future__ import annotations

from typing import Any

from universal_model import update_clarity

META_STATUSES_CLOSED = frozenset({"inferred", "confirmed", "waived"})

# meta.key → 写入 anchors 的哪一段
GOAL_META_KEYS = frozenset({
    "learning_goal",
    "goal_specifics",
    "primary_use_case",
    "target_exam",
    "target_exam_or_certification",
    "exam_type",
    "study_purpose",
})

CURRENT_META_KEYS = frozenset({
    "current_english_level",
    "available_study_time",
    "school_english_curriculum",
    "english_background",
    "current_level",
    "weekly_study_hours",
    "preferred_learning_style",
})


def sync_anchors_from_metas(universal: dict[str, Any], collection: dict[str, Any]) -> dict[str, Any]:
    anchors = universal.setdefault("anchors", {})
    goal_values: list[str] = []
    current_values: list[str] = []

    for meta in collection.get("journey_meta") or []:
        if meta.get("status") not in META_STATUSES_CLOSED:
            continue
        val = (meta.get("value") or "").strip()
        if not val or val in ("暂未明确", "用户跳过"):
            continue
        key = meta.get("key") or ""
        label = meta.get("label") or key
        if key in GOAL_META_KEYS:
            goal_values.append(val)
        elif key in CURRENT_META_KEYS:
            current_values.append(f"{label}：{val}")

    if goal_values:
        anchors["goal"] = goal_values[0]
        anchors["goal_clarity"] = "high"

    if current_values:
        existing = (anchors.get("current") or "").strip()
        from universal_model import VAGUE_ANCHOR_MARKERS  # noqa: PLC0415

        if VAGUE_ANCHOR_MARKERS.search(existing) or existing.startswith("用户"):
            existing = ""
        merged = "；".join(current_values)
        if existing and merged not in existing:
            anchors["current"] = f"{existing}；{merged}"
        else:
            anchors["current"] = merged or existing
        anchors["current_clarity"] = "high"

    return update_clarity(universal)
