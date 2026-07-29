"""腾讯云 TTS — 占位，尚未接入。"""

from __future__ import annotations

from typing import Iterator

from _lib.tts.config import TtsConfig
from _lib.tts.types import TtsChunk


class TencentTtsProvider:
    name = "tencent"

    def __init__(self, cfg: TtsConfig | None = None):
        self.cfg = cfg or TtsConfig()

    def is_available(self) -> bool:
        return False

    def synthesize_stream(
        self,
        text: str,
        *,
        voice: str | None = None,
        sentence_index: int = 0,
    ) -> Iterator[TtsChunk]:
        yield TtsChunk(
            event="error",
            sentence_index=sentence_index,
            text=text,
            error="tencent_tts_not_implemented",
        )
