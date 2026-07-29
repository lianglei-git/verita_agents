"""TTS 配置 — 环境变量。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class TtsConfig:
    provider: str = field(
        default_factory=lambda: os.getenv("TTS_PROVIDER", "aliyun").strip().lower() or "aliyun"
    )
    disabled: bool = field(
        default_factory=lambda: os.getenv("TTS_DISABLED", "").lower() in ("1", "true", "yes")
    )
    # DashScope / 阿里云百炼
    dashscope_api_key: str = field(
        default_factory=lambda: os.getenv("DASHSCOPE_API_KEY", "").strip()
    )
    dashscope_base_url: str = field(
        default_factory=lambda: os.getenv(
            "DASHSCOPE_BASE_HTTP_API_URL",
            "https://dashscope.aliyuncs.com/api/v1",
        ).rstrip("/")
    )
    model: str = field(
        default_factory=lambda: os.getenv("TTS_MODEL", "qwen3-tts-flash").strip()
        or "qwen3-tts-flash"
    )
    voice: str = field(
        default_factory=lambda: os.getenv("TTS_VOICE", "Cherry").strip() or "Cherry"
    )
    sample_rate: int = field(
        default_factory=lambda: int(os.getenv("TTS_SAMPLE_RATE", "24000"))
    )
    mime: str = field(
        default_factory=lambda: os.getenv("TTS_MIME", "audio/pcm").strip() or "audio/pcm"
    )
    media_dir: str = field(
        default_factory=lambda: os.getenv("TTS_MEDIA_DIR", "").strip()
    )

    @classmethod
    def from_overrides(cls, overrides: dict | None = None) -> "TtsConfig":
        cfg = cls()
        if not overrides:
            return cfg
        for key, val in overrides.items():
            if hasattr(cfg, key) and val is not None:
                setattr(cfg, key, val)
        return cfg
