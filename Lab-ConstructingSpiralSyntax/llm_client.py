from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from openai import OpenAI, APIError, APITimeoutError, RateLimitError

from config import LLMConfig

logger = logging.getLogger(__name__)


def _model_max_output_tokens(model: str, configured_max_tokens: int) -> int:
    """Cap max_tokens by known model-specific output limits."""
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
        """Call LLM with retry on transient errors, return raw text."""
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
            except (APITimeoutError, RateLimitError) as e:
                last_err = e
                wait = self.cfg.retry_delay * (2 ** attempt)
                logger.warning("LLM transient error (attempt %d): %s — retry in %.1fs", attempt + 1, e, wait)
                time.sleep(wait)
            except APIError as e:
                last_err = e
                logger.error("LLM API error: %s", e)
                break
        raise RuntimeError(f"LLM call failed after retries: {last_err}")

    def chat_json(self, prompt: str, system: str = "You are a helpful assistant. Always respond with valid JSON only.") -> dict[str, Any]:
        """Call LLM and parse JSON from response."""
        raw = self.chat(prompt, system)
        return _extract_json(raw)

    def stats(self) -> dict:
        return {
            "call_count": self.call_count,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
        }


def _extract_json(text: str) -> dict[str, Any]:
    """Try to parse JSON from LLM response, stripping markdown fences."""
    text = text.strip()
    # Strip ```json ... ``` fences
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"```\s*$", "", text, flags=re.MULTILINE)
    text = text.strip()

    # Find the first {...} block
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error("JSON parse error: %s\nRaw: %s", e, text[:300])
        raise
