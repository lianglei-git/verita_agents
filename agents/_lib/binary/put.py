"""预签 PUT（方案 A）。LS 注入 upload，Agent 只 PUT 一次完整对象。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class BinaryError(Exception):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code
        self.message = message or code


def parse_upload(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise BinaryError("missing_upload", "LS binary skill requires upload.{url,method,headers}")
    url = str(raw.get("url") or "").strip()
    if not url:
        raise BinaryError("missing_upload", "upload.url is required")
    method = str(raw.get("method") or "PUT").strip().upper() or "PUT"
    if method != "PUT":
        raise BinaryError("unsupported_upload_method", f"upload.method must be PUT, got {method}")
    headers = raw.get("headers") if isinstance(raw.get("headers"), dict) else {}
    headers = {str(k): str(v) for k, v in headers.items()}
    max_bytes = raw.get("max_bytes")
    try:
        max_bytes_i = int(max_bytes) if max_bytes is not None else 0
    except (TypeError, ValueError):
        max_bytes_i = 0
    return {
        "url": url,
        "method": method,
        "headers": headers,
        "expires_at": str(raw.get("expires_at") or ""),
        "max_bytes": max_bytes_i,
    }


def _expired(expires_at: str) -> bool:
    raw = (expires_at or "").strip()
    if not raw:
        return False
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        when = datetime.fromisoformat(raw)
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) >= when
    except ValueError:
        return False


def put_bytes(upload: dict[str, Any], data: bytes, *, default_content_type: str) -> None:
    spec = parse_upload(upload)
    if _expired(spec["expires_at"]):
        raise BinaryError("upload_expired", "upload.expires_at has passed")
    if spec["max_bytes"] and len(data) > spec["max_bytes"]:
        raise BinaryError("payload_too_large", f"{len(data)} bytes exceeds max_bytes={spec['max_bytes']}")
    headers = dict(spec["headers"])
    if not any(k.lower() == "content-type" for k in headers):
        headers["Content-Type"] = default_content_type
    req = Request(spec["url"], data=data, method="PUT", headers=headers)
    try:
        with urlopen(req, timeout=120) as resp:  # noqa: S310 — LS presigned URL
            status = getattr(resp, "status", 200) or 200
            if int(status) >= 400:
                raise BinaryError("upload_failed", f"PUT status {status}")
    except BinaryError:
        raise
    except HTTPError as exc:
        raise BinaryError("upload_failed", f"PUT HTTP {exc.code}") from exc
    except URLError as exc:
        raise BinaryError("upload_failed", str(exc.reason or exc)) from exc


def require_upload(kwargs: dict[str, Any]) -> dict[str, Any] | None:
    """Return parsed upload if present; None if workbench (no upload key)."""
    if "upload" not in kwargs:
        return None
    return parse_upload(kwargs.get("upload"))


def json_error(code: str, message: str, **extra: Any) -> dict[str, Any]:
    body: dict[str, Any] = {"error": code, "message": message, "output": extra.pop("output", None)}
    body.update(extra)
    return body
