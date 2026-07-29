"""TTS provider 协议与公共错误。"""

from __future__ import annotations

from typing import Iterator, Protocol

from _lib.tts.types import TtsChunk


class TtsError(RuntimeError):
    """TTS 调用失败。"""


class TtsProvider(Protocol):
    name: str

    def is_available(self) -> bool: ...

    def synthesize_stream(
        self,
        text: str,
        *,
        voice: str | None = None,
        sentence_index: int = 0,
    ) -> Iterator[TtsChunk]:
        """对单句文本做流式合成：产出 audio_delta…，以 sentence_end（或 error）收尾。"""
        ...
