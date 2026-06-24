"""LLM 驱动的路径推断与单题追问规划（无路径模板）。"""

from __future__ import annotations

import logging
from typing import Any

from _lib.llm import get_client, is_llm_available

from collection import (
    MAX_QUESTIONS,
    baseline_missing,
    baseline_question_for,
    is_baseline_complete,
)
from field_clusters import prune_path_against_twin
from planner_guard import should_ask_field

logger = logging.getLogger(__name__)

SYSTEM = """你是 Digital Twin 用户画像采集规划器。
根据用户目标，自主推断个性化学习路径（不要使用预设模板名称），并决定下一步要问什么。
规则：
1. 每次只输出 1 个 next_question
2. 由浅入深：depth 1=锚点事实, 2=路径确认, 3=瓶颈, 4=场景, 5=校准
3. 用户最多回答 25 个问题（story 不计数）
4. Baseline 未完成时优先补 Baseline
5. path 由你根据 goal 自主生成，包含 title/summary/milestones/required_fields
6. 只输出 JSON，不要 markdown
7. **禁止重复追问**：twin 中已有值的字段、或已从回答推断出的字段（如已有 city=北京 则勿再问 country/city）
8. 用户可能在一句回答里提供多个信息，规划下一题前请基于 twin 完整状态跳过已满足字段
9. 若 baseline_missing 为空，不要出 baseline 题"""


def _planner_prompt(twin: dict, collection: dict) -> str:
    count = int(collection.get("question_count") or 0)
    asked = collection.get("asked_fields") or []
    path = collection.get("path")

    return f"""当前数字孪生状态：
{{
  "twin": {twin},
  "question_count": {count},
  "budget_remaining": {MAX_QUESTIONS - count},
  "asked_fields": {asked},
  "baseline_complete": {is_baseline_complete(twin)},
  "baseline_missing": {baseline_missing(twin)},
  "current_path": {path},
  "path_confirmed": {collection.get("path_confirmed", False)}
}}

请输出 JSON：
{{
  "path": {{
    "title": "自主生成的路径标题",
    "summary": "2-3 句路径说明",
    "interpretation": "对用户目标的理解",
    "milestones": ["阶段1", "阶段2", "阶段3"],
    "confidence": 0.0,
    "required_fields": ["dot.path.field", "..."],
    "blocking_gaps": [{{"field": "dot.path", "reason": "为何 blocking"}}],
    "optional_gaps": [{{"field": "dot.path", "reason": "可选"}}]
  }},
  "next_question": {{
    "field": "dot.path",
    "question": "只问一个问题",
    "hint": "简短提示",
    "why": "为什么现在问这个",
    "depth": 1,
    "phase": "baseline|path_confirm|path_blocking|scenario|calibration",
    "skippable": false,
    "choices": ["选项A", "选项B"]
  }},
  "path_confirm_needed": false,
  "assumptions": [{{"field": "...", "value": "...", "reason": "..."}}],
  "release_recommendation": "continue|early|conditional"
}}

若 baseline 未完成，next_question 必须针对 baseline_missing 中尚未 asked 的字段。
若需用户确认路径，设置 path_confirm_needed=true，next_question 为路径确认题（depth=2）。
不要重复 asked_fields 中的字段，除非用户上次未有效回答。"""


def _normalize_path(path_data: dict | None) -> dict[str, Any]:
    if not path_data:
        return {}
    blocking = path_data.get("blocking_gaps") or []
    blocking_fields = [
        g["field"] if isinstance(g, dict) else g
        for g in blocking
    ]
    required = list(path_data.get("required_fields") or [])
    return {
        "title": path_data.get("title") or "个性化学习路径",
        "summary": path_data.get("summary") or "",
        "interpretation": path_data.get("interpretation") or "",
        "milestones": path_data.get("milestones") or [],
        "confidence": float(path_data.get("confidence") or 0.5),
        "required_fields": required,
        "blocking_gaps": blocking,
        "blocking_fields": blocking_fields,
        "optional_gaps": path_data.get("optional_gaps") or [],
    }


def _normalize_question(q: dict | None) -> dict[str, Any] | None:
    if not q or not q.get("field"):
        return None
    return {
        "field": q["field"],
        "question": q.get("question") or f"请补充 {q['field']}",
        "hint": q.get("hint") or "",
        "why": q.get("why") or "",
        "depth": int(q.get("depth") or 1),
        "phase": q.get("phase") or "path_blocking",
        "skippable": bool(q.get("skippable", False)),
        "choices": q.get("choices") or [],
    }


def plan_with_llm(twin: dict, collection: dict) -> dict[str, Any] | None:
    if not is_llm_available():
        return None

    client = get_client()
    if client is None:
        return None

    try:
        data = client.chat_json(_planner_prompt(twin, collection), system=SYSTEM)
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM planner failed: %s", exc)
        return None

    path = _normalize_path(data.get("path"))
    path = prune_path_against_twin(path, twin)
    question = _normalize_question(data.get("next_question"))

    if not question and not is_baseline_complete(twin):
        for field in baseline_missing(twin):
            if should_ask_field(twin, collection, field):
                question = baseline_question_for(field)
                break

    blocking_fields = path.get("blocking_fields") or []

    return {
        "path": path,
        "next_question": question,
        "path_confirm_needed": bool(data.get("path_confirm_needed")),
        "assumptions": data.get("assumptions") or [],
        "release_recommendation": data.get("release_recommendation") or "continue",
        "blocking_fields": blocking_fields,
        "source": "llm",
    }
