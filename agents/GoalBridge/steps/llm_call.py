"""LLM 调用封装 — 记录每次调用的输入/输出，供调试与前端展示。"""

from __future__ import annotations

import logging
from typing import Any

from debug_log import gb_log

try:
    from _lib.llm import get_client, is_llm_available
except ImportError:

    def is_llm_available() -> bool:  # type: ignore[misc]
        return False

    def get_client():  # type: ignore[misc]
        return None

logger = logging.getLogger(__name__)

_turn_llm_calls: list[dict[str, Any]] = []


def begin_llm_turn() -> None:
    _turn_llm_calls.clear()


def get_llm_calls() -> list[dict[str, Any]]:
    return list(_turn_llm_calls)


def call_llm(prompt: str, system: str, *, label: str) -> dict | None:
    record: dict[str, Any] = {
        "label": label,
        "system": system,
        "prompt": prompt,
        "response": None,
        "error": None,
    }
    gb_log(f"llm.request [{label}]", system=system, prompt=prompt)

    if not is_llm_available():
        record["error"] = "LLM 不可用"
        _turn_llm_calls.append(record)
        gb_log(f"llm.skip [{label}]", reason=record["error"])
        return None

    client = get_client()
    if client is None:
        record["error"] = "client is None"
        _turn_llm_calls.append(record)
        return None

    try:
        data = client.chat_json(prompt, system=system)
        record["response"] = data
        _turn_llm_calls.append(record)
        gb_log(f"llm.response [{label}]", data=data)
        return data
    except Exception as exc:  # noqa: BLE001
        record["error"] = str(exc)
        _turn_llm_calls.append(record)
        logger.warning("LLM failed [%s]: %s", label, exc)
        gb_log(f"llm.error [{label}]", error=str(exc))
        return None
