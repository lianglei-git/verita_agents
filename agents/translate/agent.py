"""translate — 片段对齐翻译。id / 时间戳原样回传。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_AGENT_DIR = Path(__file__).resolve().parent
_AGENTS_ROOT = _AGENT_DIR.parent
for path in (_AGENTS_ROOT, _AGENT_DIR):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from _lib.llm import get_client, is_llm_available  # noqa: E402

AGENT_ID = "translate"
PACKAGE_VERSION = "1.0.0"
SKILL = "translate"

_SYSTEM = (
    "You translate subtitle or sentence fragments. "
    "Reply with JSON only: {\"items\":[{\"id\":\"...\",\"text\":\"...\"}]}. "
    "Keep every id. Do not add, drop, or reorder items. "
    "Do not wrap in markdown."
)


def normalize_items(user_input: str, kwargs: dict[str, Any]) -> list[dict[str, Any]]:
    raw = kwargs.get("items")
    items: list[dict[str, Any]] = []
    if isinstance(raw, list):
        for i, row in enumerate(raw):
            if not isinstance(row, dict):
                continue
            text = str(row.get("text") or "").strip()
            if not text:
                continue
            items.append(
                {
                    "id": str(row.get("id") or f"t{i + 1}"),
                    "text": text,
                    "start_ms": row.get("start_ms"),
                    "end_ms": row.get("end_ms"),
                }
            )
    if items:
        return items
    text = str(kwargs.get("text") or user_input or "").strip()
    if not text:
        return []
    return [{"id": "t1", "text": text, "start_ms": None, "end_ms": None}]


def align_translations(
    source_items: list[dict[str, Any]],
    translated: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    by_id: dict[str, str] = {}
    if isinstance(translated, list):
        for row in translated:
            if not isinstance(row, dict):
                continue
            tid = str(row.get("id") or "")
            if not tid:
                continue
            by_id[tid] = str(row.get("text") or "")
    out: list[dict[str, Any]] = []
    for src in source_items:
        item: dict[str, Any] = {
            "id": src["id"],
            "text": by_id.get(src["id"]) or src["text"],
        }
        if "start_ms" in src:
            item["start_ms"] = src.get("start_ms")
        if "end_ms" in src:
            item["end_ms"] = src.get("end_ms")
        out.append(item)
    return out


def _usage(tokens: int, model: str = "") -> dict[str, Any]:
    return {
        "provider": "llm" if tokens else "",
        "model": model,
        "tokens": tokens,
        "usage_sec": 0,
        "cost_micros": None,
    }


def run(user_input: str, **kwargs: Any) -> dict[str, Any]:
    source_lang = str(kwargs.get("source_lang") or "en").strip() or "en"
    target_lang = str(kwargs.get("target_lang") or "zh-CN").strip() or "zh-CN"
    items = normalize_items(user_input, kwargs)
    meta = {
        "agent": AGENT_ID,
        "package_version": PACKAGE_VERSION,
        "skill": SKILL,
        "source_lang": source_lang,
        "target_lang": target_lang,
    }
    if not items:
        return {
            "error": "empty_input",
            "message": "provide items[] or text",
            "output": {"items": []},
            "usage": _usage(0),
            "meta": meta,
        }

    translated: list[dict[str, Any]] | None = None
    tokens = 0
    model = ""
    if is_llm_available():
        client = get_client()
        if client is not None:
            payload = {
                "source_lang": source_lang,
                "target_lang": target_lang,
                "items": [{"id": it["id"], "text": it["text"]} for it in items],
            }
            try:
                data = client.chat_json(
                    json.dumps(payload, ensure_ascii=False),
                    system=_SYSTEM,
                )
                if isinstance(data, dict):
                    raw_items = data.get("items")
                    translated = raw_items if isinstance(raw_items, list) else None
                stats = client.stats()
                tokens = int(stats.get("total_input_tokens") or 0) + int(
                    stats.get("total_output_tokens") or 0
                )
                model = getattr(client.cfg, "model", "") or ""
                meta["llm_status"] = "success"
            except Exception as exc:  # noqa: BLE001
                meta["llm_status"] = "error"
                meta["llm_error"] = str(exc)
        else:
            meta["llm_status"] = "unavailable"
    else:
        meta["llm_status"] = "unavailable"

    aligned = align_translations(items, translated)
    result: dict[str, Any] = {
        "output": {"items": aligned},
        "usage": _usage(tokens, model),
        "meta": meta,
    }
    if meta.get("llm_status") == "unavailable":
        result["error"] = "llm_unavailable"
        result["message"] = "LLM unavailable; items echoed with original text (ids preserved)."
    return result


if __name__ == "__main__":
    print(
        json.dumps(
            run(
                "",
                source_lang="en",
                target_lang="zh-CN",
                items=[{"id": "c1", "text": "I am.", "start_ms": 1, "end_ms": 2}],
            ),
            ensure_ascii=False,
            indent=2,
        )
    )
