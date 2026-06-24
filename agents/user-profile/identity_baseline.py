"""PRD v2 — 基础身份字段：须推断或问清后方可放行（无硬编码推断）。"""

from __future__ import annotations

from typing import Any

# (section, key, 中文标签)
BASELINE_IDENTITY: list[tuple[str, str, str]] = [
    ("identity", "age_range", "年龄或年龄段"),
    ("identity", "occupation", "职业/在读身份"),
    ("identity", "region_anchor", "所在地区"),
    ("identity", "native_language", "母语"),
]

FIELD_PATH_LABELS: dict[str, tuple[str, str]] = {
    "identity.age_range": ("你大概多大，或处于哪个年龄段？", "如 16-18 岁、高中在读"),
    "identity.occupation": ("你的职业或身份是？", "如高中生、公司职员、工程师"),
    "identity.region_anchor": ("你主要在哪个地区？", "如北京、上海、广州"),
    "identity.native_language": ("你的母语是什么？", "如中文、日语；注意：想学英语不等于母语是英语"),
    "identity.role_anchor": ("你目前属于哪种身份？", "如 student、employed、freelancer"),
}


def _filled(val: Any) -> bool:
    if val is None:
        return False
    if isinstance(val, str):
        return bool(val.strip())
    return bool(val)


def missing_baseline_fields(universal: dict[str, Any]) -> list[str]:
    """返回尚未填充的 baseline 字段路径，如 identity.age_range。"""
    ident = universal.get("identity") or {}
    missing: list[str] = []
    for _section, key, _label in BASELINE_IDENTITY:
        if not _filled(ident.get(key)):
            missing.append(f"identity.{key}")
    return missing


def baseline_ready(universal: dict[str, Any]) -> bool:
    return len(missing_baseline_fields(universal)) == 0
