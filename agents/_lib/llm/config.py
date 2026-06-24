"""LLM 配置 — 从环境变量读取，各 agent 可覆盖。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class LLMConfig:
    api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    base_url: str = field(
        default_factory=lambda: os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com")
    )
    model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "deepseek-chat"))
    temperature: float = field(default_factory=lambda: float(os.getenv("LLM_TEMPERATURE", "0.2")))
    max_retries: int = field(default_factory=lambda: int(os.getenv("LLM_MAX_RETRIES", "3")))
    retry_delay: float = field(default_factory=lambda: float(os.getenv("LLM_RETRY_DELAY", "2.0")))
    timeout: float = field(default_factory=lambda: float(os.getenv("LLM_TIMEOUT", "120")))
    max_tokens: int = field(default_factory=lambda: int(os.getenv("LLM_MAX_TOKENS", "4096")))

    @classmethod
    def from_overrides(cls, overrides: dict | None) -> "LLMConfig":
        if not overrides:
            return cls()
        cfg = cls()
        for key, val in overrides.items():
            if hasattr(cfg, key) and val is not None:
                setattr(cfg, key, val)
        return cfg
