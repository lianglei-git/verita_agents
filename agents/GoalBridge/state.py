"""GoalBridge 会话状态 — 按步骤拆分存储。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from contract import STEP_GOAL, UI_MODE_SEQUENTIAL, UI_MODE_SURVEY
from user_profile import empty_user_profile, normalize_user_profile


def empty_step1() -> dict[str, Any]:
    return {
        "clarity": "pending",
        "goal_text": "",
        "pending_questions": [],
        "answers": {},
        "ui_mode": UI_MODE_SEQUENTIAL,
    }


def empty_step2() -> dict[str, Any]:
    return {
        "status": "pending",
        "sufficiency": "pending",
        "goal_text": "",
        "pending_questions": [],
        "answers": {},
        "ui_mode": UI_MODE_SURVEY,
        "data": {},
    }


def empty_step3() -> dict[str, Any]:
    return {"status": "pending", "data": {}}


def empty_session() -> dict[str, Any]:
    return {
        "current_step": STEP_GOAL,
        "step1": empty_step1(),
        "step2": empty_step2(),
        "step3": empty_step3(),
        "user_profile": empty_user_profile(),
        "turns": [],
    }


def normalize_session(raw: dict | None) -> dict[str, Any]:
    base = empty_session()
    if not raw:
        return base
    base["current_step"] = int(raw.get("current_step") or STEP_GOAL)
    s1 = {**empty_step1(), **(raw.get("step1") or {})}
    if not isinstance(s1.get("pending_questions"), list):
        s1["pending_questions"] = []
    if not isinstance(s1.get("answers"), dict):
        s1["answers"] = {}
    base["step1"] = s1
    base["step2"] = {**empty_step2(), **(raw.get("step2") or {})}
    s2 = base["step2"]
    if not isinstance(s2.get("pending_questions"), list):
        s2["pending_questions"] = []
    if not isinstance(s2.get("answers"), dict):
        s2["answers"] = {}
    if not isinstance(s2.get("data"), dict):
        s2["data"] = {}
    base["step2"] = s2
    base["step3"] = {**empty_step3(), **(raw.get("step3") or {})}
    base["user_profile"] = normalize_user_profile(raw.get("user_profile"))
    base["turns"] = list(raw.get("turns") or [])
    return base


def record_turn(session: dict, user_text: str, reply: str) -> dict:
    turns = list(session.get("turns") or [])
    turns.append({"user": user_text, "assistant": reply})
    out = deepcopy(session)
    out["turns"] = turns[-30:]
    return out


def step1_complete(session: dict) -> bool:
    s1 = session.get("step1") or {}
    return s1.get("clarity") == "clear" and bool(str(s1.get("goal_text") or "").strip())


def set_step1(session: dict, **patch: Any) -> dict:
    out = deepcopy(session)
    s1 = dict(out.get("step1") or empty_step1())
    for key, val in patch.items():
        if key in s1 or key in ("clarity", "goal_text", "pending_questions", "answers", "ui_mode"):
            s1[key] = val
    out["step1"] = s1
    return out


def store_answer(session: dict, answer: dict) -> dict:
    qid = str(answer.get("question_id") or "").strip()
    if not qid:
        return session
    answers = dict((session.get("step1") or {}).get("answers") or {})
    answers[qid] = {
        "type": answer.get("type"),
        "value": answer.get("value"),
    }
    return set_step1(session, answers=answers)


def pending_questions(session: dict) -> list[dict]:
    return list((session.get("step1") or {}).get("pending_questions") or [])


def answers_map(session: dict) -> dict:
    return dict((session.get("step1") or {}).get("answers") or {})


def all_pending_answered(session: dict) -> bool:
    pending = pending_questions(session)
    if not pending:
        return False
    answers = answers_map(session)
    for q in pending:
        if q.get("required", True) and q["id"] not in answers:
            return False
    return True


def active_question(session: dict) -> dict | None:
    for q in pending_questions(session):
        if q["id"] not in answers_map(session):
            return q
    return None


def question_progress(session: dict) -> dict[str, int]:
    pending = pending_questions(session)
    answered = sum(1 for q in pending if q["id"] in answers_map(session))
    return {"answered": answered, "total": len(pending)}


def goal_text(session: dict) -> str:
    s1 = session.get("step1") or {}
    return str(s1.get("goal_text") or "").strip()


def set_step2(session: dict, **patch: Any) -> dict:
    out = deepcopy(session)
    s2 = dict(out.get("step2") or empty_step2())
    for key, val in patch.items():
        if key in s2 or key in (
            "status",
            "sufficiency",
            "goal_text",
            "pending_questions",
            "answers",
            "ui_mode",
            "data",
        ):
            s2[key] = val
    out["step2"] = s2
    return out


def step2_pending_questions(session: dict) -> list[dict]:
    return list((session.get("step2") or {}).get("pending_questions") or [])


def step2_answers_map(session: dict) -> dict:
    return dict((session.get("step2") or {}).get("answers") or {})


def step2_store_answer(session: dict, answer: dict) -> dict:
    qid = str(answer.get("question_id") or "").strip()
    if not qid:
        return session
    answers = step2_answers_map(session)
    answers[qid] = {"type": answer.get("type"), "value": answer.get("value")}
    return set_step2(session, answers=answers)


def step2_all_answered(session: dict) -> bool:
    pending = step2_pending_questions(session)
    if not pending:
        return False
    answers = step2_answers_map(session)
    for q in pending:
        if q.get("required", True) and q["id"] not in answers:
            return False
    return True


def step2_complete(session: dict) -> bool:
    s2 = session.get("step2") or {}
    return s2.get("sufficiency") == "enough" and s2.get("status") == "complete"


def ensure_step2_goal(session: dict) -> dict:
    s2 = session.get("step2") or {}
    if str(s2.get("goal_text") or "").strip():
        return session
    g = goal_text(session)
    if g:
        return set_step2(session, goal_text=g)
    return session
