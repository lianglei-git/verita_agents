"""TTS 流式事件与类型。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

TtsEvent = Literal[
    "sentence_start",
    "audio_delta",
    "sentence_end",
    "error",
    "done",
]


@dataclass
class TtsChunk:
    event: TtsEvent
    sentence_index: int | None = None
    text: str | None = None
    audio_b64: str | None = None
    mime: str | None = None
    audio_url: str | None = None
    duration_ms: int | None = None
    error: str | None = None
    sample_rate: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}
