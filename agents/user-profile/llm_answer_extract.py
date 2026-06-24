"""从单题自由文本回答中推断多字段（LLM 优先）。"""

from __future__ import annotations

import logging
from typing import Any

from _lib.llm import get_client, is_llm_available

from extract import SKILL_SCORE_KEYS, coerce_skill_score

logger = logging.getLogger(__name__)

SYSTEM_FIELD = (
    "你是用户画像抽取助手。请从用户的自由文本回答中提取尽可能多的结构化信息。"
    "只输出 JSON，不要 markdown。只填写能从回答中推断的字段；不要编造。"
)

SYSTEM_FULL = (
    "你是用户画像抽取助手。用户可能只被问到某一个话题，但回答中常包含多项信息。"
    "请从整段回答中提取所有能推断的字段，不要只提取与问题最相关的一项。"
    "只输出 JSON，不要 markdown。不要编造。"
)

PROMPT_FIELD = """用户回答（参考语境：{question_hint}）：
{answer}

已有画像（仅填空，勿覆盖已有非空值）：
{twin_snapshot}

请输出 JSON（字段可省略）：
{{
  "identity": {{
    "name": "", "age_range": "", "country": "", "region_anchor": "",
    "city": "", "native_language": "", "role_anchor": "",
    "occupation": "", "industry": "", "education_level": "", "marital_status": ""
  }},
  "capability": {{
    "cefr": "", "level_band": "", "bottleneck_for_goal": "",
    "listening": null, "speaking": null, "reading": null, "writing": null
  }},
  "growth": {{ "goal": "", "timeline_urgency": "", "deadline": "" }},
  "scenario": {{
    "interview_type": "", "target_market": "", "target_exam": "",
    "target_score_band": "", "work_mode": ""
  }}
}}"""

PROMPT_FULL = """用户本轮完整回答：
{answer}

触发问题字段（仅供参考，勿局限抽取范围）：{field}
问题原文：{question_hint}

已有画像（仅填空）：
{twin_snapshot}

请从整段回答提取所有可推断字段，并给出每项置信度（0-1）。
输出 JSON：
{{
  "patch": {{
    "identity": {{}},
    "capability": {{}},
    "growth": {{}},
    "scenario": {{}}
  }},
  "confidence": {{
    "growth.timeline_urgency": 0.9
  }}
}}"""


def _normalize(data: dict) -> dict[str, Any]:
    growth = data.get("growth") or {}
    scenario = data.get("scenario") or {}
    return {
        "identity": {k: v for k, v in (data.get("identity") or {}).items() if v not in (None, "")},
        "capability": {
            k: coerce_skill_score(v) if k in SKILL_SCORE_KEYS else v
            for k, v in (data.get("capability") or {}).items()
            if v not in (None, "") and not (k in SKILL_SCORE_KEYS and coerce_skill_score(v) is None)
        },
        "growth": {k: v for k, v in growth.items() if v not in (None, "") and k != "completed_milestones"},
        "scenario": {
            k: v
            for k, v in scenario.items()
            if v not in (None, "") and k != "next_scenarios"
        },
    }


def try_llm_enrich_answer(
    field: str,
    answer: str,
    twin: dict,
    question_hint: str = "",
) -> dict[str, Any] | None:
    if not answer.strip() or not is_llm_available():
        return None
    client = get_client()
    if client is None:
        return None

    snapshot = {
        "identity": twin.get("identity"),
        "capability": {k: v for k, v in (twin.get("capability") or {}).items() if k != "labels"},
        "growth": twin.get("growth"),
        "scenario": twin.get("scenario"),
    }
    try:
        data = client.chat_json(
            PROMPT_FIELD.format(
                question_hint=question_hint or field,
                answer=answer,
                twin_snapshot=snapshot,
            ),
            system=SYSTEM_FIELD,
        )
        return _normalize(data)
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM answer enrich failed: %s", exc)
        return None


def try_llm_enrich_full_answer(
    answer: str,
    twin: dict,
    *,
    context_field: str = "",
    question_hint: str = "",
) -> tuple[dict[str, Any] | None, dict[str, float]]:
    """全量推断：从整句抽取多字段 + 置信度。"""
    if not answer.strip() or not is_llm_available():
        return None, {}
    client = get_client()
    if client is None:
        return None, {}

    snapshot = {
        "identity": twin.get("identity"),
        "capability": {k: v for k, v in (twin.get("capability") or {}).items() if k != "labels"},
        "growth": twin.get("growth"),
        "scenario": twin.get("scenario"),
    }
    try:
        data = client.chat_json(
            PROMPT_FULL.format(
                answer=answer,
                field=context_field or "开放回答",
                question_hint=question_hint or context_field,
                twin_snapshot=snapshot,
            ),
            system=SYSTEM_FULL,
        )
        patch = _normalize(data.get("patch") or data)
        conf_raw = data.get("confidence") or {}
        confidence = {k: float(v) for k, v in conf_raw.items() if v is not None}
        return patch, confidence
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM full enrich failed: %s", exc)
        return None, {}
