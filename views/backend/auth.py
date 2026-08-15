"""内部 token：只拦 POST /api/agents/{id}/run 与 /stream。"""

from __future__ import annotations

import hmac
import os

from flask import jsonify, request

from backend.agents.envelope import error_payload


def auth_disabled() -> bool:
    return os.getenv("AGENT_AUTH_DISABLED", "").strip().lower() in {"1", "true", "yes"}


def expected_token() -> str:
    return (os.getenv("INTERNAL_TOKEN") or os.getenv("AGENT_TOKEN") or "").strip()


def is_protected_agent_call(path: str, method: str) -> bool:
    if (method or "").upper() != "POST":
        return False
    parts = (path or "").rstrip("/").split("/")
    # /api/agents/{id}/run|stream
    if len(parts) < 5:
        return False
    if parts[1] != "api" or parts[2] != "agents":
        return False
    return parts[-1] in {"run", "stream"}


def check_internal_token():
    if not is_protected_agent_call(request.path, request.method):
        return None
    if auth_disabled():
        return None
    token = expected_token()
    if not token:
        return None
    given = (request.headers.get("X-Internal-Token") or "").strip()
    if given and hmac.compare_digest(given, token):
        return None
    return jsonify(
        error_payload(
            "unauthorized",
            "missing or invalid X-Internal-Token",
        )
    ), 401
