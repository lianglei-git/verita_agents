"""PRD v2 — 会话 collection 状态。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

PRIORITY_ORDER = ("blocking", "important", "optional")
META_STATUSES_CLOSED = frozenset({"inferred", "confirmed", "waived"})
MAX_META_ASKS = 2


def empty_collection_v2() -> dict[str, Any]:
    return {
        "engine_version": "2.0",
        "phase": "anchoring",
        "journey_meta": [],
        "meta_plan_version": 0,
        "route_sketch": None,
        "distance_summary": "",
        "asked_log": [],
        "assumptions": [],
        "answered_effective": {},
        "confident_fields": {},
        "turn_count": 0,
        "release": {
            "status": "collecting",
            "reason": "建立目标与现状认知",
            "confidence": 0.0,
        },
    }


def merge_collection_v2(existing: dict | None, patch: dict | None = None) -> dict[str, Any]:
    base = empty_collection_v2()
    if existing:
        base.update(deepcopy(existing))
    if patch:
        for k, v in patch.items():
            if k == "release" and isinstance(v, dict):
                base.setdefault("release", {}).update(v)
            else:
                base[k] = v
    if base.get("engine_version") != "2.0":
        base["engine_version"] = "2.0"
    return base


def record_turn(collection: dict, *, target: str, question: str) -> dict:
    collection = merge_collection_v2(collection)
    collection["turn_count"] = int(collection.get("turn_count") or 0) + 1
    log = list(collection.get("asked_log") or [])
    log.append({"target": target, "question": question, "turn": collection["turn_count"]})
    collection["asked_log"] = log
    return collection


def find_meta(collection: dict, key: str) -> dict | None:
    for item in collection.get("journey_meta") or []:
        if item.get("key") == key:
            return item
    return None


def open_metas(collection: dict, priority: str | None = None) -> list[dict]:
    items = collection.get("journey_meta") or []
    out = [
        m
        for m in items
        if m.get("status") == "open" and int(m.get("asked_count") or 0) < MAX_META_ASKS
    ]
    if priority:
        out = [m for m in out if m.get("priority") == priority]
    return out


def record_meta_presented(collection: dict, key: str) -> dict:
    for m in collection.get("journey_meta") or []:
        if m.get("key") == key:
            m["asked_count"] = int(m.get("asked_count") or 0) + 1
            if m["asked_count"] >= MAX_META_ASKS and m.get("status") == "open":
                m["status"] = "waived"
                m["value"] = m.get("value") or "暂未明确"
                assumptions = list(collection.get("assumptions") or [])
                assumptions.append(
                    {
                        "field": f"meta:{key}",
                        "value": m["value"],
                        "reason": f"关于「{m.get('label', key)}」多次未能明确，按未知继续",
                    }
                )
                collection["assumptions"] = assumptions
            break
    return collection


def blocking_closed(collection: dict) -> bool:
    for m in collection.get("journey_meta") or []:
        if m.get("priority") == "blocking" and m.get("status") == "open":
            return False
    return True


def meta_progress(collection: dict) -> dict[str, int]:
    items = collection.get("journey_meta") or []
    blocking = [m for m in items if m.get("priority") == "blocking"]
    closed = [m for m in blocking if m.get("status") in META_STATUSES_CLOSED]
    return {"blocking_total": len(blocking), "blocking_closed": len(closed)}


def bump_meta_asked(collection: dict, key: str) -> dict:
    for m in collection.get("journey_meta") or []:
        if m.get("key") == key:
            m["asked_count"] = int(m.get("asked_count") or 0) + 1
            if m["asked_count"] >= MAX_META_ASKS and m.get("status") == "open":
                m["status"] = "waived"
                m["value"] = m.get("value") or "暂未明确"
                assumptions = list(collection.get("assumptions") or [])
                assumptions.append(
                    {
                        "field": f"meta:{key}",
                        "value": m["value"],
                        "reason": f"关于「{m.get('label', key)}」多次未能明确，按未知继续",
                    }
                )
                collection["assumptions"] = assumptions
            break
    return collection
