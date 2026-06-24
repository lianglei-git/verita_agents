"""JSON 解析工具。"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def extract_json(text: str) -> dict[str, Any]:
    """从 LLM 回复中解析 JSON，剥离 markdown 代码块。"""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"```\s*$", "", text, flags=re.MULTILINE)
    text = text.strip()

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]

    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
        raise ValueError("expected JSON object")
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error("JSON parse error: %s\nRaw: %s", exc, text[:300])
        raise
