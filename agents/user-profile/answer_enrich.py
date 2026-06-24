"""从用户回答中智能推断多字段（全量理解，避免重复追问）。"""

from __future__ import annotations

from typing import Any

from extract import (
    extract_from_story,
    infer_geography,
    merge_twin_fill_empty,
)
from field_clusters import normalize_field_value
from inference_confidence import merge_confident_fields, score_inferred_fields
from llm_answer_extract import try_llm_enrich_answer, try_llm_enrich_full_answer

FIELD_QUESTION_HINT: dict[str, str] = {
    "identity.region_anchor": "你目前主要在哪个国家或地区？",
    "identity.country": "你来自哪个国家？",
    "identity.city": "你所在的城市是？",
    "identity.native_language": "你的母语是什么？",
    "identity.occupation": "你的职业或专业方向是什么？",
    "identity.role_anchor": "你现在的身份是什么？",
    "identity.education_level": "你的学历是？",
    "growth.goal": "你的学习目标是什么？",
    "growth.timeline_urgency": "你大概什么时候需要用到英语达成目标？",
    "growth.deadline": "截止日期或目标时间是什么时候？",
    "scenario.target_market": "你的目标市场或地区是哪里？",
    "scenario.interview_type": "你准备的面试更偏哪一类？",
    "capability.speaking": "口语自评",
    "batch_baseline": (
        "请简单介绍：来自哪里、年龄、婚姻状况、学历、职业、母语、英语学习目标、英语水平"
    ),
}


def fix_misassigned_geography(twin: dict) -> list[str]:
    """纠正 geography 误填（城市写入 country、长句回答等）。"""
    from extract import CITY_COUNTRY

    fixed: list[str] = []
    ident = twin.get("identity") or {}
    country = (ident.get("country") or "").strip()
    region = (ident.get("region_anchor") or "").strip()

    if country in CITY_COUNTRY:
        twin["identity"]["city"] = country
        twin["identity"]["country"] = CITY_COUNTRY[country]
        twin["identity"]["region_anchor"] = CITY_COUNTRY[country]
        fixed.extend(["identity.city", "identity.country", "identity.region_anchor"])

    for text in (country, region):
        if len(text) > 8:
            geo = infer_geography(text)
            if geo and geo.get("identity"):
                for key, val in geo["identity"].items():
                    if val and (
                        not ident.get(key)
                        or ident.get(key) == text
                        or key in ("country", "region_anchor", "city")
                    ):
                        twin["identity"][key] = val
                        fixed.append(f"identity.{key}")
    return fixed


def _patch_new_fields(twin_before: dict, twin_after: dict) -> list[str]:
    new_fields: list[str] = []

    def walk(before: Any, after: Any, prefix: str) -> None:
        if isinstance(after, dict) and isinstance(before, dict):
            for k, v in after.items():
                path = f"{prefix}.{k}" if prefix else k
                b = before.get(k)
                if isinstance(v, dict):
                    walk(b or {}, v, path)
                elif _was_empty(b) and not _was_empty(v):
                    new_fields.append(path)
        elif _was_empty(before) and not _was_empty(after):
            new_fields.append(prefix)

    for section in ("identity", "capability", "growth", "scenario"):
        before_sec = twin_before.get(section) or {}
        after_sec = twin_after.get(section) or {}
        if section == "capability":
            before_sec = {k: v for k, v in before_sec.items() if k != "labels"}
            after_sec = {k: v for k, v in after_sec.items() if k != "labels"}
        walk(before_sec, after_sec, section)
    return new_fields


def _was_empty(val: Any) -> bool:
    if val is None:
        return True
    if isinstance(val, str):
        return not val.strip()
    return False


def _apply_normalized_patch(twin: dict, patch: dict) -> dict:
    """合并 patch 并对时间等字段规范化。"""
    for section, data in patch.items():
        if not isinstance(data, dict):
            continue
        for key, val in data.items():
            if val is None or val == "":
                continue
            path = f"{section}.{key}"
            val = normalize_field_value(path, val)
            twin = merge_twin_fill_empty(twin, {section: {key: val}})
    return twin


def enrich_from_replies(
    twin: dict,
    answers: dict[str, Any],
    collection: dict | None = None,
) -> tuple[dict, list[str], str, dict[str, float]]:
    """
    从本轮回答全量推断多字段（仅填空不覆盖）。
    返回 (twin, 新推断字段列表, method, confidence_scores)。
    """
    all_inferred: list[str] = []
    methods: list[str] = []
    all_confidence: dict[str, float] = {}

    texts: list[str] = []
    primary_field = ""
    for field, raw in answers.items():
        if field.startswith("_") or field == "collection.path_confirmed":
            continue
        text = str(raw).strip() if raw is not None else ""
        if text:
            texts.append(text)
            if not primary_field:
                primary_field = field

    if not texts:
        return twin, [], "none", {}

    combined = " ".join(texts)
    before = _snapshot(twin)

    geo = infer_geography(combined)
    if geo:
        twin = merge_twin_fill_empty(twin, geo)
        methods.append("geo")

    extracted = extract_from_story(combined)
    twin = _apply_normalized_patch(twin, extracted)
    methods.append("heuristic")

    hint = FIELD_QUESTION_HINT.get(primary_field, primary_field)
    llm_patch, llm_conf = try_llm_enrich_full_answer(
        combined,
        twin,
        context_field=primary_field,
        question_hint=hint,
    )
    if llm_patch:
        twin = _apply_normalized_patch(twin, llm_patch)
        methods.append("llm_full")
        all_confidence.update(llm_conf)
    else:
        llm_patch = try_llm_enrich_answer(primary_field, combined, twin, question_hint=hint)
        if llm_patch:
            twin = _apply_normalized_patch(twin, llm_patch)
            methods.append("llm")

    geo_fix = fix_misassigned_geography(twin)
    all_inferred.extend(_patch_new_fields(before, twin))
    all_inferred.extend(geo_fix)

    heuristic_scores = score_inferred_fields(combined, all_inferred, twin)
    for path, score in heuristic_scores.items():
        all_confidence[path] = max(all_confidence.get(path, 0), score)

    if collection is not None:
        merge_confident_fields(collection, all_confidence)

    seen: set[str] = set()
    deduped: list[str] = []
    for f in all_inferred:
        if f not in seen:
            seen.add(f)
            deduped.append(f)

    method = "+".join(dict.fromkeys(methods)) if methods else "none"
    return twin, deduped, method, all_confidence


def _snapshot(twin: dict) -> dict:
    import copy

    return copy.deepcopy(
        {
            "identity": twin.get("identity") or {},
            "capability": {k: v for k, v in (twin.get("capability") or {}).items() if k != "labels"},
            "growth": twin.get("growth") or {},
            "scenario": twin.get("scenario") or {},
        }
    )
