"""LLM 问句生成 — 自然对话式提问（模板兜底）。"""

from __future__ import annotations

import logging
from typing import Any

from _lib.llm import get_client, is_llm_available

logger = logging.getLogger(__name__)

SYSTEM = """你是用户画像采集助手。根据用户已有信息和待补充项，生成一句自然、口语化的提问。
要求：
1. 只输出 JSON，不要 markdown
2. 一次只问一件事的感觉，但可以把多个缺失项自然串联（不要像表单清单）
3. 若用户之前说过相关内容，可引用（如「你提到在北京…」）
4. 语气亲切简洁，中文"""


def _fallback_batch_question(
    twin: dict,
    missing_labels: list[str],
    *,
    is_followup: bool,
    last_reply: str = "",
) -> tuple[str, str, str]:
    if not missing_labels:
        return ("请简单介绍一下你的基本情况", "随便用一段话描述即可。", "例如：我来自北京，30岁，做前端…")
    phrase = "、".join(missing_labels[:-1]) + f"，以及{missing_labels[-1]}" if len(missing_labels) > 1 else missing_labels[0]
    if is_followup:
        q = f"上次回答里还缺一些信息：{phrase}。方便再补充一句吗？"
    else:
        q = f"为了更好地了解你，能简单说说{phrase}吗？"
    return (q, "随便用一段话描述即可，我会自动整理。", "例如：我来自北京，30岁，未婚，硕士，做前端…")


def compose_batch_question(
    twin: dict,
    collection: dict,
    *,
    missing_fields: list[str],
    missing_labels: list[str],
    template_question: str,
    template_why: str,
    template_hint: str,
    is_followup: bool,
) -> dict[str, str]:
    last_reply = ""
    ledger = collection.get("answered_effective") or {}
    batch_entry = ledger.get("batch_baseline") or {}
    if batch_entry:
        last_reply = batch_entry.get("raw", "")

    if not is_llm_available():
        q, why, hint = _fallback_batch_question(
            twin, missing_labels, is_followup=is_followup, last_reply=last_reply
        )
        return {"question": q, "why": why, "hint": hint}

    client = get_client()
    if client is None:
        q, why, hint = _fallback_batch_question(
            twin, missing_labels, is_followup=is_followup, last_reply=last_reply
        )
        return {"question": q, "why": why, "hint": hint}

    ident = twin.get("identity") or {}
    goal = (twin.get("growth") or {}).get("goal") or ""
    context = {
        "known": {
            "city": ident.get("city"),
            "occupation": ident.get("occupation"),
            "goal": goal,
            "age_range": ident.get("age_range"),
        },
        "missing_fields": missing_fields,
        "missing_labels": missing_labels,
        "is_followup": is_followup,
        "last_reply": last_reply[:200] if last_reply else None,
    }
    prompt = f"""请为「基础画像采集」生成一句提问。

上下文：{context}

模板参考（可改写，勿照搬清单感）：{template_question}

输出 JSON：
{{"question": "...", "why": "...", "hint": "..."}}"""

    try:
        data = client.chat_json(prompt, system=SYSTEM)
        return {
            "question": data.get("question") or template_question,
            "why": data.get("why") or template_why,
            "hint": data.get("hint") or template_hint,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM batch question compose failed: %s", exc)
        q, why, hint = _fallback_batch_question(
            twin, missing_labels, is_followup=is_followup, last_reply=last_reply
        )
        return {"question": q, "why": why, "hint": hint}


def compose_single_question(
    twin: dict,
    collection: dict,
    question: dict[str, Any],
) -> dict[str, Any]:
    """为单题追问润色问句（保留 field/choices 等结构）。"""
    if not question or question.get("field") == "collection.path_confirmed":
        return question

    template_q = question.get("question") or ""
    field = question.get("field") or ""

    if not is_llm_available():
        return question

    client = get_client()
    if client is None:
        return question

    last_inferred = collection.get("inferred_from_last_answer") or []
    prompt = f"""请将下列采集问题改写得更自然，像对话而非问卷。

字段：{field}
模板问题：{template_q}
用户已知画像摘要：goal={(twin.get('growth') or {}).get('goal')}, occupation={(twin.get('identity') or {}).get('occupation')}
上轮自动推断：{last_inferred}

输出 JSON（保留 field 不变，可改 question/why/hint）：
{{"question": "...", "why": "...", "hint": "..."}}"""

    try:
        data = client.chat_json(prompt, system=SYSTEM)
        out = dict(question)
        if data.get("question"):
            out["question"] = data["question"]
        if data.get("why"):
            out["why"] = data["why"]
        if data.get("hint"):
            out["hint"] = data["hint"]
        return out
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM single question compose failed: %s", exc)
        return question


def compose_anchor_question(universal: dict, kind: str) -> dict[str, str]:
    anchors = universal.get("anchors") or {}
    ident = universal.get("identity") or {}
    if kind == "goal":
        if (anchors.get("goal") or "").strip():
            return {
                "question": "你的目标我大概理解了，还想补充或修正一下吗？",
                "why": "确保方向准确，后面会据此规划要问的信息。",
                "hint": "如：通过英语拿海外 offer、赚美元、准备雅思…",
            }
        return {
            "question": "你希望英语主要帮你达成什么目标？",
            "why": "一切路线都从你的真实目标出发，而不是先考英语水平。",
            "hint": "如：海外技术面试、远程接美元单、留学、职场沟通…",
        }
    occ = ident.get("occupation") or ""
    region = ident.get("region_anchor") or ""
    ctx = f"（已知：{occ} {region}）".strip() if occ or region else ""
    return {
        "question": f"说说你现在的状况吧{ctx}：工作、英语水平、时间上有什么限制？",
        "why": "了解「现在」才能判断离目标还差什么；可以分几次慢慢补充。",
        "hint": "如：在国内做前端 3 年，能读文档，口语弱，希望 3 个月内面试…",
    }


def compose_meta_question(
    universal: dict,
    collection: dict,
    meta: dict,
) -> dict[str, str]:
    anchors = universal.get("anchors") or {}
    goal = anchors.get("goal") or ""
    label = meta.get("label") or meta.get("key") or "这项信息"
    why = meta.get("why") or "完善本次学习规划"
    template = {
        "question": f"关于「{label}」，方便说一下吗？",
        "why": why,
        "hint": "用你自己的话回答即可，我会自动整理",
    }
    if not is_llm_available():
        return template
    client = get_client()
    if client is None:
        return template
    try:
        data = client.chat_json(
            f"""生成一句自然提问。
目标：{goal}
现在：{anchors.get('current', '')}
待了解：{label}（{why}）
模板：{template['question']}
输出 JSON：{{"question":"","why":"","hint":""}}""",
            system=SYSTEM,
        )
        return {
            "question": data.get("question") or template["question"],
            "why": data.get("why") or why,
            "hint": data.get("hint") or template["hint"],
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM meta question failed: %s", exc)
        return template
