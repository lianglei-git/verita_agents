"""图像生成配置 — 从环境变量读取。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _default_api_key() -> str:
    return os.getenv("IMAGE_API_KEY", "").strip() or os.getenv("OPENAI_API_KEY", "").strip()


@dataclass
class ImageConfig:
    api_key: str = field(default_factory=_default_api_key)
    base_url: str = field(
        default_factory=lambda: os.getenv(
            "IMAGE_BASE_URL",
            os.getenv("OPENAI_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"),
        ).rstrip("/")
    )
    model: str = field(default_factory=lambda: os.getenv("IMAGE_MODEL", "glm-image"))
    timeout: float = field(default_factory=lambda: float(os.getenv("IMAGE_TIMEOUT", "120")))
    default_size: str = field(default_factory=lambda: os.getenv("IMAGE_DEFAULT_SIZE", "1280x1280"))

    @classmethod
    def from_overrides(cls, overrides: dict | None) -> "ImageConfig":
        if not overrides:
            return cls()
        cfg = cls()
        for key, val in overrides.items():
            if hasattr(cfg, key) and val is not None:
                setattr(cfg, key, val)
        return cfg
