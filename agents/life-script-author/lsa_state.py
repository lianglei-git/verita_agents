"""Life Script Author 会话状态。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from lsa_contract import (
    CHAPTER_CONTINUITY,
    CHAPTER_DRAFT,
    CHAPTER_PLAN,
    CHAPTER_UPDATE,
    DEFAULT_ADAPTATION_MODE,
    DEFAULT_CHAPTER_COUNT,
    PHASE_BIBLE,
    PHASE_CHAPTER,
    PHASE_COMPLETE,
    PHASE_MID_REVIEW,
    PHASE_OUTLINE,
    PHASE_SETUP,
)


def empty_setup() -> dict[str, Any]:
    return {
        "status": "pending",
        "adaptation_mode": DEFAULT_ADAPTATION_MODE,
        "creative_intent": {
            "narrative_perspective": "",
            "time_span": "",
            "genre_intensity": "",
            "taboos": [],
            "ending_openness": "semi_open",
        },
        "pending_questions": [],
        "answers": {},
    }


def empty_outline() -> dict[str, Any]:
    return {
        "status": "pending",
        "target_chapter_count": DEFAULT_CHAPTER_COUNT,
        "chapters": [],
    }


def empty_chapter_work() -> dict[str, Any]:
    return {
        "current_number": 1,
        "subphase": CHAPTER_PLAN,
        "plan": None,
        "draft": None,
        "continuity_report": None,
        "completed": [],
    }


def empty_session() -> dict[str, Any]:
    return {
        "current_phase": PHASE_SETUP,
        "setup": empty_setup(),
        "handoff": {},
        "story_bible": None,
        "bible_approved": False,
        "outline": empty_outline(),
        "outline_approved": False,
        "chapter_work": empty_chapter_work(),
        "mid_review": {"last_at_chapter": 0, "pending": False, "notes": ""},
        "turns": [],
        "llm_calls": [],
    }


def normalize_session(raw: dict | None) -> dict[str, Any]:
    base = empty_session()
    if not raw:
        return base

    base["current_phase"] = str(raw.get("current_phase") or PHASE_SETUP)
    base["handoff"] = dict(raw.get("handoff") or {})
    base["story_bible"] = raw.get("story_bible")
    base["bible_approved"] = bool(raw.get("bible_approved", False))
    base["outline_approved"] = bool(raw.get("outline_approved", False))

    setup = {**empty_setup(), **(raw.get("setup") or {})}
    ci = {**empty_setup()["creative_intent"], **(setup.get("creative_intent") or {})}
    if not isinstance(ci.get("taboos"), list):
        ci["taboos"] = []
    setup["creative_intent"] = ci
    if not isinstance(setup.get("pending_questions"), list):
        setup["pending_questions"] = []
    if not isinstance(setup.get("answers"), dict):
        setup["answers"] = {}
    base["setup"] = setup

    outline = {**empty_outline(), **(raw.get("outline") or {})}
    if not isinstance(outline.get("chapters"), list):
        outline["chapters"] = []
    try:
        outline["target_chapter_count"] = max(
            3, int(outline.get("target_chapter_count") or DEFAULT_CHAPTER_COUNT)
        )
    except (TypeError, ValueError):
        outline["target_chapter_count"] = DEFAULT_CHAPTER_COUNT
    base["outline"] = outline

    cw = {**empty_chapter_work(), **(raw.get("chapter_work") or {})}
    try:
        cw["current_number"] = max(1, int(cw.get("current_number") or 1))
    except (TypeError, ValueError):
        cw["current_number"] = 1
    cw["subphase"] = str(cw.get("subphase") or CHAPTER_PLAN)
    if not isinstance(cw.get("completed"), list):
        cw["completed"] = []
    base["chapter_work"] = cw

    mr = {"last_at_chapter": 0, "pending": False, "notes": ""}
    mr.update(raw.get("mid_review") or {})
    base["mid_review"] = mr
    base["turns"] = list(raw.get("turns") or [])
    base["llm_calls"] = list(raw.get("llm_calls") or [])
    return base


def record_turn(session: dict, user_text: str, reply: str) -> dict:
    out = deepcopy(session)
    turns = list(out.get("turns") or [])
    turns.append({"user": user_text, "assistant": reply})
    out["turns"] = turns[-30:]
    return out


def set_phase(session: dict, phase: str) -> dict:
    out = deepcopy(session)
    out["current_phase"] = phase
    return out


def set_setup(session: dict, **patch: Any) -> dict:
    out = deepcopy(session)
    setup = dict(out.get("setup") or empty_setup())
    for key, val in patch.items():
        if key == "creative_intent" and isinstance(val, dict):
            ci = dict(setup.get("creative_intent") or {})
            ci.update(val)
            setup["creative_intent"] = ci
        else:
            setup[key] = val
    out["setup"] = setup
    return out


def set_bible(session: dict, bible: dict | None, *, approved: bool | None = None) -> dict:
    out = deepcopy(session)
    out["story_bible"] = bible
    if approved is not None:
        out["bible_approved"] = approved
    return out


def set_outline(session: dict, **patch: Any) -> dict:
    out = deepcopy(session)
    outline = dict(out.get("outline") or empty_outline())
    outline.update(patch)
    out["outline"] = outline
    return out


def set_chapter_work(session: dict, **patch: Any) -> dict:
    out = deepcopy(session)
    cw = dict(out.get("chapter_work") or empty_chapter_work())
    cw.update(patch)
    out["chapter_work"] = cw
    return out


def setup_complete(session: dict) -> bool:
    return (session.get("setup") or {}).get("status") == "complete"


def current_chapter_number(session: dict) -> int:
    return int((session.get("chapter_work") or {}).get("current_number") or 1)


def chapter_subphase(session: dict) -> str:
    return str((session.get("chapter_work") or {}).get("subphase") or CHAPTER_PLAN)


def total_chapters(session: dict) -> int:
    outline = session.get("outline") or {}
    chapters = outline.get("chapters") or []
    if chapters:
        return len(chapters)
    return int(outline.get("target_chapter_count") or DEFAULT_CHAPTER_COUNT)


def all_chapters_complete(session: dict) -> bool:
    cw = session.get("chapter_work") or {}
    completed = cw.get("completed") or []
    return len(completed) >= total_chapters(session)


def needs_mid_review(session: dict) -> bool:
    n = current_chapter_number(session)
    mr = session.get("mid_review") or {}
    last = int(mr.get("last_at_chapter") or 0)
    from lsa_contract import MID_REVIEW_INTERVAL

    return n > 0 and n % MID_REVIEW_INTERVAL == 0 and n > last


def append_llm_calls(session: dict, calls: list[dict]) -> dict:
    if not calls:
        return session
    out = deepcopy(session)
    merged = list(out.get("llm_calls") or [])
    merged.extend(calls)
    out["llm_calls"] = merged[-50:]
    return out
