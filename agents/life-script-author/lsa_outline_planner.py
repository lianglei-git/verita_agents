"""故事圣经与章节大纲子流程。"""

from __future__ import annotations

import json
import uuid
from typing import Any

from _lib.planning import (
    build_safety_system_prompt,
    empty_story_bible,
    normalize_story_bible,
    validate_contract,
)

from lsa_contract import DEFAULT_ADAPTATION_MODE, DEFAULT_CHAPTER_COUNT
from lsa_llm import call_llm_json

SYSTEM = build_safety_system_prompt("narrative")

SETUP_QUESTIONS: list[dict[str, Any]] = [
    {
        "id": "narrative_perspective",
        "type": "open",
        "text": "希望采用什么叙事视角？（如第一人称、第三人称有限视角）",
        "required": True,
    },
    {
        "id": "time_span",
        "type": "open",
        "text": "故事时间跨度大致多久？（如三年、十年）",
        "required": True,
    },
    {
        "id": "genre_intensity",
        "type": "open",
        "text": "题材强度偏好？（现实主义 / 轻度戏剧化 / 强戏剧冲突）",
        "required": True,
    },
    {
        "id": "ending_openness",
        "type": "single",
        "text": "结局开放度？",
        "options": [
            {"value": "open", "label": "开放结局"},
            {"value": "semi_open", "label": "半开放"},
            {"value": "closed", "label": "明确结局"},
        ],
        "required": True,
    },
    {
        "id": "taboos",
        "type": "open",
        "text": "创作禁区（不愿出现的情节、人物或细节，可留空）",
        "required": False,
    },
    {
        "id": "adaptation_mode",
        "type": "single",
        "text": "与现实经历的映射方式（默认去识别化）",
        "options": [
            {"value": "faithful", "label": "忠实映射"},
            {"value": "deidentified", "label": "去识别化改编"},
            {"value": "fictionalized", "label": "完全虚构化"},
        ],
        "required": True,
    },
]


def _scenario_context(handoff: dict) -> str:
    scenario_set = handoff.get("scenario_set") or {}
    selected_id = str(
        scenario_set.get("selected_scenario_id")
        or handoff.get("scenario_id")
        or ""
    ).strip()
    scenarios = scenario_set.get("scenarios") or []
    chosen = None
    for s in scenarios:
        if str(s.get("id")) == selected_id:
            chosen = s
            break
    if not chosen and scenarios:
        chosen = scenarios[0]

    profile = handoff.get("planning_profile") or {}
    parts = [
        f"目标锚点：{profile.get('anchors', {}).get('goal', '')}",
        f"现状锚点：{profile.get('anchors', {}).get('current', '')}",
    ]
    if chosen:
        parts.append(f"已选情景：{chosen.get('title', '')} — {chosen.get('tagline', '')}")
        premises = [p.get("text", "") for p in (chosen.get("premises") or [])[:3]]
        if premises:
            parts.append("情景前提：" + "；".join(premises))
    return "\n".join(p for p in parts if p.strip())


def ensure_setup_questions(session: dict) -> dict:
    setup = session.get("setup") or {}
    if setup.get("pending_questions"):
        return session
    from lsa_state import set_setup

    return set_setup(session, pending_questions=list(SETUP_QUESTIONS))


def apply_setup_answer(session: dict, answer: dict) -> dict:
    from lsa_state import set_setup

    qid = str(answer.get("question_id") or "").strip()
    if not qid:
        return session
    answers = dict((session.get("setup") or {}).get("answers") or {})
    answers[qid] = {"type": answer.get("type"), "value": answer.get("value")}
    session = set_setup(session, answers=answers)

    ci = dict((session.get("setup") or {}).get("creative_intent") or {})
    val = answer.get("value")
    if qid in ("narrative_perspective", "time_span", "genre_intensity", "ending_openness"):
        if isinstance(val, str):
            ci[qid] = val.strip()
        elif isinstance(val, list) and val:
            ci[qid] = str(val[0])
    elif qid == "taboos" and isinstance(val, str) and val.strip():
        taboos = list(ci.get("taboos") or [])
        taboos.append(val.strip())
        ci["taboos"] = taboos
    elif qid == "adaptation_mode" and isinstance(val, str):
        mode = val.strip()
        if mode in ("faithful", "deidentified", "fictionalized"):
            session = set_setup(session, adaptation_mode=mode)

    session = set_setup(session, creative_intent=ci)
    return session


def setup_all_answered(session: dict) -> bool:
    pending = (session.get("setup") or {}).get("pending_questions") or []
    answers = (session.get("setup") or {}).get("answers") or {}
    for q in pending:
        if q.get("required", True) and q["id"] not in answers:
            return False
    return bool(pending)


def finalize_setup(session: dict) -> dict:
    from lsa_state import set_setup

    return set_setup(session, status="complete")


def _fallback_bible(session: dict) -> dict:
    handoff = session.get("handoff") or {}
    setup = session.get("setup") or {}
    ci = setup.get("creative_intent") or {}
    profile = handoff.get("planning_profile") or {}
    goal = profile.get("anchors", {}).get("goal", "未命名目标")
    bible = empty_story_bible()
    bible["bible_id"] = f"bible_{uuid.uuid4().hex[:8]}"
    bible["profile_id"] = str(profile.get("profile_id") or "")
    bible["adaptation_mode"] = setup.get("adaptation_mode") or DEFAULT_ADAPTATION_MODE
    bible["creative_intent"] = {
        **bible["creative_intent"],
        **ci,
    }
    bible["core_conflict"] = f"主角在追寻「{goal}」的过程中，与现实约束和内心抉择不断碰撞。"
    bible["themes"] = ["成长", "选择", "代价"]
    bible["characters"] = [
        {
            "id": "char_protagonist",
            "name": "林远",
            "role": "protagonist",
            "arc": "从犹豫观望到主动承担",
            "traits": ["敏感", "坚韧"],
            "state": {"chapter": 0, "emotional": "观望"},
        }
    ]
    bible["fact_boundary"]["do_not_identify"] = ["真实姓名", "具体雇主", "可识别地址"]
    bible["style_constraints"] = {
        "tone": "写实克制",
        "pov": ci.get("narrative_perspective") or "第三人称有限",
        "tense": "过去时",
    }
    return normalize_story_bible(bible)


def generate_story_bible(session: dict) -> tuple[dict, list[str]]:
    """生成 StoryBible，返回 (bible, issues)。"""
    handoff = session.get("handoff") or {}
    setup = session.get("setup") or {}
    ci = setup.get("creative_intent") or {}
    adaptation = setup.get("adaptation_mode") or DEFAULT_ADAPTATION_MODE

    prompt = f"""基于以下用户确认的创作意图与规划情景，生成故事圣经 StoryBible JSON。

创作意图：
{json.dumps(ci, ensure_ascii=False, indent=2)}

改编模式：{adaptation}（默认去识别化，勿写入可识别真实信息）

情景与画像上下文：
{_scenario_context(handoff)}

输出完整 StoryBible JSON，包含：characters、relationships、core_conflict、themes、
world_rules、timeline（至少3条）、foreshadowing（至少2条）、style_constraints、
fact_boundary（含 do_not_identify）。人物使用虚构姓名。
"""

    raw = call_llm_json(prompt, SYSTEM, label="story_bible")
    if raw:
        bible = normalize_story_bible({**empty_story_bible(), **raw})
        bible["adaptation_mode"] = adaptation
        bible["creative_intent"] = {**bible["creative_intent"], **ci}
        if not bible.get("bible_id"):
            bible["bible_id"] = f"bible_{uuid.uuid4().hex[:8]}"
    else:
        bible = _fallback_bible(session)

    issues = validate_contract(bible, "story_bible")
    return bible, issues


def _fallback_outline(session: dict, count: int) -> list[dict[str, Any]]:
    bible = session.get("story_bible") or {}
    conflict = bible.get("core_conflict") or "主线冲突"
    chapters: list[dict[str, Any]] = []
    acts = [
        ("开端", 0.15),
        ("发展", 0.35),
        ("中段转折", 0.25),
        ("高潮", 0.15),
        ("收束", 0.10),
    ]
    idx = 1
    for act_name, ratio in acts:
        act_count = max(1, int(count * ratio))
        for j in range(act_count):
            if idx > count:
                break
            chapters.append({
                "chapter_number": idx,
                "title": f"第{idx}章 · {act_name}",
                "summary": f"围绕「{conflict[:40]}」推进，{act_name}阶段的第{j + 1}节拍。",
                "act": act_name,
            })
            idx += 1
    while len(chapters) < count:
        n = len(chapters) + 1
        chapters.append({
            "chapter_number": n,
            "title": f"第{n}章",
            "summary": "情节持续推进与人物成长。",
            "act": "发展",
        })
    return chapters[:count]


def generate_outline(session: dict) -> tuple[list[dict[str, Any]], list[str]]:
    """生成全书章节表，返回 (chapters, issues)。"""
    bible = session.get("story_bible") or {}
    outline = session.get("outline") or {}
    count = int(outline.get("target_chapter_count") or DEFAULT_CHAPTER_COUNT)

    prompt = f"""根据故事圣经，生成全书章节大纲（恰好 {count} 章）。

故事圣经摘要：
{json.dumps({
    "core_conflict": bible.get("core_conflict"),
    "themes": bible.get("themes"),
    "characters": bible.get("characters"),
    "timeline": bible.get("timeline"),
    "foreshadowing": bible.get("foreshadowing"),
}, ensure_ascii=False, indent=2)}

输出 JSON：
{{
  "chapters": [
    {{"chapter_number": 1, "title": "章标题", "summary": "200字内节拍摘要", "act": "开端|发展|转折|高潮|收束"}}
  ]
}}
章节数必须等于 {count}，叙事连贯，分布起承转合。
"""

    raw = call_llm_json(prompt, SYSTEM, label="chapter_outline")
    chapters: list[dict[str, Any]] = []
    if raw and isinstance(raw.get("chapters"), list):
        for item in raw["chapters"]:
            if isinstance(item, dict) and item.get("chapter_number"):
                chapters.append({
                    "chapter_number": int(item["chapter_number"]),
                    "title": str(item.get("title") or ""),
                    "summary": str(item.get("summary") or ""),
                    "act": str(item.get("act") or ""),
                })
    if len(chapters) < count:
        chapters = _fallback_outline(session, count)

    chapters.sort(key=lambda c: c["chapter_number"])
    issues: list[str] = []
    if len(chapters) != count:
        issues.append(f"expected {count} chapters, got {len(chapters)}")
    return chapters, issues
