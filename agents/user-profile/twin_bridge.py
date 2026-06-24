"""PRD v2 — universal ↔ legacy twin 映射（展示兼容）。"""

from __future__ import annotations

from typing import Any

from extract import merge_twin


def universal_from_legacy(payload: dict) -> dict[str, Any]:
    from universal_model import empty_universal, merge_universal

    if payload.get("universal"):
        return merge_universal(payload["universal"], None)

    twin = payload.get("twin") or {}
    u = empty_universal()
    ident = twin.get("identity") or {}
    growth = twin.get("growth") or {}
    cap = twin.get("capability") or {}

    patch = {
        "anchors": {
            "goal": growth.get("goal") or "",
            "current": _build_current_from_twin(twin),
        },
        "identity": {
            "age_range": ident.get("age_range") or "",
            "occupation": ident.get("occupation") or "",
            "region_anchor": ident.get("region_anchor") or ident.get("country") or ident.get("city") or "",
            "native_language": ident.get("native_language") or "",
            "role_anchor": ident.get("role_anchor") or "",
        },
        "capability_snapshot": {
            "self_assessed_level": cap.get("cefr") or cap.get("level_band") or "",
            "weakest": cap.get("bottleneck_for_goal") or "",
        },
    }
    return merge_universal(u, patch)


def collection_from_legacy(payload: dict) -> dict[str, Any]:
    from meta_collection import empty_collection_v2, merge_collection_v2

    if payload.get("collection") and payload["collection"].get("engine_version") == "2.0":
        return merge_collection_v2(payload["collection"])

    old = payload.get("collection") or {}
    c = empty_collection_v2()
    if old.get("route_sketch"):
        c["route_sketch"] = old["route_sketch"]
    elif old.get("path"):
        p = old["path"]
        c["route_sketch"] = {
            "title": p.get("title"),
            "summary": p.get("summary"),
            "milestones": p.get("milestones") or [],
        }
    c["turn_count"] = int(old.get("question_count") or old.get("turn_count") or 0)
    c["assumptions"] = list(old.get("assumptions") or [])
    return merge_collection_v2(c)


def _build_current_from_twin(twin: dict) -> str:
    ident = twin.get("identity") or {}
    cap = twin.get("capability") or {}
    parts: list[str] = []
    if ident.get("occupation"):
        parts.append(f"职业：{ident['occupation']}")
    if ident.get("age_range"):
        parts.append(f"年龄：{ident['age_range']}")
    if ident.get("region_anchor") or ident.get("city"):
        parts.append(f"地区：{ident.get('region_anchor') or ident.get('city')}")
    for sk, label in (("speaking", "口语"), ("listening", "听力")):
        if cap.get(sk) is not None:
            parts.append(f"{label}：{cap[sk]}")
    return "；".join(parts)


def twin_from_universal(universal: dict, collection: dict | None = None) -> dict:
    """生成 legacy twin 供 UI 展示。"""
    anchors = universal.get("anchors") or {}
    ident = universal.get("identity") or {}
    snap = universal.get("capability_snapshot") or {}

    twin = merge_twin(
        {},
        {
            "identity": {
                "age_range": ident.get("age_range") or "",
                "occupation": ident.get("occupation") or "",
                "region_anchor": ident.get("region_anchor") or "",
                "native_language": ident.get("native_language") or "",
                "role_anchor": ident.get("role_anchor") or "",
                "country": ident.get("region_anchor") or "",
                "city": "",
            },
            "growth": {"goal": anchors.get("goal") or "", "current_stage": ""},
            "capability": {
                "level_band": snap.get("self_assessed_level") or "",
                "cefr": snap.get("self_assessed_level") or "",
                "bottleneck_for_goal": snap.get("weakest") or "unknown",
            },
        },
    )

    if collection:
        for meta in collection.get("journey_meta") or []:
            if meta.get("status") in ("confirmed", "inferred") and meta.get("value"):
                _map_meta_to_twin(twin, meta)

    twin["_current_narrative"] = anchors.get("current") or ""
    return twin


def _map_meta_to_twin(twin: dict, meta: dict) -> None:
    key = meta.get("key") or ""
    val = meta.get("value") or ""
    scenario = twin.setdefault("scenario", {})
    growth = twin.setdefault("growth", {})
    mapping = {
        "target_market": ("scenario", "target_market"),
        "interview_type": ("scenario", "interview_type"),
        "target_exam": ("scenario", "target_exam"),
        "deadline": ("growth", "deadline"),
        "timeline_pressure": ("growth", "timeline_urgency"),
    }
    if key in mapping:
        section, field = mapping[key]
        twin.setdefault(section, {})[field] = val
