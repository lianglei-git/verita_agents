"""Step 1 — 判断用户目标是否明确（多题下发 → 逐题作答 → 答毕重判）。"""

from __future__ import annotations

import logging
from typing import Any

from contract import STEP_GOAL, UI_MODE_SURVEY, normalize_questions
from debug_log import gb_log
from prompts.step1 import (
    BOOTSTRAP_REPLY,
    LLM_UNAVAILABLE_REPLY,
    SYSTEM,
    build_step1_prompt,
    build_step1_rejudge_prompt,
)
from steps.llm_call import begin_llm_turn, call_llm, get_llm_calls
from user_profile import (
    format_round_user_line,
    get_user_profile,
    merge_profile_from_llm,
    merge_round_before_ai,
)
from state import (
    active_question,
    all_pending_answered,
    answers_map,
    empty_session,
    normalize_session,
    pending_questions,
    question_progress,
    record_turn,
    set_step1,
    step1_complete,
    store_answer,
)

try:
    from _lib.llm import is_llm_available
except ImportError:

    def is_llm_available() -> bool:  # type: ignore[misc]
        return False

logger = logging.getLogger(__name__)

STEP = STEP_GOAL


def _answer_display(q: dict, stored: dict) -> str:
    val = stored.get("value")
    if q.get("type") == "multi" and isinstance(val, list):
        labels = {o["id"]: o["label"] for o in q.get("options") or []}
        return "、".join(labels.get(v, str(v)) for v in val)
    if q.get("type") == "single" and isinstance(val, str):
        labels = {o["id"]: o["label"] for o in q.get("options") or []}
        return labels.get(val, val)
    return str(val or "").strip()


def _format_answer_bundle(session: dict) -> str:
    lines: list[str] = []
    for q in pending_questions(session):
        stored = answers_map(session).get(q["id"])
        if not stored:
            continue
        lines.append(f"- [{q['id']}] {q['text']} → {_answer_display(q, stored)}")
    return "\n".join(lines)


def _qa_items(session: dict) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for q in pending_questions(session):
        stored = answers_map(session).get(q["id"])
        if not stored:
            continue
        items.append({"question": q["text"], "answer": _answer_display(q, stored)})
    return items


def _normalize_llm_data(data: dict) -> dict:
    out = dict(data)
    clarity = str(out.get("goal_clarity") or out.get("clarity") or "unclear").strip()
    if clarity not in ("unclear", "clear"):
        clarity = "unclear"
    out["goal_clarity"] = clarity
    return out


def _fallback_reply(data: dict) -> str:
    reply = str(data.get("reply") or "").strip()
    if reply:
        return reply
    goal = str(data.get("goal_text") or "").strip()
    if data.get("goal_clarity") == "clear":
        return f"目标已明确：{goal}" if goal else "目标已明确，可以进入下一步。"
    questions = normalize_questions(data.get("next_questions"))
    if not questions and data.get("next_question"):
        questions = normalize_questions([data.get("next_question")])
    if questions:
        return "根据您补充的信息，还需要再确认几项。"
    return "请继续说明您的目标。"


def _apply_llm(session: dict, data: dict) -> dict:
    data = _normalize_llm_data(data)
    session = merge_profile_from_llm(session, data)
    gb_log("step1.llm.parse", llm_raw=data)
    clarity = data["goal_clarity"]
    goal = str(data.get("goal_text") or "").strip()
    if not goal:
        goal = str((session.get("step1") or {}).get("goal_text") or "").strip()
    questions = normalize_questions(data.get("next_questions"))
    if not questions and data.get("next_question"):
        questions = normalize_questions([data.get("next_question")])
    for q in questions:
        q["step"] = STEP

    session = set_step1(session, clarity=clarity, goal_text=goal or None)
    if clarity == "clear":
        session = set_step1(session, pending_questions=[], answers={})
    else:
        session = set_step1(session, pending_questions=questions, answers={})
        if len(questions) > 1:
            session = set_step1(session, ui_mode=UI_MODE_SURVEY)
    if clarity == "unclear" and not questions:
        gb_log("step1.llm.warn", reason="unclear but no valid next_questions after normalize")
    gb_log(
        "step1.llm.applied",
        goal_clarity=clarity,
        goal_text=goal or None,
        next_questions_count=len(questions),
        next_question_ids=[q["id"] for q in questions],
    )
    return session


def _build_result(
    session: dict,
    reply: str,
    *,
    source: str,
) -> dict[str, Any]:
    complete = step1_complete(session)
    if complete:
        session = dict(session)
        session["current_step"] = 2

    pending = pending_questions(session)
    active = None if complete else active_question(session)
    progress = question_progress(session)
    ui_mode = (session.get("step1") or {}).get("ui_mode") or "sequential"

    return {
        "session": session,
        "reply": reply,
        "current_step": session.get("current_step", STEP),
        "step_complete": complete,
        "next_questions": pending if not complete else [],
        "active_question": active,
        "next_question": active,
        "question_progress": progress,
        "ui_mode": ui_mode,
        "source": source,
        "llm_calls": get_llm_calls(),
    }


def _process_llm_turn(session: dict, data: dict | None) -> tuple[dict, str] | None:
    if not data:
        return None
    data = _normalize_llm_data(data)
    reply = _fallback_reply(data)
    session = _apply_llm(session, data)
    return session, reply


def _llm_judge(session: dict, user_message: str) -> tuple[dict, str | None]:
    session = merge_round_before_ai(
        session,
        step=STEP,
        items=[{"question": "用户目标表述", "answer": user_message.strip()}],
    )
    prompt = build_step1_prompt(user_message, session)
    data = call_llm(prompt, SYSTEM, label="step1.judge")
    processed = _process_llm_turn(session, data)
    if processed:
        return processed
    return session, None


def _llm_rejudge(session: dict) -> tuple[dict, str | None, str]:
    items = _qa_items(session)
    bundle = _format_answer_bundle(session)
    session = merge_round_before_ai(session, step=STEP, items=items)
    gb_log("step1.pre_ai.profile", user_profile=get_user_profile(session), answer_bundle=bundle)
    prompt = build_step1_rejudge_prompt(session, bundle)
    data = call_llm(prompt, SYSTEM, label="step1.rejudge")
    processed = _process_llm_turn(session, data)
    user_line = format_round_user_line(bundle)
    if processed:
        session, reply = processed
        return session, reply, user_line
    return session, None, user_line


def _store_answers_batch(session: dict, answers_batch: list[dict] | None) -> dict:
    if not answers_batch:
        return session
    for item in answers_batch:
        if isinstance(item, dict) and item.get("question_id"):
            session = store_answer(session, item)
    return session


def _merge_answered_to_profile(session: dict) -> dict:
    items = _qa_items(session)
    if items:
        session = merge_round_before_ai(session, step=STEP, items=items)
    return session


def _confirm_step(session: dict) -> dict[str, Any]:
    s1 = session.get("step1") or {}
    profile = get_user_profile(session)
    goal = str(s1.get("goal_text") or "").strip()
    if not goal:
        structured = profile.get("structured") or {}
        goal = str(structured.get("目标") or structured.get("goal") or "").strip()
    if not goal and profile.get("summary"):
        goal = str(profile.get("summary") or "")[:120].strip()
    session = set_step1(
        session,
        clarity="clear",
        goal_text=goal or "（用户确认进入下一步）",
        pending_questions=[],
        answers={},
    )
    session = dict(session)
    session["current_step"] = 2
    reply = f"已按您的确认锁定目标，进入信息收集。"
    session = record_turn(session, "（我认为目标已经够清楚了）", reply)
    return _log_result(_build_result(session, reply, source="confirm"))


def _try_rejudge(session: dict) -> dict[str, Any]:
    if not is_llm_available():
        items = _qa_items(session)
        if items:
            session = merge_round_before_ai(session, step=STEP, items=items)
        return _build_result(session, LLM_UNAVAILABLE_REPLY, source="error")
    session, reply, user_line = _llm_rejudge(session)
    if reply is None:
        return _build_result(session, "处理失败，请重试。", source="error")
    session = record_turn(session, user_line, reply)
    return _build_result(session, reply, source="rejudge")


def run(
    session: dict,
    user_input: str,
    answer: dict | None = None,
    answers_batch: list[dict] | None = None,
    confirm_step: bool = False,
) -> dict[str, Any]:
    begin_llm_turn()
    session = normalize_session(session)
    gb_log(
        "step1.run ▶",
        user_input=user_input or None,
        answer=answer,
        answers_batch=answers_batch,
        confirm_step=confirm_step,
        step1_in=session.get("step1"),
    )

    if confirm_step and not step1_complete(session):
        session = _store_answers_batch(session, answers_batch)
        session = _merge_answered_to_profile(session)
        return _confirm_step(session)

    if step1_complete(session):
        goal = (session.get("step1") or {}).get("goal_text") or ""
        return _log_result(_build_result(
            session,
            f"目标已明确：{goal}。可进入步骤 2（信息收集，待实现）。",
            source="cached",
        ))

    # 开放题可用 message 文本作答（兼容首轮输入）
    text = (user_input or "").strip()
    if text and pending_questions(session) and not answer and not answers_batch:
        active = active_question(session)
        if active and active.get("type") == "open":
            answer = {"question_id": active["id"], "type": "open", "value": text}
            text = ""

    if answers_batch:
        for item in answers_batch:
            if isinstance(item, dict):
                session = store_answer(session, item)
        if pending_questions(session) and all_pending_answered(session):
            return _log_result(_try_rejudge(session))
        return _log_result(_build_result(session, "请完成所有题目后再提交。", source="error"))

    # 逐题收集中：记录单题答案
    if answer and pending_questions(session):
        session = store_answer(session, answer)
        if not all_pending_answered(session):
            active = active_question(session)
            prog = question_progress(session)
            reply = f"已记录（{prog['answered']}/{prog['total']}），请继续下一题。"
            return _log_result(_build_result(session, reply, source="collecting"))

        return _log_result(_try_rejudge(session))

    # 已全部答完但未带 answer（如恢复会话、误点运行）：自动重判
    if pending_questions(session) and all_pending_answered(session):
        return _log_result(_try_rejudge(session))

    text = (user_input or "").strip()

    if not text and not (session.get("turns") or []):
        session = record_turn(session, "", BOOTSTRAP_REPLY)
        bootstrap_q = [{
            "id": "goal_intro",
            "step": STEP,
            "type": "open",
            "text": BOOTSTRAP_REPLY,
            "options": [],
            "required": True,
        }]
        session = set_step1(session, pending_questions=bootstrap_q, clarity="unclear")
        return _log_result(_build_result(session, BOOTSTRAP_REPLY, source="bootstrap"))

    if not text:
        return _log_result(_build_result(session, "请输入您的回答。", source="error"))

    if not is_llm_available():
        return _log_result(_build_result(session, LLM_UNAVAILABLE_REPLY, source="error"))

    judged = _llm_judge(session, text)
    session, reply = judged
    if reply is None:
        return _log_result(_build_result(session, "处理失败，请重试。", source="error"))
    session = record_turn(session, text, reply)
    return _log_result(_build_result(session, reply, source="llm"))


def bootstrap() -> dict[str, Any]:
    return run(empty_session(), "", None)


def _log_result(result: dict[str, Any]) -> dict[str, Any]:
    gb_log(
        "step1.run ◀",
        source=result.get("source"),
        step_complete=result.get("step_complete"),
        question_progress=result.get("question_progress"),
        active_question_id=(result.get("active_question") or {}).get("id"),
        reply=result.get("reply"),
    )
    return result
