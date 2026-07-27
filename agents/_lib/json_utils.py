"""JSON 解析工具（基于 json-repair，容忍 LLM 输出瑕疵）。"""

from __future__ import annotations

import logging
import re
from typing import Any

import json_repair

logger = logging.getLogger(__name__)


def extract_json(text: str) -> dict[str, Any]:
    """从 LLM 回复中解析 JSON，剥离 markdown 代码块并用 json-repair 修复。"""
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"```\s*$", "", text, flags=re.MULTILINE)
    text = text.strip()

    try:
        data = json_repair.loads(text)
        if isinstance(data, dict):
            return data
        raise ValueError(f"expected JSON object, got {type(data).__name__}")
    except Exception as exc:  # noqa: BLE001
        logger.error("JSON parse error: %s\nRaw: %s", exc, text[:300])
        raise
