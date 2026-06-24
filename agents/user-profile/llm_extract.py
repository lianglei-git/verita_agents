"""使用 LLM 从个人故事抽取 Digital Twin 字段（含 Baseline 锚点）。"""

from __future__ import annotations

import logging
from typing import Any

from _lib.llm import get_client, is_llm_available

logger = logging.getLogger(__name__)

SYSTEM = (
    "你是用户画像抽取助手。根据用户的个人故事，提取结构化 JSON。"
    "只输出一个 JSON 对象，不要 markdown。缺失字段用空字符串或 null。"
)

PROMPT_TEMPLATE = """从以下个人故事中抽取用户画像字段。

故事：
{story}

请输出 JSON，结构如下（字段名必须一致）：
{{
  "identity": {{
    "name": "",
    "age_range": "",
    "country": "",
    "region_anchor": "",
    "city": "",
    "native_language": "",
    "role_anchor": "employed|student|freelancer|career_change|other",
    "occupation": "",
    "industry": "",
    "education_level": "",
    "marital_status": "",
    "timezone": ""
  }},
  "capability": {{
    "cefr": "",
    "level_band": "beginner|elementary|intermediate|upper_intermediate|advanced",
    "bottleneck_for_goal": "listening|speaking|reading|writing|general|unknown",
    "listening": null,
    "speaking": null,
    "reading": null,
    "writing": null
  }},
  "growth": {{
    "goal": "",
    "current_stage": "",
    "timeline_urgency": "",
    "deadline": ""
  }},
  "scenario": {{
    "primary_track": "",
    "current_scenario": "",
    "interview_type": "",
    "target_market": "",
    "target_exam": "",
    "target_score_band": "",
    "work_mode": ""
  }}
}}
"""


def try_llm_extract(story: str) -> dict[str, Any] | None:
    """LLM 抽取；不可用或失败时返回 None，由调用方回退启发式。"""
    if not story.strip() or not is_llm_available():
        return None

    client = get_client()
    if client is None:
        return None

    try:
        data = client.chat_json(PROMPT_TEMPLATE.format(story=story), system=SYSTEM)
        return _normalize_extract(data)
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM story extract failed, fallback to heuristics: %s", exc)
        return None


def _normalize_extract(data: dict) -> dict[str, Any]:
    """对齐 extract_from_story 的输出结构。"""
    growth = data.get("growth") or {}
    scenario = data.get("scenario") or {}
    return {
        "identity": {**(data.get("identity") or {})},
        "capability": {**(data.get("capability") or {})},
        "growth": {
            "goal": growth.get("goal", ""),
            "current_stage": growth.get("current_stage", ""),
            "timeline_urgency": growth.get("timeline_urgency", ""),
            "deadline": growth.get("deadline", ""),
            "completed_milestones": [],
        },
        "scenario": {
            "primary_track": scenario.get("primary_track", ""),
            "current_scenario": scenario.get("current_scenario", ""),
            "interview_type": scenario.get("interview_type", ""),
            "target_market": scenario.get("target_market", ""),
            "target_exam": scenario.get("target_exam", ""),
            "target_score_band": scenario.get("target_score_band", ""),
            "work_mode": scenario.get("work_mode", ""),
            "next_scenarios": [],
        },
    }
