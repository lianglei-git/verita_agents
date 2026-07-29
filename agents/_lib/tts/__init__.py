"""可插拔 TTS：统一流式契约 + 厂商 provider。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from _lib.tts.base import TtsError, TtsProvider
from _lib.tts.config import TtsConfig
from _lib.tts.types import TtsChunk
from _lib.tts.utterance import synthesize_utterance
from _lib.tts.wav_utils import concat_wavs, pcm16le_to_wav, wav_duration_ms

if TYPE_CHECKING:
    pass

_PROVIDERS = {
    "aliyun": "aliyun_dashscope",
    "aliyun_dashscope": "aliyun_dashscope",
    "dashscope": "aliyun_dashscope",
    "tencent": "tencent",
}


def is_tts_available(cfg: TtsConfig | None = None) -> bool:
    cfg = cfg or TtsConfig()
    if cfg.disabled:
        return False
    try:
        provider = get_provider(cfg)
    except TtsError:
        return False
    return provider.is_available()


def get_provider(cfg: TtsConfig | None = None) -> TtsProvider:
    cfg = cfg or TtsConfig()
    key = (cfg.provider or "aliyun").strip().lower()
    alias = _PROVIDERS.get(key)
    if alias == "aliyun_dashscope":
        from _lib.tts.providers.aliyun_dashscope import AliyunDashScopeProvider

        return AliyunDashScopeProvider(cfg)
    if alias == "tencent":
        from _lib.tts.providers.tencent import TencentTtsProvider

        return TencentTtsProvider(cfg)
    raise TtsError(
        f"Unknown TTS_PROVIDER={cfg.provider!r}. "
        f"Supported: {', '.join(sorted(set(_PROVIDERS)))}"
    )


__all__ = [
    "TtsChunk",
    "TtsConfig",
    "TtsError",
    "TtsProvider",
    "concat_wavs",
    "get_provider",
    "is_tts_available",
    "pcm16le_to_wav",
    "synthesize_utterance",
    "wav_duration_ms",
]
