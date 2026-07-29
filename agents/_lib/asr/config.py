"""ASR 配置 — 环境变量。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _dashscope_base_url() -> str:
    explicit = os.getenv("DASHSCOPE_BASE_HTTP_API_URL", "").strip()
    if explicit:
        return explicit.rstrip("/")
    workspace = os.getenv("DASHSCOPE_WORKSPACE_ID", "").strip()
    if workspace:
        return f"https://{workspace}.cn-beijing.maas.aliyuncs.com/api/v1"
    return "https://dashscope.aliyuncs.com/api/v1"


def _compatible_base_url() -> str:
    explicit = (
        os.getenv("ASR_COMPATIBLE_BASE_URL", "").strip()
        or os.getenv("DASHSCOPE_COMPATIBLE_BASE_URL", "").strip()
    )
    if explicit:
        return explicit.rstrip("/")
    workspace = os.getenv("DASHSCOPE_WORKSPACE_ID", "").strip()
    if workspace:
        return f"https://{workspace}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
    return "https://dashscope.aliyuncs.com/compatible-mode/v1"


def _subtitle_model() -> str:
    return (
        os.getenv("ASR_SUBTITLE_MODEL", "").strip()
        or os.getenv("ASR_MODEL", "").strip()
        or "paraformer-v2"
    )


def _compare_model() -> str:
    return os.getenv("ASR_COMPARE_MODEL", "").strip() or "qwen3-asr-flash"


@dataclass
class AsrConfig:
    disabled: bool = field(
        default_factory=lambda: os.getenv("ASR_DISABLED", "").lower() in ("1", "true", "yes")
    )
    api_key: str = field(
        default_factory=lambda: os.getenv("DASHSCOPE_API_KEY", "").strip()
    )
    base_http_api_url: str = field(default_factory=_dashscope_base_url)
    compatible_base_url: str = field(default_factory=_compatible_base_url)
    # subtitle / Paraformer（兼容旧 ASR_MODEL）
    model: str = field(default_factory=_subtitle_model)
    subtitle_model: str = field(default_factory=_subtitle_model)
    # compare / 跟读校对
    compare_model: str = field(default_factory=_compare_model)
    media_dir: str = field(
        default_factory=lambda: os.getenv("ASR_MEDIA_DIR", "").strip()
    )
    language_hints: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            h.strip()
            for h in os.getenv("ASR_LANGUAGE_HINTS", "zh,en").split(",")
            if h.strip()
        )
        or ("zh", "en")
    )

    @classmethod
    def from_overrides(cls, overrides: dict | None = None) -> "AsrConfig":
        cfg = cls()
        if not overrides:
            return cfg
        for key, val in overrides.items():
            if hasattr(cfg, key) and val is not None:
                setattr(cfg, key, val)
        if overrides.get("subtitle_model"):
            cfg.model = cfg.subtitle_model
        elif overrides.get("model"):
            cfg.subtitle_model = cfg.model
        return cfg
