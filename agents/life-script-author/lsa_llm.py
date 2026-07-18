"""LLM 调用封装。"""

from __future__ import annotations

import logging
from typing import Any

try:
    from _lib.llm import get_client, is_llm_available
except ImportError:

    def is_llm_available() -> bool:  # type: ignore[misc]
        return False

    def get_client():  # type: ignore[misc]
        return None

logger = logging.getLogger(__name__)

_turn_calls: list[dict[str, Any]] = []


def begin_turn() -> None:
    _turn_calls.clear()


def drain_calls() -> list[dict[str, Any]]:
    return list(_turn_calls)


def call_llm_json(
    prompt: str,
    system: str,
    *,
    label: str,
) -> dict[str, Any] | None:
    record: dict[str, Any] = {
        "label": label,
        "system": system[:500] + ("…" if len(system) > 500 else ""),
        "prompt": prompt[:2000] + ("…" if len(prompt) > 2000 else ""),
        "response": None,
        "error": None,
    }

    if not is_llm_available():
        record["error"] = "LLM 不可用"
        _turn_calls.append(record)
        return None

    client = get_client()
    if client is None:
        record["error"] = "client is None"
        _turn_calls.append(record)
        return None

    try:
        data = client.chat_json(prompt, system=system)
        record["response"] = data
        _turn_calls.append(record)
        return data if isinstance(data, dict) else None
    except Exception as exc:  # noqa: BLE001
        record["error"] = str(exc)
        _turn_calls.append(record)
        logger.warning("LLM failed [%s]: %s", label, exc)
        return None
