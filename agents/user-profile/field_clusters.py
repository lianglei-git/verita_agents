"""字段语义簇 — 答一即满、防重复追问。"""

from __future__ import annotations

import re
from typing import Any

from extract import CITY_COUNTRY, SKILL_SCORE_KEYS, coerce_skill_score

# 语义簇：簇内任一字段有值，整簇视为 satisfied
FIELD_CLUSTERS: dict[str, tuple[str, ...]] = {
    "region": ("identity.region_anchor", "identity.country", "identity.city"),
    "identity_role": ("identity.occupation", "identity.role_anchor"),
    "english_level": (
        "capability.level_band",
        "capability.cefr",
        "capability.listening",
        "capability.speaking",
        "capability.reading",
        "capability.writing",
    ),
    "timeline": ("growth.timeline_urgency", "growth.deadline"),
    "interview_context": ("scenario.interview_type", "scenario.target_market"),
    "exam_context": ("scenario.target_exam", "scenario.target_score_band"),
    "speaking_skill": ("capability.speaking",),
    "listening_skill": ("capability.listening",),
    "reading_skill": ("capability.reading",),
    "writing_skill": ("capability.writing",),
    "bottleneck": ("capability.bottleneck_for_goal",),
}

FIELD_TO_CLUSTER: dict[str, str] = {
    field: cluster
    for cluster, fields in FIELD_CLUSTERS.items()
    for field in fields
}

CONFIDENCE_THRESHOLD = 0.75
MAX_CLUSTER_ASKS = 2

VALID_CEFR = frozenset({"A1", "A2", "B1", "B2", "C1", "C2"})
VALID_LEVEL_BANDS = frozenset(
    {"beginner", "elementary", "intermediate", "upper_intermediate", "advanced"}
)
LEVEL_DECLINED_MARKERS = ("不确定", "不知道", "不清楚", "没测过", "unknown", "不详")
CEFR_PATTERN = re.compile(r"\b(A1|A2|B1|B2|C1|C2)\b", re.I)


def _get_path(obj: dict, path: str) -> Any:
    cur: Any = obj
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _is_filled(val: Any) -> bool:
    if val is None:
        return False
    if isinstance(val, str):
        return bool(val.strip())
    if isinstance(val, (int, float)):
        return True
    if isinstance(val, list):
        return len(val) > 0
    return bool(val)


def region_satisfied(twin: dict) -> bool:
    ident = twin.get("identity") or {}
    if _is_filled(ident.get("region_anchor")) or _is_filled(ident.get("country")):
        return True
    city = (ident.get("city") or "").strip()
    return bool(city and city in CITY_COUNTRY)


def _raw_field_satisfied(twin: dict, field: str) -> bool:
    if field in ("identity.region_anchor", "identity.country"):
        return region_satisfied(twin)
    if field == "identity.city":
        return _is_filled(_get_path(twin, field))
    return _is_filled(_get_path(twin, field))


def cluster_for_field(field: str) -> str | None:
    return FIELD_TO_CLUSTER.get(field)


def cluster_members(cluster: str) -> tuple[str, ...]:
    return FIELD_CLUSTERS.get(cluster, ())


def is_cluster_satisfied(twin: dict, cluster: str) -> bool:
    if cluster == "english_level":
        return english_level_satisfied(twin)
    members = FIELD_CLUSTERS.get(cluster, ())
    if not members:
        return False
    return any(_raw_field_satisfied(twin, f) for f in members)


def english_level_satisfied(twin: dict) -> bool:
    """英语水平簇：CEFR / 档位 / 技能分 / 明确自评或「不确定」均视为已答。"""
    cap = twin.get("capability") or {}
    cefr = (cap.get("cefr") or "").strip().upper()
    band = (cap.get("level_band") or "").strip().lower()

    if cefr in VALID_CEFR:
        return True
    if band in VALID_LEVEL_BANDS:
        return True

    for key in SKILL_SCORE_KEYS:
        if coerce_skill_score(cap.get(key)) is not None:
            return True

    bottleneck = (cap.get("bottleneck_for_goal") or "").strip().lower()
    if bottleneck and bottleneck not in ("unknown", ""):
        return True

    for raw in ((cap.get("cefr") or ""), (cap.get("level_band") or "")):
        text = str(raw).strip()
        if not text:
            continue
        if any(m in text for m in LEVEL_DECLINED_MARKERS):
            return True
        if len(text) >= 3 and text.upper() not in VALID_CEFR and text.lower() not in VALID_LEVEL_BANDS:
            return True

    return False


def extract_cefr_from_text(raw: str) -> str:
    """从自由文本抽出 CEFR 等级。"""
    text = (raw or "").strip()
    if not text:
        return ""
    match = CEFR_PATTERN.search(text)
    if match:
        return match.group(1).upper()
    lower = text.lower()
    cn_map = {
        "入门": "A1",
        "基础": "A2",
        "初级": "A2",
        "中级": "B1",
        "中高级": "B2",
        "高级": "C1",
        "精通": "C2",
        "流利": "C1",
    }
    for k, v in cn_map.items():
        if k in text:
            return v
    if any(m in text for m in LEVEL_DECLINED_MARKERS):
        return "unknown"
    return ""


def assume_english_level_if_exhausted(twin: dict, collection: dict) -> bool:
    """追问次数用尽时，用假设值闭合英语水平簇。"""
    if english_level_satisfied(twin):
        return False
    cap = twin.setdefault("capability", {})
    cap["level_band"] = cap.get("level_band") or "unknown"
    cap["cefr"] = cap.get("cefr") or "unknown"
    assumptions = list(collection.get("assumptions") or [])
    assumptions.append(
        {
            "field": "capability.level_band",
            "value": "unknown",
            "reason": "英语水平多次未能明确，按未知处理并继续",
        }
    )
    collection["assumptions"] = assumptions
    return True


def record_cluster_ask(collection: dict, field: str | None) -> dict:
    if not field:
        return collection
    cluster = cluster_for_field(field) or field
    counts = dict(collection.get("cluster_ask_counts") or {})
    counts[cluster] = int(counts.get(cluster) or 0) + 1
    collection["cluster_ask_counts"] = counts
    return collection


def cluster_ask_exhausted(collection: dict, field: str) -> bool:
    cluster = cluster_for_field(field) or field
    count = int((collection.get("cluster_ask_counts") or {}).get(cluster) or 0)
    return count >= MAX_CLUSTER_ASKS


def is_field_satisfied(twin: dict, field: str) -> bool:
    """字段或所属语义簇已满足。"""
    cluster = cluster_for_field(field)
    if cluster and is_cluster_satisfied(twin, cluster):
        return True
    return _raw_field_satisfied(twin, field)


def normalize_timeline(raw: str) -> str:
    """将「3个月」等口语时间规范为统一档位。"""
    text = (raw or "").strip()
    if not text:
        return ""

    lower = text.lower()
    if any(k in lower for k in ("暂无", "不确定", "没想好", "没有期限", "随时")):
        return "暂无硬性期限"
    if any(k in text for k in ("半年以上", "半年多", "一年以上", "长期")):
        return "半年以上"
    if any(k in text for k in ("1个月内", "一个月内", "尽快", "马上", "紧急")):
        return "1个月内"

    month_match = re.search(r"(\d+)\s*个?\s*月", text)
    if month_match:
        n = int(month_match.group(1))
        if n <= 1:
            return "1个月内"
        if n <= 3:
            return "1-3个月"
        if n <= 6:
            return "3-6个月"
        return "半年以上"

    if re.search(r"1\s*[-–—~到至]\s*3\s*个?月", text):
        return "1-3个月"
    if re.search(r"3\s*[-–—~到至]\s*6\s*个?月", text):
        return "3-6个月"

    year_match = re.search(r"(\d{4})\s*年", text)
    if year_match:
        return year_match.group(0)

    return text


def normalize_field_value(field: str, raw: Any) -> Any:
    if field in ("growth.timeline_urgency", "growth.deadline") and isinstance(raw, str):
        return normalize_timeline(raw) or raw.strip()
    return raw


def prune_path_against_twin(path: dict | None, twin: dict) -> dict:
    """从 path 的 gap 列表中剔除 twin 已满足的字段（含语义簇）。"""
    if not path:
        return {}

    pruned = dict(path)

    def _keep(field: str) -> bool:
        return not is_field_satisfied(twin, field)

    blocking = []
    for gap in pruned.get("blocking_gaps") or []:
        field = gap["field"] if isinstance(gap, dict) else gap
        if _keep(field):
            blocking.append(gap)
    pruned["blocking_gaps"] = blocking
    pruned["blocking_fields"] = [
        g["field"] if isinstance(g, dict) else g for g in blocking
    ]

    optional = []
    for gap in pruned.get("optional_gaps") or []:
        field = gap["field"] if isinstance(gap, dict) else gap
        if _keep(field):
            optional.append(gap)
    pruned["optional_gaps"] = optional

    pruned["required_fields"] = [
        f for f in (pruned.get("required_fields") or []) if _keep(f)
    ]
    return pruned
