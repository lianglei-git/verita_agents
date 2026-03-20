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
                print(response)
                self.call_count += 1
                usage = response.usage
                if usage:
                    self.total_input_tokens += usage.prompt_tokens
                    self.total_output_tokens += usage.completion_tokens
                return response.choices[0].message.content or ""
            except Exception as e:
                print("报错了 曹：", e)
                pass
            except (APITimeoutError, RateLimitError) as e:
                last_err = e
                wait = self.cfg.retry_delay * (2 ** attempt)
                logger.warning("LLM transient error (attempt %d/%d): %s — retry in %.1fs", 
                             attempt + 1, self.cfg.max_retries + 1, e, wait)
                logger.info("API配置: model=%s, base_url=%s, timeout=%.1fs", 
                          self.cfg.model, self.cfg.base_url, self.cfg.timeout)
                time.sleep(wait)
            except (APIError) as e:
                last_err = e
                logger.error("LLM API error (attempt %d/%d): %s", 
                           attempt + 1, self.cfg.max_retries + 1, e)
                logger.error("详细错误信息: %s", str(e))
                if hasattr(e, 'response') and e.response is not None:
                    logger.error("响应状态码: %s", e.response.status_code)
                    if hasattr(e.response, 'headers'):
                        logger.error("响应头: %s", dict(e.response.headers))
                logger.info("API配置诊断: model=%s, base_url=%s, timeout=%.1fs", 
                          self.cfg.model, self.cfg.base_url, self.cfg.timeout)
                # 检查API密钥是否配置
                if not self.cfg.api_key:
                    logger.error("❌ API密钥未配置! 请检查OPENAI_API_KEY环境变量")
                else:
                    logger.info("✅ API密钥已配置 (前10位): %s...", self.cfg.api_key[:10])
                break
        # 构建更详细的错误信息
        error_details = f"LLM call failed after {self.cfg.max_retries + 1} retries"
        if last_err:
            error_details += f"\n最后错误: {last_err}"
            error_details += f"\n错误类型: {type(last_err).__name__}"
        error_details += f"\nAPI配置: model={self.cfg.model}, base_url={self.cfg.base_url}"
        error_details += f"\nAPI密钥配置: {'已配置' if self.cfg.api_key else '未配置'}"
        if self.cfg.api_key:
            error_details += f" (前10位: {self.cfg.api_key[:10]}...)"
        
        raise RuntimeError(error_details)

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
