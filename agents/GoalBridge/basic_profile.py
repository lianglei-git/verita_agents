"""基础画像 — JSON 配置加载与合并进 user_profile（不调 LLM）。"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from contract import normalize_questions
from user_profile import get_user_profile, set_user_profile

_SCHEMA_PATH = Path(__file__).resolve().parent / "config" / "basic_profile.schema.json"


@lru_cache(maxsize=1)
def load_basic_profile_schema() -> dict[str, Any]:
    with _SCHEMA_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return {"title": "基础信息", "description": "", "fields": []}
    fields = data.get("fields")
    if not isinstance(fields, list):
        data["fields"] = []
    return data


def get_schema_for_client() -> dict[str, Any]:
    return load_basic_profile_schema()


def schema_fields(schema: dict | None = None) -> list[dict[str, Any]]:
    raw = schema or load_basic_profile_schema()
    return [f for f in (raw.get("fields") or []) if isinstance(f, dict)]


def schema_to_questions(schema: dict | None = None) -> list[dict[str, Any]]:
    """将 schema 字段转为与问卷一致的题目结构（text 使用中文 label）。"""
    out: list[dict] = []
    for field in schema_fields(schema):
        fid = str(field.get("id") or "").strip()
        label = str(field.get("label") or fid).strip()
        if not fid or not label:
            continue
        qtype = str(field.get("type") or "open").strip()
        options = field.get("options") or []
        if qtype in ("single", "multi") and isinstance(options, list) and options:
            opt_objs = [
                {"id": f"opt_{i}", "label": str(o).strip()}
                for i, o in enumerate(options)
                if str(o).strip()
            ]
        else:
            qtype = "open"
            opt_objs = []
        out.append({
            "id": fid,
            "step": 2,
            "type": qtype,
            "text": label,
            "options": opt_objs,
            "required": bool(field.get("required", False)),
        })
    return normalize_questions(out)


def _display_value(field: dict, stored: dict) -> str:
    val = stored.get("value")
    qtype = str(field.get("type") or "open")
    options = field.get("options") or []
    opt_labels = {f"opt_{i}": str(o).strip() for i, o in enumerate(options) if str(o).strip()}

    if qtype == "multi" and isinstance(val, list):
        parts = [opt_labels.get(v, str(v)) for v in val if str(v).strip()]
        return "、".join(parts)
    if qtype == "single" and isinstance(val, str):
        return opt_labels.get(val, val)
    return str(val or "").strip()


def answers_to_structured(
    answers: dict[str, dict],
    schema: dict | None = None,
) -> dict[str, str]:
    """field_id → 存储值 转为 中文 label → 展示文本。"""
    by_id = {str(f.get("id")): f for f in schema_fields(schema) if f.get("id")}
    structured: dict[str, str] = {}
    for fid, stored in answers.items():
        field = by_id.get(str(fid))
        if not field or not isinstance(stored, dict):
            continue
        label = str(field.get("label") or fid).strip()
        text = _display_value(field, stored)
        if label and text:
            structured[label] = text
    return structured


def merge_basic_profile(session: dict, structured: dict[str, str]) -> dict:
    """将基础画像（中文键）并入 user_profile，不调用 LLM。"""
    if not structured:
        return session

    profile = get_user_profile(session)
    merged_structured = {**(profile.get("structured") or {}), **structured}
    profile["structured"] = merged_structured

    line = "；".join(f"{k}：{v}" for k, v in structured.items())
    prev = str(profile.get("summary") or "").strip()
    if line and line not in prev:
        profile["summary"] = f"{prev}\n{line}".strip() if prev else line

    log = list(profile.get("qa_log") or [])
    log.append({
        "step": 2,
        "items": [{"question": k, "answer": v} for k, v in structured.items()],
    })
    profile["qa_log"] = log[-40:]

    return set_user_profile(session, **profile)
