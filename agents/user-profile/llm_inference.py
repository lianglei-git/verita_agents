"""PRD v2 — LLM 语义理解（推断 goal/current/identity，无固定关键词表）。"""

from __future__ import annotations

import json
import logging
from typing import Any

from universal_model import merge_current_fragment, merge_universal, snapshot_for_planner

logger = logging.getLogger(__name__)

try:
    from _lib.llm import get_client, is_llm_available
except ImportError:

    def is_llm_available() -> bool:
        return False

    def get_client():
        return None


UNDERSTAND_SYSTEM = """你是用户英语学习需求理解助手。
从自然语言中语义推断用户的真实目标、现状与基础身份信息。
禁止使用关键词表或固定模板；根据语境合理推断。
只输出 JSON，不要 markdown。不要编造用户未提及的事实。"""

UNDERSTAND_PROMPT = """已有状态（可为空）：
{existing}

用户本轮输入：
{text}

回答语境：{target_hint}

请输出 JSON：
{{
  "anchors": {{
    "goal": "学习目标（为何学英语、用来做什么）— 与身份/现状分开描述",
    "current": "现状摘要（身份、水平、时间等）— 不要与 goal 整句重复",
    "goal_clarity": "low|medium|high",
    "current_clarity": "low|medium|high"
  }},
  "identity": {{
    "age_range": "若能从表述推断则填，如「高中生」→「15-18岁」或「高中在读」",
    "occupation": "职业或身份，如「高中生」「前端工程师」",
    "region_anchor": "所在地区，仅当用户提及或可从上下文合理推断",
    "native_language": "母语；用户说「学英语/学习英语」是指学习目标语，母语通常仍为中文，勿填英语",
    "role_anchor": "student|employed|freelancer|career_change|other 等，能推断则填"
  }},
  "capability_snapshot": {{
    "self_assessed_level": "自评英语水平，仅当用户提及",
    "strongest": "",
    "weakest": ""
  }},
  "inferred_paths": ["anchors.goal", "identity.occupation"]
}}

推断原则（语义理解，非关键词匹配）：
1. 一句话兼含身份与目标时须拆分：如「我是高中生，想学英语出国旅游」→ goal 侧重旅游英语；current/identity 侧重高中生身份
2. 「高中生/大学生/职员」等可推断 occupation、role_anchor、age_range（用常见年龄段表述，注明是推断）
3. 「学英语/想要英语」≠ 母语是英语；未提母语且输入为中文时，若可合理推断母语为中文则填「中文」，否则留空待问
4. inferred_paths 列出本轮实际写入的字段路径（含 identity.*）
5. goal/current 必须是用户视角陈述，禁止「用户未明确」「可能为」等分析性措辞；目标不清时 goal_clarity 设为 low"""


META_INFER_SYSTEM = """你是学习路径信息采集助手。
根据用户回答语义判断哪些待采集项可闭合。只输出 JSON，不要编造。"""

META_INFER_PROMPT = """用户目标与现状：
{anchors}

待采集项（仅 status=open）：
{open_metas}

用户回答（针对 {target_key}）：
{text}

输出 JSON：
{{
  "meta_updates": [
    {{"key": "与上表 key 一致", "value": "简洁中文", "status": "inferred", "confidence": 0.85}}
  ]
}}"""

PLAN_SYSTEM = """你是英语学习路径规划器。
根据用户独特目标动态决定还需了解什么。只输出 JSON。"""


def _target_hint(target: str | None) -> str:
    if target == "anchor:goal":
        return "用户正在说明或修正学习目标"
    if target == "anchor:current":
        return "用户正在说明或补充现状"
    if target and target.startswith("universal:"):
        return f"用户正在补充基础信息：{target.split(':', 1)[1]}"
    if target and target.startswith("meta:"):
        return f"用户正在回答 journey 项：{target.split(':', 1)[1]}"
    return "开放输入（故事或综合描述，需拆分 goal/current 并提取 identity）"


def _clean_section(data: dict | None) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {}
    out: dict[str, Any] = {}
    for k, v in data.items():
        if v is None:
            continue
        if isinstance(v, str) and not v.strip():
            continue
        out[k] = v.strip() if isinstance(v, str) else v
    return out


def _apply_llm_result(
    universal: dict[str, Any],
    data: dict[str, Any],
    raw: str,
    *,
    target: str | None,
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    anchors_in = _clean_section(data.get("anchors"))
    patch: dict[str, Any] = {
        "identity": _clean_section(data.get("identity")),
        "capability_snapshot": _clean_section(data.get("capability_snapshot")),
        "anchors": {},
    }

    if target == "anchor:current":
        patch["anchors"]["current"] = anchors_in.get("current") or raw
        if anchors_in.get("goal"):
            patch["anchors"]["goal"] = anchors_in["goal"]
    elif target == "anchor:goal":
        patch["anchors"]["goal"] = anchors_in.get("goal") or raw
        if anchors_in.get("current"):
            patch["anchors"]["current"] = anchors_in["current"]
    else:
        if anchors_in.get("goal"):
            patch["anchors"]["goal"] = anchors_in["goal"]
        elif not (universal.get("anchors") or {}).get("goal"):
            patch["anchors"]["goal"] = raw
        if anchors_in.get("current"):
            patch["anchors"]["current"] = anchors_in["current"]
        elif patch.get("identity"):
            parts = [
                patch["identity"][k]
                for k in ("occupation", "age_range", "region_anchor")
                if patch["identity"].get(k)
            ]
            if parts and not (universal.get("anchors") or {}).get("current"):
                patch["anchors"]["current"] = "；".join(parts)

    for ck in ("goal_clarity", "current_clarity"):
        if anchors_in.get(ck) in ("low", "medium", "high"):
            patch["anchors"][ck] = anchors_in[ck]

    universal = merge_universal(universal, patch)
    if anchors_in.get("goal_clarity") in ("low", "medium", "high"):
        universal.setdefault("anchors", {})["goal_clarity"] = anchors_in["goal_clarity"]
    if anchors_in.get("current_clarity") in ("low", "medium", "high"):
        universal.setdefault("anchors", {})["current_clarity"] = anchors_in["current_clarity"]

    inferred = [str(p) for p in (data.get("inferred_paths") or []) if p]
    return universal, patch, inferred


def understand_user_text(
    universal: dict[str, Any],
    text: str,
    *,
    target: str | None = None,
) -> tuple[dict[str, Any], list[str], str]:
    raw = (text or "").strip()
    if not raw:
        return universal, [], "none"

    if not is_llm_available():
        return _fallback_absorb(universal, raw, target=target)

    client = get_client()
    if client is None:
        return _fallback_absorb(universal, raw, target=target)

    existing = snapshot_for_planner(universal)
    prompt = UNDERSTAND_PROMPT.format(
        existing=json.dumps(existing, ensure_ascii=False),
        text=raw,
        target_hint=_target_hint(target),
    )
    try:
        data = client.chat_json(prompt, system=UNDERSTAND_SYSTEM)
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM understand failed: %s", exc)
        return _fallback_absorb(universal, raw, target=target)

    universal, patch, inferred = _apply_llm_result(universal, data, raw, target=target)
    if not inferred:
        for path in ("anchors.goal", "anchors.current"):
            key = path.split(".")[1]
            if (patch.get("anchors") or {}).get(key) or (universal.get("anchors") or {}).get(key):
                inferred.append(path)
        for k, v in (patch.get("identity") or {}).items():
            if v:
                inferred.append(f"identity.{k}")
    return universal, list(dict.fromkeys(inferred)), "llm"


def _fallback_absorb(
    universal: dict[str, Any],
    raw: str,
    *,
    target: str | None,
) -> tuple[dict[str, Any], list[str], str]:
    """无 LLM：仅保存原文，不硬编码推断 identity。"""
    inferred: list[str] = []
    patch: dict[str, Any] = {"anchors": {}}

    if target == "anchor:goal":
        patch["anchors"]["goal"] = raw
        inferred.append("anchors.goal")
    elif target == "anchor:current":
        universal = merge_current_fragment(universal, raw)
        inferred.append("anchors.current")
    elif target and target.startswith("universal:"):
        field_path = target.split(":", 1)[1]
        section, key = field_path.split(".", 1)
        patch[section] = {key: raw}
        inferred.append(field_path)
    else:
        patch["anchors"]["goal"] = raw
        patch["anchors"]["current"] = raw
        inferred.extend(["anchors.goal", "anchors.current"])

    universal = merge_universal(universal, patch)
    return universal, inferred, "fallback"


def infer_metas_from_answer(
    universal: dict[str, Any],
    collection: dict[str, Any],
    text: str,
    *,
    target_key: str,
) -> list[dict[str, Any]]:
    raw = (text or "").strip()
    if not raw or not is_llm_available():
        return []
    client = get_client()
    if client is None:
        return []

    anchors = universal.get("anchors") or {}
    open_metas = [
        {"key": m.get("key"), "label": m.get("label"), "why": m.get("why"), "priority": m.get("priority")}
        for m in collection.get("journey_meta") or []
        if m.get("status") == "open"
    ]
    if not open_metas:
        return []

    prompt = META_INFER_PROMPT.format(
        anchors=json.dumps({"goal": anchors.get("goal"), "current": anchors.get("current")}, ensure_ascii=False),
        open_metas=json.dumps(open_metas, ensure_ascii=False),
        target_key=target_key,
        text=raw,
    )
    try:
        data = client.chat_json(prompt, system=META_INFER_SYSTEM)
        return [u for u in (data.get("meta_updates") or []) if isinstance(u, dict) and u.get("key")]
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM meta infer failed: %s", exc)
        return []


def plan_journey_via_llm(universal: dict[str, Any]) -> dict[str, Any] | None:
    if not is_llm_available():
        return None
    client = get_client()
    if client is None:
        return None

    prompt = f"""根据用户独特目标与现状，规划 journey 还需了解的信息（3-6 条）与路线草图。

用户状态：
{json.dumps(snapshot_for_planner(universal), ensure_ascii=False)}

要求：
1. journey_meta 须贴合该用户目标（旅游/晋升/考试等各不相同）
2. 能从已有信息推断的项设 status=inferred 并填 value

输出 JSON：
{{
  "distance_summary": "",
  "route_sketch": {{"title": "", "summary": "", "milestones": ["", "", ""]}},
  "journey_meta": [
    {{"key": "snake_case", "label": "", "why": "", "priority": "blocking|important|optional", "value": null, "status": "open"}}
  ]
}}"""
    try:
        return client.chat_json(prompt, system=PLAN_SYSTEM)
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM journey plan failed: %s", exc)
        return None
