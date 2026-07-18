"""章节计划与正文写作子流程。"""

from __future__ import annotations

import json
import uuid
from typing import Any

from _lib.planning import (
    build_safety_system_prompt,
    empty_chapter_draft,
    empty_chapter_plan,
    normalize_chapter_draft,
    normalize_chapter_plan,
    validate_contract,
)

from lsa_contract import TARGET_WORD_MAX, TARGET_WORD_MIN
from lsa_llm import call_llm_json

SYSTEM = build_safety_system_prompt("narrative")


def _outline_entry(session: dict, chapter_number: int) -> dict[str, Any]:
    chapters = (session.get("outline") or {}).get("chapters") or []
    for ch in chapters:
        if int(ch.get("chapter_number") or 0) == chapter_number:
            return ch
    return {"chapter_number": chapter_number, "title": f"第{chapter_number}章", "summary": ""}


def _bible_context(bible: dict, chapter_number: int) -> dict[str, Any]:
    """向模型传递相关章节上下文与圣经摘要。"""
    summaries = [
        s for s in (bible.get("chapter_summaries") or [])
        if int(s.get("chapter_number") or 0) < chapter_number
    ][-5:]
    return {
        "core_conflict": bible.get("core_conflict"),
        "themes": bible.get("themes"),
        "characters": bible.get("characters"),
        "relationships": bible.get("relationships"),
        "unresolved_threads": bible.get("unresolved_threads"),
        "foreshadowing": [
            f for f in (bible.get("foreshadowing") or [])
            if f.get("status") == "planted"
        ],
        "recent_chapter_summaries": summaries,
        "style_constraints": bible.get("style_constraints"),
        "fact_boundary": bible.get("fact_boundary"),
    }


def _fallback_plan(session: dict, chapter_number: int) -> dict[str, Any]:
    bible = session.get("story_bible") or {}
    entry = _outline_entry(session, chapter_number)
    plan = empty_chapter_plan()
    plan["plan_id"] = f"plan_{uuid.uuid4().hex[:8]}"
    plan["bible_id"] = str(bible.get("bible_id") or "")
    plan["chapter_number"] = chapter_number
    plan["title"] = entry.get("title") or f"第{chapter_number}章"
    plan["objectives"] = [entry.get("summary") or "推进主线冲突"]
    plan["conflict"] = bible.get("core_conflict") or "人物内心与外部压力的碰撞"
    plan["beats"] = ["开场情境", "冲突升级", "抉择时刻", "章末悬念"]
    plan["threads_to_continue"] = list(bible.get("unresolved_threads") or [])[:3]
    plan["threads_to_plant"] = ["新伏笔"]
    plan["expected_word_count"] = {"min": TARGET_WORD_MIN, "max": TARGET_WORD_MAX}
    return normalize_chapter_plan(plan)


def generate_chapter_plan(session: dict, chapter_number: int) -> tuple[dict, list[str]]:
    bible = session.get("story_bible") or {}
    entry = _outline_entry(session, chapter_number)
    ctx = _bible_context(bible, chapter_number)

    prompt = f"""为第 {chapter_number} 章生成 ChapterPlan JSON（先计划、后写作）。

大纲条目：
{json.dumps(entry, ensure_ascii=False)}

故事圣经相关上下文：
{json.dumps(ctx, ensure_ascii=False, indent=2)}

要求：
- objectives、conflict、beats（4-8个节拍）
- character_state_changes 对应 characters.id
- threads_to_continue / threads_to_plant
- expected_word_count min={TARGET_WORD_MIN} max={TARGET_WORD_MAX}
- approval.status 设为 "draft"
"""

    raw = call_llm_json(prompt, SYSTEM, label=f"chapter_plan_{chapter_number}")
    if raw:
        plan = normalize_chapter_plan({**empty_chapter_plan(), **raw})
        plan["chapter_number"] = chapter_number
        plan["bible_id"] = str(bible.get("bible_id") or plan.get("bible_id") or "")
        if not plan.get("plan_id"):
            plan["plan_id"] = f"plan_{uuid.uuid4().hex[:8]}"
    else:
        plan = _fallback_plan(session, chapter_number)

    issues = validate_contract(plan, "chapter_plan")
    return plan, issues


def _fallback_draft(session: dict, plan: dict) -> dict[str, Any]:
    n = int(plan.get("chapter_number") or 1)
    title = plan.get("title") or f"第{n}章"
    beats = plan.get("beats") or ["开场", "冲突", "收束"]
    paragraphs = [
        f"【{title}】",
        "",
        "（以下为基于所选情景创作的虚构叙事，不代表现实预测。）",
        "",
    ]
    for i, beat in enumerate(beats, 1):
        paragraphs.append(
            f"第{i}节拍·{beat}：林远站在岔路口，想起此前未竟的约定。"
            f"风从楼间穿过，他把笔记本攥得更紧了一些。"
        )
        paragraphs.append("")
    content = "\n".join(paragraphs)
    draft = empty_chapter_draft()
    draft["draft_id"] = f"draft_{uuid.uuid4().hex[:8]}"
    draft["plan_id"] = str(plan.get("plan_id") or "")
    draft["chapter_number"] = n
    draft["title"] = title
    draft["content"] = content
    draft["extracted_events"] = [f"第{n}章完成节拍：{b}" for b in beats[:3]]
    draft["new_threads"] = list(plan.get("threads_to_plant") or [])[:2]
    return normalize_chapter_draft(draft)


def generate_chapter_draft(session: dict, plan: dict) -> tuple[dict, list[str]]:
    bible = session.get("story_bible") or {}
    n = int(plan.get("chapter_number") or 1)
    ctx = _bible_context(bible, n)

    prompt = f"""根据已批准的章节计划撰写 ChapterDraft JSON。

章节计划：
{json.dumps(plan, ensure_ascii=False, indent=2)}

故事圣经上下文：
{json.dumps(ctx, ensure_ascii=False, indent=2)}

要求：
- content 为完整章节正文，字数目标 {TARGET_WORD_MIN}-{TARGET_WORD_MAX}
- 保留 fiction_disclaimer
- 填写 extracted_events、character_state_updates、new_threads
- revision.status 为 "draft"
- 遵守去识别化与 taboos，正文为虚构叙事
"""

    raw = call_llm_json(prompt, SYSTEM, label=f"chapter_draft_{n}")
    if raw:
        draft = normalize_chapter_draft({**empty_chapter_draft(), **raw})
        draft["chapter_number"] = n
        draft["plan_id"] = str(plan.get("plan_id") or draft.get("plan_id") or "")
        draft["title"] = draft.get("title") or plan.get("title") or f"第{n}章"
        if not draft.get("draft_id"):
            draft["draft_id"] = f"draft_{uuid.uuid4().hex[:8]}"
    else:
        draft = _fallback_draft(session, plan)

    issues = validate_contract(draft, "chapter_draft")
    return draft, issues
