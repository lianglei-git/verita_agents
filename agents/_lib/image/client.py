"""OpenAI 兼容图像生成客户端（智谱 GLM-Image 等）。"""

from __future__ import annotations

import logging
import os
from typing import Any

from openai import APIError, APITimeoutError, OpenAI, RateLimitError

from _lib.image.config import ImageConfig

logger = logging.getLogger(__name__)

_CLIENT: "ImageClient | None" = None


def is_image_api_available() -> bool:
    disabled = os.getenv("IMAGE_DISABLED", "").lower() in ("1", "true", "yes")
    key = os.getenv("IMAGE_API_KEY", "").strip() or os.getenv("OPENAI_API_KEY", "").strip()
    return not disabled and bool(key)


def get_image_client(cfg: ImageConfig | None = None) -> "ImageClient | None":
    if not is_image_api_available():
        return None
    global _CLIENT
    if cfg is None:
        if _CLIENT is None:
            _CLIENT = ImageClient(ImageConfig())
        return _CLIENT
    return ImageClient(cfg)


class ImageClient:
    def __init__(self, cfg: ImageConfig):
        self.cfg = cfg
        self._client = OpenAI(
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            timeout=cfg.timeout,
        )

    def generate(self, prompt: str, *, size: str | None = None) -> dict[str, Any]:
        size = size or self.cfg.default_size
        last_err: Exception | None = None
        for attempt in range(2):
            try:
                response = self._client.images.generate(
                    model=self.cfg.model,
                    prompt=prompt,
                    size=size,
                )
                data = response.data or []
                if not data:
                    raise RuntimeError("图像 API 未返回 data")
                item = data[0]
                url = getattr(item, "url", None) or (item.get("url") if isinstance(item, dict) else None)
                b64 = getattr(item, "b64_json", None) or (
                    item.get("b64_json") if isinstance(item, dict) else None
                )
                if not url and not b64:
                    raise RuntimeError("图像 API 响应缺少 url / b64_json")
                out: dict[str, Any] = {
                    "url": url,
                    "b64_json": b64,
                    "created": getattr(response, "created", None),
                }
                content_filter = getattr(response, "content_filter", None)
                if content_filter is not None:
                    out["content_filter"] = content_filter
                return out
            except (APITimeoutError, RateLimitError) as exc:
                last_err = exc
                logger.warning("Image API transient error (attempt %d): %s", attempt + 1, exc)
            except APIError as exc:
                last_err = exc
                logger.error("Image API error: %s", exc)
                break
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                logger.error("Image API unexpected error: %s", exc)
                break

        detail = "图像生成失败"
        if last_err:
            detail += f": {last_err}"
        raise RuntimeError(detail)
