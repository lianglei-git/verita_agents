"""Helpers for stripping ephemeral audio from agent results before history persist."""

from __future__ import annotations

import copy
from typing import Any


_AUDIO_KEYS = {
    "audio_b64",
    "audio_data_uri",
    "audio_url",
    "audio",
    "data",
}


def strip_ephemeral_audio(result: dict[str, Any] | None) -> dict[str, Any] | None:
    """Deep-copy result and remove audio payloads when meta.ephemeral_audio is set."""
    if not isinstance(result, dict):
        return result

    meta = result.get("meta")
    ephemeral = isinstance(meta, dict) and bool(meta.get("ephemeral_audio"))
    # Always strip obvious audio keys from TTS-shaped payloads
    has_audio_shape = any(k in result for k in _AUDIO_KEYS) or (
        isinstance(result.get("sentences"), list)
        and any(
            isinstance(s, dict) and any(k in s for k in _AUDIO_KEYS)
            for s in result["sentences"]
        )
    )
    if not ephemeral and not has_audio_shape:
        return result

    slim = copy.deepcopy(result)
    for key in _AUDIO_KEYS:
        slim.pop(key, None)

    sentences = slim.get("sentences")
    if isinstance(sentences, list):
        slim["sentences"] = [
            (
                {k: v for k, v in item.items() if k not in _AUDIO_KEYS}
                if isinstance(item, dict)
                else item
            )
            for item in sentences
        ]

    meta2 = slim.setdefault("meta", {})
    if isinstance(meta2, dict):
        meta2["ephemeral_audio"] = True
    return slim
