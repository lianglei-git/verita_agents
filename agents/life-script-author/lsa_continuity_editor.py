"""连续性校验与故事圣经回写子流程。"""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from _lib.planning import (
    audit_document_text_fields,
    build_safety_system_prompt,
    normalize_story_bible,
    scan_text_violations,
)

from lsa_llm import call_llm_json

SYSTEM = build_safety_system_prompt("narrative")


def _rule_based_checks(bible: dict, plan: dict, draft: dict) -> list[dict[str, Any]]:
    """轻量规则检查（无 LLM 时仍可用）。"""
    flags: list[dict[str, Any]] = []
    content = str(draft.get("content") or "")
    chapter_number = int(draft.get("chapter_number") or 0)

    for v in scan_text_violations(content):
        flags.append({
            "severity": "error",
            "code": v["code"],
            "message": v["message"],
        })

    for field, label in (("content", "正文"), ("title", "标题")):
        for v in audit_document_text_fields(draft, [field]):
            flags.append({
                "severity": "warning",
                "code": "safety_scan",
                "message": f"{label}: {v}",
            })

    char_ids = {c.get("id") for c in (bible.get("characters") or [])}
    for upd in draft.get("character_state_updates") or []:
        cid = upd.get("character_id")
        if cid and cid not in char_ids:
            flags.append({
                "severity": "warning",
                "code": "unknown_character",
                "message": f"草稿更新了未在圣经中登记的人物：{cid}",
            })

    planned_threads = set(plan.get("threads_to_continue") or [])
    for thread in planned_threads:
        if thread and thread not in content:
            flags.append({
                "severity": "info",
                "code": "thread_not_evident",
                "message": f"计划延续的线索「{thread[:40]}」在正文中不明显",
            })

    summaries = bible.get("chapter_summaries") or []
    for s in summaries:
        if int(s.get("chapter_number") or 0) == chapter_number:
            flags.append({
                "severity": "warning",
                "code": "duplicate_chapter",
                "message": f"第 {chapter_number} 章摘要已存在于圣经中",
            })
            break

    return flags


def run_continuity_check(
    bible: dict,
    plan: dict,
    draft: dict,
) -> dict[str, Any]:
    """对照故事圣经检查连续性，返回报告。"""
    rule_flags = _rule_based_checks(bible, plan, draft)

    prompt = f"""对照故事圣经检查章节草稿的连续性问题。

故事圣经：
{json.dumps({
    "timeline": bible.get("timeline"),
    "characters": bible.get("characters"),
    "foreshadowing": bible.get("foreshadowing"),
    "unresolved_threads": bible.get("unresolved_threads"),
    "world_rules": bible.get("world_rules"),
}, ensure_ascii=False, indent=2)}

章节计划：
{json.dumps({
    "objectives": plan.get("objectives"),
    "character_state_changes": plan.get("character_state_changes"),
    "threads_to_plant": plan.get("threads_to_plant"),
}, ensure_ascii=False)}

草稿摘要（前800字）：
{str(draft.get("content") or "")[:800]}

输出 JSON：
{{
  "passed": true/false,
  "issues": [
    {{"severity": "info|warning|error", "code": "...", "message": "..."}}
  ],
  "summary": "一句话总结"
}}
只报告矛盾，不要静默掩盖。severity=error 表示应退回修订。
"""

    raw = call_llm_json(prompt, SYSTEM, label="continuity_check")
    llm_issues: list[dict[str, Any]] = []
    passed = True
    summary = ""

    if raw:
        passed = bool(raw.get("passed", True))
        summary = str(raw.get("summary") or "")
        for item in raw.get("issues") or []:
            if isinstance(item, dict) and item.get("message"):
                llm_issues.append({
                    "severity": item.get("severity") or "warning",
                    "code": str(item.get("code") or "continuity"),
                    "message": str(item.get("message")),
                })

    all_issues = rule_flags + llm_issues
    has_error = any(i.get("severity") == "error" for i in all_issues)
    if has_error:
        passed = False

    return {
        "passed": passed and not has_error,
        "issues": all_issues,
        "summary": summary or (
            "连续性检查通过" if passed and not has_error else "发现需关注的连续性问题"
        ),
    }


def apply_draft_to_bible(bible: dict, plan: dict, draft: dict) -> dict:
    """将章节草稿提取的事件与状态回写 StoryBible。"""
    out = normalize_story_bible(deepcopy(bible))
    n = int(draft.get("chapter_number") or 1)
    title = str(draft.get("title") or plan.get("title") or f"第{n}章")

    summaries = [s for s in (out.get("chapter_summaries") or [])
                 if int(s.get("chapter_number") or 0) != n]
    summary_text = " ".join(draft.get("extracted_events") or [])[:500]
    if not summary_text:
        summary_text = str(draft.get("content") or "")[:300]
    summaries.append({
        "chapter_number": n,
        "title": title,
        "summary": summary_text,
    })
    summaries.sort(key=lambda s: int(s.get("chapter_number") or 0))
    out["chapter_summaries"] = summaries

    chars = list(out.get("characters") or [])
    char_map = {c.get("id"): c for c in chars}
    for upd in draft.get("character_state_updates") or []:
        cid = upd.get("character_id")
        if not cid:
            continue
        if cid in char_map:
            state = dict(char_map[cid].get("state") or {})
            state.update(upd.get("state") or {})
            state["chapter"] = n
            char_map[cid]["state"] = state
        else:
            chars.append({
                "id": cid,
                "name": cid,
                "role": "supporting",
                "arc": "",
                "traits": [],
                "state": {**(upd.get("state") or {}), "chapter": n},
            })
    out["characters"] = list(char_map.values()) if char_map else chars

    timeline = list(out.get("timeline") or [])
    for i, evt in enumerate(draft.get("extracted_events") or []):
        if not evt:
            continue
        timeline.append({
            "id": f"ch{n}_evt_{i + 1}",
            "when": f"第{n}章",
            "event": str(evt),
            "chapter_refs": [n],
        })
    out["timeline"] = timeline

    threads = list(out.get("unresolved_threads") or [])
    continued = set(plan.get("threads_to_continue") or [])
    planted = set(draft.get("new_threads") or []) | set(plan.get("threads_to_plant") or [])
    threads = [t for t in threads if t not in continued]
    for t in planted:
        if t and t not in threads:
            threads.append(t)
    out["unresolved_threads"] = threads

    notes = list(out.get("continuity_notes") or [])
    notes.append(f"第{n}章已回写：{title}")
    out["continuity_notes"] = notes[-20:]

    return normalize_story_bible(out)
