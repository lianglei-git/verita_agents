"""基础画像批量采集 — 一次自然提问，从自由回答中推断。"""

from __future__ import annotations

from typing import Any

from collection import field_is_satisfied, region_satisfied
from question_composer import compose_batch_question

# 批量基础信息字段（面向用户的「基本情况」）
BATCH_PROFILE_SPECS: list[dict[str, Any]] = [
    {
        "field": "identity.region_anchor",
        "label": "来自哪里",
        "ask": "你来自哪里",
        "hint": "国家或城市，如北京、上海、新加坡",
        "alternates": ["identity.country", "identity.city"],
        "required": True,
    },
    {
        "field": "identity.age_range",
        "label": "年龄",
        "ask": "年龄多大",
        "hint": "如 28 岁，或 25-34",
        "required": True,
    },
    {
        "field": "identity.marital_status",
        "label": "婚姻状况",
        "ask": "婚姻状况",
        "hint": "未婚 / 已婚 / 离异 / 其他",
        "required": False,
    },
    {
        "field": "identity.education_level",
        "label": "学历",
        "ask": "最高学历",
        "hint": "如高中、本科、硕士、博士",
        "required": False,
    },
    {
        "field": "identity.occupation",
        "label": "职业或身份",
        "ask": "现在的职业或身份",
        "hint": "如前端工程师、大三学生、自由职业",
        "alternates": ["identity.role_anchor"],
        "required": True,
    },
    {
        "field": "identity.native_language",
        "label": "母语",
        "ask": "母语是什么",
        "hint": "如中文、英语",
        "required": True,
    },
    {
        "field": "growth.goal",
        "label": "学习目标",
        "ask": "希望通过英语达成什么目标",
        "hint": "如海外面试、留学、职场沟通",
        "required": True,
    },
    {
        "field": "capability.level_band",
        "label": "英语水平",
        "ask": "整体英语水平如何",
        "hint": "基础 / 中级 / 高级，或 A1–C2",
        "alternates": ["capability.cefr"],
        "required": False,
    },
]

BATCH_FIELD = "batch_baseline"


def _spec_satisfied(twin: dict, spec: dict[str, Any]) -> bool:
    field = spec["field"]
    if field in ("identity.region_anchor", "identity.country"):
        return region_satisfied(twin)
    if field_is_satisfied(twin, field):
        return True
    for alt in spec.get("alternates") or []:
        if alt in ("identity.region_anchor", "identity.country"):
            if region_satisfied(twin):
                return True
        elif field_is_satisfied(twin, alt):
            return True
    return False


def profile_basics_missing(twin: dict, collection: dict | None = None) -> list[str]:
    """尚未满足的基础画像字段。"""
    missing: list[str] = []
    for spec in BATCH_PROFILE_SPECS:
        if collection:
            from inference_confidence import is_confidently_known

            if is_confidently_known(collection, spec["field"]):
                continue
        if not _spec_satisfied(twin, spec):
            missing.append(spec["field"])
    return missing


def needs_batch_baseline(twin: dict, collection: dict) -> bool:
    """是否仍处于基础画像批量采集阶段。"""
    if collection.get("batch_baseline_done"):
        return False
    missing = profile_basics_missing(twin, collection)
    required_missing = [
        s["field"]
        for s in BATCH_PROFILE_SPECS
        if s.get("required") and s["field"] in missing
    ]
    return len(required_missing) >= 1


def _missing_specs(twin: dict, collection: dict | None = None) -> list[dict[str, Any]]:
    missing_set = set(profile_basics_missing(twin, collection))
    return [s for s in BATCH_PROFILE_SPECS if s["field"] in missing_set]


def _compose_ask_phrase(specs: list[dict[str, Any]]) -> str:
    """将缺失项拼成一句自然提问。"""
    if not specs:
        return "请简单介绍一下你的基本情况"
    parts = [s["ask"] for s in specs]
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]}，{parts[1]}"
    return "、".join(parts[:-1]) + f"，以及{parts[-1]}"


def build_batch_question(twin: dict, collection: dict) -> dict[str, Any]:
    """构建单条批量基础提问（用户一段话回答，系统推断）。"""
    specs = _missing_specs(twin, collection)
    missing_fields = [s["field"] for s in specs]
    missing_labels = [s["label"] for s in specs]
    asked = set(collection.get("asked_fields") or [])
    is_followup = BATCH_FIELD in asked

    if is_followup:
        template_q = f"上次回答里还缺一些信息：{_compose_ask_phrase(specs)}。方便再补充一句吗？"
        template_why = "我会根据补充内容继续自动整理，不必逐项填写。"
    else:
        template_q = f"为了更好地了解你，请简单介绍一下：{_compose_ask_phrase(specs)}？"
        template_why = "随便用一段话描述即可，我会自动整理你的基础画像。"

    template_hint = "例如：我来自北京，30岁，未婚，硕士，做前端，母语中文，想准备海外技术面试"

    composed = compose_batch_question(
        twin,
        collection,
        missing_fields=missing_fields,
        missing_labels=missing_labels,
        template_question=template_q,
        template_why=template_why,
        template_hint=template_hint,
        is_followup=is_followup,
    )

    return {
        "field": BATCH_FIELD,
        "question": composed["question"],
        "hint": composed["hint"],
        "why": composed["why"],
        "depth": 1,
        "phase": "baseline",
        "skippable": False,
        "missing_fields": missing_fields,
        "missing_count": len(specs),
    }


def mark_batch_done(collection: dict) -> dict:
    collection["batch_baseline_done"] = True
    collection["mode"] = "single"
    return collection
