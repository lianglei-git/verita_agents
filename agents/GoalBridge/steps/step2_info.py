"""Step 2 — 信息收集（问卷下发 → 批量作答 → AI 评估是否足够）。"""

from __future__ import annotations

import logging
from typing import Any

from contract import STEP_INFO, normalize_questions
from debug_log import gb_log
from prompts.step1 import LLM_UNAVAILABLE_REPLY
from prompts.step2 import (
    BOOTSTRAP_REPLY,
    SYSTEM,
    build_step2_evaluate_prompt,
    build_step2_plan_prompt,
)
from steps.llm_call import begin_llm_turn, call_llm, get_llm_calls
from user_profile import (
    format_round_user_line,
    get_user_profile,
    merge_profile_from_llm,
    merge_round_before_ai,
)
from state import (
    basic_profile_complete,
    ensure_step3_goal,
    normalize_session,
    record_turn,
    set_step3_info,
    step1_complete,
    step3_all_answered,
    step3_answers_map,
    step3_info_complete,
    step3_pending_questions,
    step3_store_answer,
)

logger = logging.getLogger(__name__)

STEP = STEP_INFO


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
    for q in step3_pending_questions(session):
        stored = step3_answers_map(session).get(q["id"])
        if not stored:
            continue
        lines.append(f"- [{q['id']}] {q['text']} → {_answer_display(q, stored)}")
    return "\n".join(lines)


def _qa_items(session: dict) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for q in step3_pending_questions(session):
        stored = step3_answers_map(session).get(q["id"])
        if not stored:
            continue
        items.append({"question": q["text"], "answer": _answer_display(q, stored)})
    return items


def _normalize_llm_data(data: dict) -> dict:
    out = dict(data)
    suff = str(
        out.get("info_sufficiency") or out.get("sufficiency") or "need_more"
    ).strip()
    if suff not in ("need_more", "enough"):
        suff = "need_more"
    out["info_sufficiency"] = suff
    return out


def _fallback_reply(data: dict) -> str:
    reply = str(data.get("reply") or "").strip()
    if reply:
        return reply
    if data.get("info_sufficiency") == "enough":
        return "基础信息已收集完整，可进入步骤 4（差距评估，待实现）。"
    questions = normalize_questions(data.get("next_questions"))
    if questions:
        return "请补充以下信息，以便更准确评估。"
    return BOOTSTRAP_REPLY


def _apply_llm(session: dict, data: dict) -> dict:
    data = _normalize_llm_data(data)
    session = merge_profile_from_llm(session, data)
    gb_log("step2.llm.parse", llm_raw=data)
    suff = data["info_sufficiency"]
    collected = data.get("collected_info")
    if not isinstance(collected, dict):
        collected = {}
    profile = get_user_profile(session)
    if not collected and profile.get("structured"):
        collected = dict(profile.get("structured") or {})
    questions = normalize_questions(data.get("next_questions"))
    if not questions and data.get("next_question"):
        questions = normalize_questions([data.get("next_question")])
    for q in questions:
        q["step"] = STEP

    session = ensure_step3_goal(session)
    if suff == "enough":
        session = set_step3_info(
            session,
            sufficiency="enough",
            status="complete",
            pending_questions=[],
            answers={},
            data=collected,
        )
    else:
        session = set_step3_info(
            session,
            sufficiency="need_more",
            status="collecting",
            pending_questions=questions,
            answers={},
        )
    gb_log(
        "step2.llm.applied",
        info_sufficiency=suff,
        next_questions_count=len(questions),
        collected_keys=list(collected.keys()) if collected else [],
    )
    return session


def _process_llm_turn(session: dict, data: dict | None) -> tuple[dict, str] | None:
    if not data:
        return None
    data = _normalize_llm_data(data)
    reply = _fallback_reply(data)
    session = _apply_llm(session, data)
    return session, reply


def _build_result(session: dict, reply: str, *, source: str) -> dict[str, Any]:
    complete = step3_info_complete(session)
    if complete:
        session = dict(session)
        session["current_step"] = 4

    pending = step3_pending_questions(session)
    progress = {
        "answered": sum(1 for q in pending if q["id"] in step3_answers_map(session)),
        "total": len(pending),
    }
    ui_mode = (session.get("step3") or {}).get("ui_mode") or "survey"

    return {
        "session": session,
        "reply": reply,
        "current_step": session.get("current_step", STEP),
        "step_complete": complete,
        "next_questions": pending if not complete else [],
        "active_question": None,
        "next_question": None,
        "question_progress": progress,
        "ui_mode": ui_mode,
        "source": source,
        "llm_calls": get_llm_calls(),
    }


def _llm_plan(session: dict) -> tuple[dict, str | None]:
    prompt = build_step2_plan_prompt(session)
    data = call_llm(prompt, SYSTEM, label="step2.plan")
    processed = _process_llm_turn(session, data)
    if processed:
        return processed
    return session, None


def _llm_evaluate(session: dict) -> tuple[dict, str | None, str]:
    items = _qa_items(session)
    bundle = _format_answer_bundle(session)
    session = merge_round_before_ai(session, step=STEP, items=items)
    gb_log("step2.pre_ai.profile", user_profile=get_user_profile(session), answer_bundle=bundle)
    prompt = build_step2_evaluate_prompt(session, bundle)
    data = call_llm(prompt, SYSTEM, label="step2.evaluate")
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
            session = step3_store_answer(session, item)
    return session


def _merge_answered_to_profile(session: dict) -> dict:
    items = _qa_items(session)
    if items:
        session = merge_round_before_ai(session, step=STEP, items=items)
    return session


def _confirm_step(session: dict) -> dict[str, Any]:
    session = ensure_step3_goal(session)
    profile = get_user_profile(session)
    collected = dict(profile.get("structured") or {})
    session = set_step3_info(
        session,
        sufficiency="enough",
        status="complete",
        pending_questions=[],
        answers={},
        data=collected,
    )
    session = dict(session)
    session["current_step"] = 4
    reply = "已按您的确认完成信息收集，进入差距评估。"
    session = record_turn(session, "（就这样）", reply)
    return _log_result(_build_result(session, reply, source="confirm"))


def _try_evaluate(session: dict) -> dict[str, Any]:
    from _lib.llm import is_llm_available  # noqa: WPS433

    if not is_llm_available():
        items = _qa_items(session)
        if items:
            session = merge_round_before_ai(session, step=STEP, items=items)
        return _log_result(_build_result(session, LLM_UNAVAILABLE_REPLY, source="error"))
    evaluated = _llm_evaluate(session)
    session, reply, user_line = evaluated
    if reply is None:
        return _log_result(_build_result(session, "处理失败，请重试。", source="error"))
    session = record_turn(session, user_line, reply)
    return _log_result(_build_result(session, reply, source="evaluate"))


def _log_result(result: dict[str, Any]) -> dict[str, Any]:
    gb_log(
        "step2.run ◀",
        source=result.get("source"),
        step_complete=result.get("step_complete"),
        question_progress=result.get("question_progress"),
        reply=result.get("reply"),
    )
    return result


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
        "step2.run ▶",
        user_input=user_input or None,
        answer=answer,
        answers_batch=answers_batch,
        confirm_step=confirm_step,
        step3_in=session.get("step3"),
    )

    if not step1_complete(session):
        return _log_result(
            _build_result(session, "请先完成步骤 1（明确目标）。", source="error"),
        )

    if not basic_profile_complete(session):
        return _log_result(
            _build_result(session, "请先完成步骤 2（基础信息）。", source="error"),
        )

    session = ensure_step3_goal(session)

    if confirm_step and not step3_info_complete(session):
        session = _store_answers_batch(session, answers_batch)
        session = _merge_answered_to_profile(session)
        return _confirm_step(session)

    if step3_info_complete(session):
        goal = (session.get("step3") or {}).get("goal_text") or ""
        return _log_result(
            _build_result(
                session,
                f"信息已收集完毕（目标：{goal}）。可进入步骤 4。",
                source="cached",
            ),
        )

    if answers_batch:
        for item in answers_batch:
            if isinstance(item, dict):
                session = step3_store_answer(session, item)
        if step3_pending_questions(session) and step3_all_answered(session):
            return _try_evaluate(session)
        return _log_result(
            _build_result(session, "请完成所有题目后再提交。", source="error"),
        )

    if answer and step3_pending_questions(session):
        session = step3_store_answer(session, answer)
        if step3_all_answered(session):
            return _try_evaluate(session)
        return _log_result(
            _build_result(session, "请通过问卷一次性提交全部回答。", source="error"),
        )

    if step3_pending_questions(session) and step3_all_answered(session):
        return _try_evaluate(session)

    s3 = session.get("step3") or {}
    needs_plan = (
        not step3_pending_questions(session)
        and s3.get("status") in ("pending", "collecting", None)
        and s3.get("sufficiency") != "enough"
    )
    if needs_plan:
        from _lib.llm import is_llm_available  # noqa: WPS433

        if not is_llm_available():
            return _log_result(_build_result(session, LLM_UNAVAILABLE_REPLY, source="error"))
        planned = _llm_plan(session)
        session, reply = planned
        if reply is None:
            return _log_result(_build_result(session, "处理失败，请重试。", source="error"))
        if not step3_pending_questions(session):
            if step3_info_complete(session):
                return _log_result(
                    _build_result(
                        session,
                        "步骤 3 不应在首次出题时直接结束；请重试生成问卷。",
                        source="error",
                    ),
                )
            return _log_result(
                _build_result(
                    session,
                    "AI 未返回有效问卷题目，请重试。",
                    source="error",
                ),
            )
        goal = (session.get("step3") or {}).get("goal_text") or ""
        session = record_turn(session, f"开始收集补充信息（目标：{goal}）", reply)
        return _log_result(_build_result(session, reply, source="plan"))

    return _log_result(
        _build_result(session, "请填写下方问卷并提交。", source="error"),
    )


def bootstrap() -> dict[str, Any]:
    from state import empty_session

    s = empty_session()
    s["current_step"] = STEP
    s["step1"] = {**s["step1"], "clarity": "clear", "goal_text": "示例目标"}
    s["step2"] = {**s["step2"], "status": "complete"}
    return run(s, "", None)
