"""OpenAI 兼容 LLM 客户端 — 重试、JSON、token 统计。"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from openai import APIError, APITimeoutError, OpenAI, RateLimitError

from _lib.json_utils import extract_json
from _lib.llm.config import LLMConfig

logger = logging.getLogger(__name__)

_CLIENT: "LLMClient | None" = None


def is_llm_available() -> bool:
    disabled = os.getenv("LLM_DISABLED", "").lower() in ("1", "true", "yes")
    return not disabled and bool(os.getenv("OPENAI_API_KEY", "").strip())


def get_client(cfg: LLMConfig | None = None) -> "LLMClient | None":
    """获取 LLM 客户端；无 API key 或 LLM_DISABLED 时返回 None。"""
    if not is_llm_available():
        return None
    global _CLIENT
    if cfg is None:
        if _CLIENT is None:
            _CLIENT = LLMClient(LLMConfig())
        return _CLIENT
    return LLMClient(cfg)


def _model_max_output_tokens(model: str, configured_max_tokens: int) -> int:
    name = (model or "").strip().lower()
    if "deepseek-reasoner" in name:
        return min(configured_max_tokens, 64000)
    if "deepseek-chat" in name:
        return min(configured_max_tokens, 8192)
    return configured_max_tokens


class LLMClient:
    def __init__(self, cfg: LLMConfig):
        self.cfg = cfg
        self._client = OpenAI(
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            timeout=cfg.timeout,
        )
        self.call_count = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def chat(self, prompt: str, system: str = "You are a helpful assistant.") -> str:
        last_err: Exception | None = None
        for attempt in range(self.cfg.max_retries + 1):
            try:
                request_max_tokens = _model_max_output_tokens(self.cfg.model, self.cfg.max_tokens)
                response = self._client.chat.completions.create(
                    model=self.cfg.model,
                    temperature=self.cfg.temperature,
                    max_tokens=request_max_tokens,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                )
                self.call_count += 1
                usage = response.usage
                if usage:
                    self.total_input_tokens += usage.prompt_tokens
                    self.total_output_tokens += usage.completion_tokens
                return response.choices[0].message.content or ""
            except (APITimeoutError, RateLimitError) as exc:
                last_err = exc
                wait = self.cfg.retry_delay * (2**attempt)
                logger.warning(
                    "LLM transient error (attempt %d/%d): %s — retry in %.1fs",
                    attempt + 1,
                    self.cfg.max_retries + 1,
                    exc,
                    wait,
                )
                time.sleep(wait)
            except APIError as exc:
                last_err = exc
                logger.error("LLM API error: %s", exc)
                break
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                logger.error("LLM unexpected error: %s", exc)
                break

        detail = f"LLM call failed after {self.cfg.max_retries + 1} retries"
        if last_err:
            detail += f": {last_err}"
        raise RuntimeError(detail)

    def chat_json(
        self,
        prompt: str,
        system: str = "You are a helpful assistant. Always respond with valid JSON only.",
    ) -> dict[str, Any]:
        raw = self.chat(prompt, system)
        return extract_json(raw)

    def stats(self) -> dict[str, int]:
        return {
            "call_count": self.call_count,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
        }
