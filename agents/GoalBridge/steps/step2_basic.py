"""Step 2 — 基础画像（固定 JSON 模板，直接合并 user_profile，不调 LLM）。"""

from __future__ import annotations

from typing import Any

from basic_profile import (
    answers_to_structured,
    get_schema_for_client,
    merge_basic_profile,
    schema_to_questions,
)
from contract import STEP_BASIC
from debug_log import gb_log
from state import (
    basic_profile_complete,
    basic_store_answer,
    basic_store_batch,
    normalize_session,
    record_turn,
    set_basic_profile,
    step1_complete,
)

STEP = STEP_BASIC
DONE_REPLY = "基础信息已记录，接下来将根据您的目标收集补充信息。"


def _build_result(session: dict, reply: str, *, source: str) -> dict[str, Any]:
    complete = basic_profile_complete(session)
    if complete:
        session = dict(session)
        session["current_step"] = 3

    questions = schema_to_questions()
    answers = (session.get("step2") or {}).get("answers") or {}
    answered = sum(1 for q in questions if q["id"] in answers)

    return {
        "session": session,
        "reply": reply,
        "current_step": session.get("current_step", STEP),
        "step_complete": complete,
        "next_questions": questions if not complete else [],
        "active_question": None,
        "next_question": None,
        "question_progress": {"answered": answered, "total": len(questions)},
        "ui_mode": "survey",
        "source": source,
        "llm_calls": [],
        "basic_profile_schema": get_schema_for_client(),
    }


def _finish(session: dict, *, partial: bool) -> dict[str, Any]:
    answers = (session.get("step2") or {}).get("answers") or {}
    structured = answers_to_structured(answers)
    if structured:
        session = merge_basic_profile(session, structured)
    session = set_basic_profile(session, status="complete")
    session = dict(session)
    session["current_step"] = 3
    user_line = "（就这样）" if partial else "（提交基础信息）"
    session = record_turn(session, user_line, DONE_REPLY)
    gb_log("step2.basic.done", structured=structured, partial=partial)
    return _build_result(session, DONE_REPLY, source="finish" if partial else "submit")


def run(
    session: dict,
    user_input: str,
    answer: dict | None = None,
    answers_batch: list[dict] | None = None,
    confirm_step: bool = False,
) -> dict[str, Any]:
    session = normalize_session(session)
    gb_log(
        "step2.basic.run ▶",
        confirm_step=confirm_step,
        answers_batch=answers_batch,
        step2_in=session.get("step2"),
    )

    if not step1_complete(session):
        return _build_result(session, "请先完成步骤 1（明确目标）。", source="error")

    if basic_profile_complete(session):
        return _build_result(session, DONE_REPLY, source="cached")

    if confirm_step:
        if answers_batch:
            session = basic_store_batch(session, answers_batch)
        return _finish(session, partial=True)

    if answers_batch is not None:
        session = basic_store_batch(session, answers_batch)
        return _finish(session, partial=False)

    if answer:
        session = basic_store_answer(session, answer)

    schema = get_schema_for_client()
    title = str(schema.get("title") or "基础信息")
    desc = str(schema.get("description") or "").strip()
    reply = f"{title}：{desc}" if desc else title
    return _build_result(session, reply, source="form")
