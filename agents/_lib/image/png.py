"""把图像 API 结果收成 PNG 字节 + 宽高。"""

from __future__ import annotations

import base64
import io
import struct
from typing import Any
from urllib.request import Request, urlopen


def png_size(data: bytes) -> tuple[int, int]:
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not_png")
    width, height = struct.unpack(">II", data[16:24])
    return int(width), int(height)


def fetch_image_bytes(payload: dict[str, Any]) -> bytes:
    b64 = payload.get("b64_json")
    if b64:
        return base64.b64decode(b64)
    url = str(payload.get("url") or "").strip()
    if not url:
        raise RuntimeError("empty_image")
    req = Request(url, headers={"User-Agent": "verita-image/1.0"})
    with urlopen(req, timeout=60) as resp:  # noqa: S310 — vendor CDN
        return resp.read()


def ensure_png(data: bytes) -> bytes:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return data
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("png_convert_requires_pillow") from exc
    img = Image.open(io.BytesIO(data))
    if img.mode not in {"RGB", "RGBA"}:
        img = img.convert("RGBA" if "A" in img.getbands() else "RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
