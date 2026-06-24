"""推断置信度 — 高置信字段自动写入并跳过追问。"""

from __future__ import annotations

import re
from typing import Any

from field_clusters import CONFIDENCE_THRESHOLD, normalize_timeline

# 启发式置信规则：(字段路径, 模式, 置信度)
_HEURISTIC_RULES: list[tuple[str, re.Pattern[str], float]] = [
    ("identity.age_range", re.compile(r"\d{1,2}\s*岁"), 0.92),
    ("growth.timeline_urgency", re.compile(r"\d+\s*个?\s*月"), 0.88),
    ("growth.timeline_urgency", re.compile(r"1\s*[-–—~到至]\s*3\s*个?月"), 0.9),
    ("growth.deadline", re.compile(r"\d{4}\s*年"), 0.85),
    ("identity.education_level", re.compile(r"博士|硕士|本科|大专|高中"), 0.9),
    ("identity.marital_status", re.compile(r"未婚|已婚|离异|单身"), 0.88),
    ("capability.cefr", re.compile(r"\b(A1|A2|B1|B2|C1|C2)\b", re.I), 0.95),
    ("scenario.target_market", re.compile(r"硅谷|美国|欧洲|东南亚|新加坡|加拿大"), 0.82),
    ("scenario.interview_type", re.compile(r"技术面试|行为面|HR面|全英文"), 0.8),
    ("capability.speaking", re.compile(r"口语.{0,6}(\d{1,3})"), 0.85),
    ("capability.listening", re.compile(r"听力.{0,6}(\d{1,3})"), 0.85),
]

_CITY_PATTERN = re.compile(
    r"(北京|上海|深圳|广州|杭州|成都|南京|武汉|西安|重庆|天津|苏州|厦门|青岛|大连|香港|台北)"
)


def score_field_confidence(field: str, text: str, value: Any) -> float:
    """对单字段推断结果打置信分（0–1）。"""
    if value is None or (isinstance(value, str) and not value.strip()):
        return 0.0

    text = (text or "").strip()
    score = 0.55  # 有值即有基础分

    for rule_field, pattern, conf in _HEURISTIC_RULES:
        if rule_field == field and pattern.search(text):
            score = max(score, conf)

    if field.startswith("identity.") and field.endswith(("country", "city", "region_anchor")):
        if _CITY_PATTERN.search(text):
            score = max(score, 0.9)

    if field == "growth.goal" and len(text) >= 4:
        score = max(score, 0.7)

    if field in ("growth.timeline_urgency", "growth.deadline"):
        norm = normalize_timeline(str(value))
        if norm and norm != str(value).strip():
            score = max(score, 0.85)
        elif re.search(r"\d", str(value)):
            score = max(score, 0.8)

    return min(1.0, score)


def score_inferred_fields(
    text: str,
    inferred_paths: list[str],
    twin: dict,
) -> dict[str, float]:
    """为本轮新推断字段批量打分。"""
    scores: dict[str, float] = {}
    for path in inferred_paths:
        parts = path.split(".", 1)
        if len(parts) != 2:
            continue
        section, key = parts
        value = (twin.get(section) or {}).get(key)
        scores[path] = score_field_confidence(path, text, value)
    return scores


def merge_confident_fields(
    collection: dict,
    scores: dict[str, float],
    *,
    threshold: float = CONFIDENCE_THRESHOLD,
) -> list[str]:
    """将高置信字段记入 collection.confident_fields，返回自动采信列表。"""
    store = dict(collection.get("confident_fields") or {})
    auto: list[str] = []
    for field, conf in scores.items():
        if conf >= threshold:
            store[field] = round(conf, 2)
            auto.append(field)
    collection["confident_fields"] = store
    return auto


def is_confidently_known(collection: dict, field: str) -> bool:
    conf = (collection.get("confident_fields") or {}).get(field)
    return conf is not None and float(conf) >= CONFIDENCE_THRESHOLD


def should_skip_asking(collection: dict, field: str, twin: dict, *, field_satisfied_fn) -> bool:
    """高置信或字段/簇已满足 → 不问。"""
    if field_satisfied_fn(twin, field):
        return True
    if is_confidently_known(collection, field):
        return True
    cluster = None
    from field_clusters import cluster_for_field, cluster_members

    cluster = cluster_for_field(field)
    if cluster:
        for member in cluster_members(cluster):
            if is_confidently_known(collection, member):
                return True
    return False
