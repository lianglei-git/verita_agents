"""LS 统一信封：双 body 解析、响应包装、进程内幂等。"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Any

RESERVED_BODY_KEYS = frozenset({"input", "options", "run_id", "request_id"})

ENVELOPE_ERRORS = [
    {
        "http": 400,
        "code": "<agent error>",
        "retry": False,
        "message": "业务错误（如缺参、校验失败）。LS 不要重试。",
    },
    {
        "http": 401,
        "code": "unauthorized",
        "retry": False,
        "message": "缺少或错误的 X-Internal-Token。未设 INTERNAL_TOKEN 时不校验。",
    },
    {
        "http": 404,
        "code": "agent_not_found",
        "retry": False,
        "message": "未知 skill 或 agent id。",
    },
    {
        "http": 500,
        "code": "internal_error",
        "retry": True,
        "message": "未捕获异常或上游 5xx。LS 可重试。",
    },
]


class IdempotencyCache:
    """进程内 LRU。相同 request_id 回同一份响应，不落盘。"""

    def __init__(self, maxsize: int = 256) -> None:
        self.maxsize = maxsize
        self._data: OrderedDict[str, tuple[int, dict[str, Any]]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> tuple[int, dict[str, Any]] | None:
        with self._lock:
            hit = self._data.get(key)
            if hit is None:
                return None
            self._data.move_to_end(key)
            return hit

    def put(self, key: str, status: int, body: dict[str, Any]) -> None:
        with self._lock:
            self._data[key] = (status, body)
            self._data.move_to_end(key)
            while len(self._data) > self.maxsize:
                self._data.popitem(last=False)


IDEMPOTENCY = IdempotencyCache()


def idempotency_key(skill: str, request_id: str) -> str:
    return f"{skill}:{request_id}"


def parse_run_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    """兼容 Views `{input, options, run_id}` 与 LS 扁平字段 + `request_id`。"""
    data = payload if isinstance(payload, dict) else {}
    raw_rid = data.get("request_id")
    request_id = str(raw_rid).strip() if raw_rid is not None else ""
    run_id = data.get("run_id")

    options_raw = data.get("options")
    if isinstance(options_raw, dict):
        user_input = data.get("input")
        if user_input is None:
            user_input = ""
        return {
            "user_input": user_input,
            "options": dict(options_raw),
            "run_id": run_id,
            "request_id": request_id or None,
        }

    options = {k: v for k, v in data.items() if k not in RESERVED_BODY_KEYS}
    user_input = data.get("input")
    if user_input is None:
        user_input = data.get("text") or ""
    return {
        "user_input": user_input,
        "options": options,
        "run_id": run_id,
        "request_id": request_id or None,
    }


def extract_output(result: Any) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {"value": result}
    out = result.get("output")
    if isinstance(out, dict):
        return out
    return {k: v for k, v in result.items() if k not in {"error", "message"}}


def extract_usage(result: Any, latency_ms: int) -> dict[str, Any]:
    usage: dict[str, Any] = {
        "provider": "",
        "model": "",
        "tokens": 0,
        "usage_sec": 0,
        "cost_micros": None,
        "latency_ms": latency_ms,
    }
    if not isinstance(result, dict):
        return usage
    raw = result.get("usage")
    if isinstance(raw, dict):
        usage.update({k: raw[k] for k in usage if k in raw})
        usage["latency_ms"] = raw.get("latency_ms", latency_ms)
        return usage
    meta = result.get("meta")
    if isinstance(meta, dict):
        usage["provider"] = meta.get("provider") or ""
        usage["model"] = meta.get("model") or ""
        if meta.get("tokens") is not None:
            usage["tokens"] = meta["tokens"]
        if meta.get("usage_sec") is not None:
            usage["usage_sec"] = meta["usage_sec"]
        if meta.get("cost_micros") is not None:
            usage["cost_micros"] = meta["cost_micros"]
    return usage


def extract_versions(spec: dict[str, Any], result: Any) -> dict[str, str]:
    meta = result.get("meta") if isinstance(result, dict) else None
    meta = meta if isinstance(meta, dict) else {}
    package = meta.get("package_version") or spec.get("version") or "0.0.0"
    skill_version = spec.get("skill_version") or spec.get("version") or "1.0"
    return {
        "skill_version": str(skill_version),
        "package_version": str(package),
    }


def agent_error(result: Any) -> dict[str, str] | None:
    if not isinstance(result, dict) or not result.get("error"):
        return None
    code = result.get("error")
    if not isinstance(code, str):
        code = "agent_error"
    message = result.get("message")
    if not message:
        message = str(result.get("error"))
    return {"code": code, "message": str(message)}


def error_payload(code: str, message: str, **extra: Any) -> dict[str, Any]:
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    body.update(extra)
    return body


def build_envelope(
    *,
    spec: dict[str, Any],
    request_id: str | None,
    user_input: Any,
    result: Any,
    latency_ms: int,
) -> dict[str, Any]:
    skill = spec.get("skill") or spec["id"]
    return {
        "request_id": request_id,
        "skill": skill,
        "output": extract_output(result),
        "usage": extract_usage(result, latency_ms),
        "versions": extract_versions(spec, result),
        "agent_id": spec["id"],
        "input": user_input,
        "result": result,
    }


def elapsed_ms(started: float) -> int:
    return max(0, int((time.perf_counter() - started) * 1000))
