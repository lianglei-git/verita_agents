"""sentence.extract — 从转写/正文/cue 拆出学习句。"""

from __future__ import annotations

import json
import re
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

AGENT_ID = "sentence-extract"
PACKAGE_VERSION = "1.0.0"
SKILL = "sentence.extract"

_END_RE = re.compile(r"(?:……|…|\.{3,}|[。！？!?．]|\.(?=\s|$))\s*")
_SHORT_MERGE = 80
_LONG_SPLIT = 180

_SYSTEM = (
    "You split learning sentences from transcript or subtitle cues. "
    "Merge fragments that are not complete sentences. Split run-on lines. "
    "Reply with JSON only: {\"sentences\":[{\"text\":\"...\",\"cue_ids\":[\"c1\"]}]}. "
    "Use only given cue ids. Do not invent timestamps. No markdown."
)


def _ends_sentence(text: str) -> bool:
    s = (text or "").rstrip()
    if not s:
        return False
    return bool(_END_RE.search(s[-8:])) or s[-1] in "。！？!?."


def split_text(text: str) -> list[str]:
    raw = (text or "").strip()
    if not raw:
        return []
    parts: list[str] = []
    start = 0
    for match in _END_RE.finditer(raw):
        piece = raw[start : match.end()].strip()
        if piece:
            parts.append(piece)
        start = match.end()
    tail = raw[start:].strip()
    if tail:
        parts.append(tail)
    return parts or ([raw] if raw else [])


def normalize_cues(cues: Any) -> list[dict[str, Any]]:
    if not isinstance(cues, list):
        return []
    out: list[dict[str, Any]] = []
    for i, row in enumerate(cues):
        if not isinstance(row, dict):
            continue
        text = str(row.get("text") or "").strip()
        if not text:
            continue
        out.append(
            {
                "id": str(row.get("id") or f"c{i}"),
                "text": text,
                "start_ms": row.get("start_ms"),
                "end_ms": row.get("end_ms"),
            }
        )
    return out


def _maybe_split_buf(buf: dict[str, Any]) -> list[dict[str, Any]]:
    text = buf["text"]
    if len(text) < _LONG_SPLIT or text.count(" ") < 8:
        pieces = split_text(text) if _ends_sentence(text) and len(split_text(text)) > 1 else [text]
        if len(pieces) <= 1:
            return [
                {
                    "text": text,
                    "start_ms": buf.get("start_ms"),
                    "end_ms": buf.get("end_ms"),
                    "cue_ids": list(buf.get("cue_ids") or []),
                }
            ]
    else:
        pieces = split_text(text)
        if len(pieces) <= 1:
            pieces = [text]
    n = len(pieces)
    start = buf.get("start_ms")
    end = buf.get("end_ms")
    rows: list[dict[str, Any]] = []
    for i, piece in enumerate(pieces):
        row_start, row_end = start, end
        if (
            n > 1
            and isinstance(start, int)
            and isinstance(end, int)
            and end >= start
        ):
            span = end - start
            row_start = start + int(span * i / n)
            row_end = start + int(span * (i + 1) / n)
        rows.append(
            {
                "text": piece,
                "start_ms": row_start,
                "end_ms": row_end,
                "cue_ids": list(buf.get("cue_ids") or []),
            }
        )
    return rows


def extract_from_cues(cues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sentences: list[dict[str, Any]] = []
    buf: dict[str, Any] | None = None
    for cue in cues:
        if buf is None:
            buf = {
                "text": cue["text"],
                "start_ms": cue.get("start_ms"),
                "end_ms": cue.get("end_ms"),
                "cue_ids": [cue["id"]],
            }
            continue
        if not _ends_sentence(buf["text"]) and len(buf["text"]) < _SHORT_MERGE:
            buf["text"] = f"{buf['text']} {cue['text']}".strip()
            if cue.get("end_ms") is not None:
                buf["end_ms"] = cue.get("end_ms")
            buf["cue_ids"].append(cue["id"])
            continue
        sentences.extend(_maybe_split_buf(buf))
        buf = {
            "text": cue["text"],
            "start_ms": cue.get("start_ms"),
            "end_ms": cue.get("end_ms"),
            "cue_ids": [cue["id"]],
        }
    if buf:
        sentences.extend(_maybe_split_buf(buf))
    return sentences


def extract_from_text(text: str) -> list[dict[str, Any]]:
    return [
        {"text": piece, "start_ms": None, "end_ms": None, "cue_ids": []}
        for piece in split_text(text)
    ]


def _has_media(cues: list[dict[str, Any]]) -> bool:
    return any(c.get("start_ms") is not None or c.get("end_ms") is not None for c in cues)


def _null_times_if_no_media(
    sentences: list[dict[str, Any]], has_media: bool
) -> list[dict[str, Any]]:
    if has_media:
        return sentences
    for row in sentences:
        row["start_ms"] = None
        row["end_ms"] = None
    return sentences


def run(user_input: str, **kwargs: Any) -> dict[str, Any]:
    learning = str(kwargs.get("learning_language") or "en").strip() or "en"
    text = str(kwargs.get("text") or user_input or "").strip()
    cues = normalize_cues(kwargs.get("cues"))
    meta = {
        "agent": AGENT_ID,
        "package_version": PACKAGE_VERSION,
        "skill": SKILL,
        "learning_language": learning,
    }
    if not text and not cues:
        return {
            "error": "empty_input",
            "message": "provide text and/or cues[]",
            "output": {"sentences": []},
            "usage": {"provider": "", "model": "", "tokens": 0, "usage_sec": 0, "cost_micros": None},
            "meta": meta,
        }

    has_media = _has_media(cues)
    if cues:
        sentences = extract_from_cues(cues)
        if text and not sentences:
            sentences = extract_from_text(text)
    else:
        sentences = extract_from_text(text)
    sentences = _null_times_if_no_media(sentences, has_media)

    tokens = 0
    model = ""
    if is_llm_available() and sentences:
        client = get_client()
        if client is not None:
            payload = {
                "learning_language": learning,
                "text": text,
                "cues": cues,
                "draft": sentences,
            }
            try:
                data = client.chat_json(json.dumps(payload, ensure_ascii=False), system=_SYSTEM)
                raw = data.get("sentences") if isinstance(data, dict) else None
                if isinstance(raw, list) and raw:
                    refined: list[dict[str, Any]] = []
                    known = {c["id"] for c in cues}
                    for row in raw:
                        if not isinstance(row, dict):
                            continue
                        piece = str(row.get("text") or "").strip()
                        if not piece:
                            continue
                        ids = [
                            str(x)
                            for x in (row.get("cue_ids") or [])
                            if str(x) in known
                        ]
                        match = next((s for s in sentences if s["text"] == piece), None)
                        refined.append(
                            {
                                "text": piece,
                                "start_ms": match["start_ms"] if match else None,
                                "end_ms": match["end_ms"] if match else None,
                                "cue_ids": ids or (match["cue_ids"] if match else []),
                            }
                        )
                    if refined:
                        sentences = _null_times_if_no_media(refined, has_media)
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
        meta["llm_status"] = "heuristic"

    return {
        "output": {"sentences": sentences},
        "usage": {
            "provider": "llm" if tokens else "",
            "model": model,
            "tokens": tokens,
            "usage_sec": 0,
            "cost_micros": None,
        },
        "meta": meta,
    }


if __name__ == "__main__":
    print(
        json.dumps(
            run(
                "",
                learning_language="en",
                cues=[
                    {"id": "c1", "text": "I am.", "start_ms": 1, "end_ms": 2},
                    {"id": "c2", "text": "We're in a competitive industry.", "start_ms": 3, "end_ms": 9},
                ],
            ),
            ensure_ascii=False,
            indent=2,
        )
    )
