"""用户画像 — 每轮作答提交给 AI 之前合并，AI 返回后再精炼。"""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any


def empty_user_profile() -> dict[str, Any]:
    return {
        "summary": "",
        "structured": {},
        "qa_log": [],
    }


def normalize_user_profile(raw: dict | None) -> dict[str, Any]:
    base = empty_user_profile()
    if not raw:
        return base
    base["summary"] = str(raw.get("summary") or "").strip()
    structured = raw.get("structured")
    base["structured"] = dict(structured) if isinstance(structured, dict) else {}
    log = raw.get("qa_log")
    base["qa_log"] = list(log) if isinstance(log, list) else []
    return base


def get_user_profile(session: dict) -> dict[str, Any]:
    return normalize_user_profile(session.get("user_profile"))


def set_user_profile(session: dict, **patch: Any) -> dict:
    out = deepcopy(session)
    profile = get_user_profile(out)
    for key, val in patch.items():
        if key in profile:
            profile[key] = val
    out["user_profile"] = profile
    return out


def merge_round_before_ai(
    session: dict,
    *,
    step: int,
    items: list[dict[str, str]],
) -> dict:
    """用户答毕、调用 AI 之前：把本轮问答并入画像（qa_log + structured + summary 草稿）。"""
    if not items:
        return session

    profile = get_user_profile(session)
    log = list(profile.get("qa_log") or [])
    log.append({"step": step, "items": [dict(i) for i in items]})
    profile["qa_log"] = log[-40:]

    structured = dict(profile.get("structured") or {})
    summary_lines: list[str] = []
    for item in items:
        q = str(item.get("question") or "").strip()
        a = str(item.get("answer") or "").strip()
        if not q or not a:
            continue
        structured[q] = a
        summary_lines.append(f"{q}：{a}")

    profile["structured"] = structured
    if summary_lines:
        round_text = "；".join(summary_lines)
        prev = str(profile.get("summary") or "").strip()
        if round_text not in prev:
            profile["summary"] = f"{prev}\n{round_text}".strip() if prev else round_text

    return set_user_profile(session, **profile)


def merge_profile_from_llm(session: dict, data: dict) -> dict:
    """AI 返回后：用 profile_summary / profile_facts 精炼画像（覆盖 summary，合并 structured）。"""
    profile = get_user_profile(session)
    summary = (
        data.get("profile_summary")
        or data.get("user_profile_summary")
        or data.get("profile_update")
        or ""
    )
    if isinstance(summary, str) and summary.strip():
        profile["summary"] = summary.strip()

    facts = (
        data.get("profile_facts")
        or data.get("accumulated_facts")
        or data.get("collected_info")
    )
    if isinstance(facts, dict) and facts:
        profile["structured"] = {**profile.get("structured", {}), **facts}

    return set_user_profile(session, **profile)


def profile_for_prompt(session: dict) -> str:
    """注入 Prompt 的「提交前已合并画像」。"""
    profile = get_user_profile(session)
    parts: list[str] = []
    if profile.get("summary"):
        parts.append(profile["summary"])
    structured = profile.get("structured") or {}
    if structured:
        parts.append(json.dumps(structured, ensure_ascii=False, indent=2))
    return "\n".join(parts).strip() or "（尚无）"


def format_round_user_line(bundle: str) -> str:
    if not bundle.strip():
        return "（本轮无作答）"
    return "本轮回答：\n" + bundle.strip()
