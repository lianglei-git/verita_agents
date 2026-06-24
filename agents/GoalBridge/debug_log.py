"""GoalBridge 控制台调试日志 — 前后端统一前缀 [GoalBridge]。"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

_LOG = logging.getLogger("goal_bridge")

_CONFIGURED = False


def _ensure_configured() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True
    level = logging.DEBUG if os.getenv("GOALBRIDGE_DEBUG", "1").lower() not in ("0", "false", "no") else logging.INFO
    _LOG.setLevel(level)
    if not _LOG.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("[GoalBridge] %(message)s"))
        _LOG.addHandler(handler)
    _LOG.propagate = False


def _safe_json(data: Any, limit: int = 4000) -> str:
    try:
        text = json.dumps(data, ensure_ascii=False, indent=2, default=str)
    except (TypeError, ValueError):
        text = repr(data)
    if len(text) > limit:
        return text[:limit] + f"\n…（截断，共 {len(text)} 字符）"
    return text


def gb_log(phase: str, **fields: Any) -> None:
    """结构化打印到 stderr/终端。"""
    _ensure_configured()
    lines = [f"── {phase} ──"]
    for key, val in fields.items():
        if val is None:
            continue
        if isinstance(val, (dict, list)):
            lines.append(f"{key}:\n{_safe_json(val)}")
        else:
            lines.append(f"{key}: {val}")
    _LOG.info("\n".join(lines))
