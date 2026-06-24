"""PRD v2 — 回答写入 universal / journey_meta（LLM 语义推断）。"""

from __future__ import annotations

from typing import Any

from anchor_extractor import absorb_text
from anchor_sync import sync_anchors_from_metas
from llm_inference import infer_metas_from_answer
from meta_collection import find_meta


def _close_meta(meta: dict, value: str, source: str = "user", confidence: float = 0.9) -> None:
    meta["value"] = value.strip()
    meta["status"] = "confirmed" if source == "user" else "inferred"
    meta["confidence"] = confidence
    meta["source"] = source


def _apply_meta_updates(collection: dict, updates: list[dict]) -> list[str]:
    closed: list[str] = []
    for upd in updates:
        key = upd.get("key")
        if not key:
            continue
        meta = find_meta(collection, key)
        if not meta or meta.get("status") != "open":
            continue
        value = (upd.get("value") or "").strip()
        if not value:
            continue
        conf = float(upd.get("confidence") or 0.75)
        _close_meta(meta, value, source="inferred", confidence=conf)
        closed.append(f"meta:{key}")
    return closed


def apply_target_answer(
    universal: dict[str, Any],
    collection: dict[str, Any],
    target: str,
    text: str,
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    """处理单题回答。返回 (universal, collection, inferred_paths)。"""
    raw = (text or "").strip()
    inferred: list[str] = []

    if not raw:
        return universal, collection, inferred

    if target.startswith("anchor:"):
        universal, inf = absorb_text(universal, raw, target=target)
        inferred.extend(inf)
    elif target.startswith("universal:"):
        universal, inf = absorb_text(universal, raw, target=target)
        inferred.extend(inf)
    elif target.startswith("meta:"):
        key = target.split(":", 1)[1]
        meta = find_meta(collection, key)
        if meta:
            _close_meta(meta, raw, source="user")
            inferred.append(f"meta:{key}")
        llm_updates = infer_metas_from_answer(universal, collection, raw, target_key=key)
        inferred.extend(_apply_meta_updates(collection, llm_updates))
    else:
        universal, inf = absorb_text(universal, raw)
        inferred.extend(inf)
        llm_updates = infer_metas_from_answer(universal, collection, raw, target_key="")
        inferred.extend(_apply_meta_updates(collection, llm_updates))

    ledger = dict(collection.get("answered_effective") or {})
    ledger[target] = {"raw": raw, "inferred": inferred}
    collection["answered_effective"] = ledger

    universal = sync_anchors_from_metas(universal, collection)

    return universal, collection, list(dict.fromkeys(inferred))
