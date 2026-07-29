"""可插拔 ASR：字幕 Paraformer + 校对 qwen3-asr-flash。"""

from __future__ import annotations

from _lib.asr.config import AsrConfig
from _lib.asr.diff import diff_tokens, tokenize
from _lib.asr.errors import AsrError
from _lib.asr.paraformer import is_asr_available, transcribe_url
from _lib.asr.qwen_flash import transcribe_audio
from _lib.asr.types import AsrResult, AsrSentence, AsrWord

__all__ = [
    "AsrConfig",
    "AsrError",
    "AsrResult",
    "AsrSentence",
    "AsrWord",
    "diff_tokens",
    "is_asr_available",
    "tokenize",
    "transcribe_audio",
    "transcribe_url",
]
