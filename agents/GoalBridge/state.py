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


def empty_step2_basic() -> dict[str, Any]:
    return {
        "status": "pending",
        "answers": {},
    }


def empty_step3_info() -> dict[str, Any]:
    return {
        "status": "pending",
        "sufficiency": "pending",
        "goal_text": "",
        "pending_questions": [],
        "answers": {},
        "ui_mode": UI_MODE_SURVEY,
        "data": {},
    }


def empty_step4_gap() -> dict[str, Any]:
    return {"status": "pending", "data": {}}


def empty_session() -> dict[str, Any]:
    return {
        "current_step": STEP_GOAL,
        "step1": empty_step1(),
        "step2": empty_step2_basic(),
        "step3": empty_step3_info(),
        "step4": empty_step4_gap(),
        "user_profile": empty_user_profile(),
        "turns": [],
    }


def _migrate_legacy_session(raw: dict) -> dict:
    """兼容旧版：step2=信息收集、step3=差距评估。"""
    out = dict(raw)
    legacy_s2 = out.get("step2") or {}
    if legacy_s2.get("sufficiency") is not None or legacy_s2.get("goal_text"):
        if not (out.get("step3") or {}).get("sufficiency"):
            out["step3"] = legacy_s2
        out["step2"] = empty_step2_basic()
        cs = int(out.get("current_step") or 1)
        if cs == 2 and legacy_s2.get("status") == "complete":
            out["current_step"] = 3
        elif cs == 3:
            out["current_step"] = 4
    legacy_s3 = out.get("step3") or {}
    if (
        legacy_s3.get("sufficiency") is None
        and legacy_s3.get("status") == "pending"
        and not legacy_s3.get("pending_questions")
        and not out.get("step4")
    ):
        out["step4"] = legacy_s3
    return out


def normalize_session(raw: dict | None) -> dict[str, Any]:
    base = empty_session()
    if not raw:
        return base
    raw = _migrate_legacy_session(raw)
    base["current_step"] = int(raw.get("current_step") or STEP_GOAL)
    s1 = {**empty_step1(), **(raw.get("step1") or {})}
    if not isinstance(s1.get("pending_questions"), list):
        s1["pending_questions"] = []
    if not isinstance(s1.get("answers"), dict):
        s1["answers"] = {}
    base["step1"] = s1

    s2 = {**empty_step2_basic(), **(raw.get("step2") or {})}
    if not isinstance(s2.get("answers"), dict):
        s2["answers"] = {}
    base["step2"] = s2

    s3 = {**empty_step3_info(), **(raw.get("step3") or {})}
    if not isinstance(s3.get("pending_questions"), list):
        s3["pending_questions"] = []
    if not isinstance(s3.get("answers"), dict):
        s3["answers"] = {}
    if not isinstance(s3.get("data"), dict):
        s3["data"] = {}
    base["step3"] = s3

    base["step4"] = {**empty_step4_gap(), **(raw.get("step4") or {})}
    base["user_profile"] = normalize_user_profile(raw.get("user_profile"))
    base["turns"] = list(raw.get("turns") or [])
    return base


def record_turn(session: dict, user_text: str, reply: str) -> dict:
    turns = list(session.get("turns") or [])
    turns.append({"user": user_text, "assistant": reply})
    out = deepcopy(session)
    out["turns"] = turns[-30:]
    return out


# --- Step 1 目标 ---
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
    answers[qid] = {"type": answer.get("type"), "value": answer.get("value")}
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


# --- Step 2 基础画像 ---
def basic_profile_complete(session: dict) -> bool:
    return (session.get("step2") or {}).get("status") == "complete"


def set_basic_profile(session: dict, **patch: Any) -> dict:
    out = deepcopy(session)
    s2 = dict(out.get("step2") or empty_step2_basic())
    for key, val in patch.items():
        if key in s2 or key in ("status", "answers"):
            s2[key] = val
    out["step2"] = s2
    return out


def basic_answers_map(session: dict) -> dict:
    return dict((session.get("step2") or {}).get("answers") or {})


def basic_store_answer(session: dict, answer: dict) -> dict:
    qid = str(answer.get("question_id") or "").strip()
    if not qid:
        return session
    answers = basic_answers_map(session)
    answers[qid] = {"type": answer.get("type"), "value": answer.get("value")}
    return set_basic_profile(session, answers=answers)


def basic_store_batch(session: dict, answers_batch: list[dict]) -> dict:
    for item in answers_batch:
        if isinstance(item, dict) and item.get("question_id"):
            session = basic_store_answer(session, item)
    return session


# --- Step 3 信息收集（AI）---
def set_step3_info(session: dict, **patch: Any) -> dict:
    out = deepcopy(session)
    s3 = dict(out.get("step3") or empty_step3_info())
    for key, val in patch.items():
        if key in s3 or key in (
            "status",
            "sufficiency",
            "goal_text",
            "pending_questions",
            "answers",
            "ui_mode",
            "data",
        ):
            s3[key] = val
    out["step3"] = s3
    return out


def step3_pending_questions(session: dict) -> list[dict]:
    return list((session.get("step3") or {}).get("pending_questions") or [])


def step3_answers_map(session: dict) -> dict:
    return dict((session.get("step3") or {}).get("answers") or {})


def step3_store_answer(session: dict, answer: dict) -> dict:
    qid = str(answer.get("question_id") or "").strip()
    if not qid:
        return session
    answers = step3_answers_map(session)
    answers[qid] = {"type": answer.get("type"), "value": answer.get("value")}
    return set_step3_info(session, answers=answers)


def step3_all_answered(session: dict) -> bool:
    pending = step3_pending_questions(session)
    if not pending:
        return False
    answers = step3_answers_map(session)
    for q in pending:
        if q.get("required", True) and q["id"] not in answers:
            return False
    return True


def step3_info_complete(session: dict) -> bool:
    s3 = session.get("step3") or {}
    return s3.get("sufficiency") == "enough" and s3.get("status") == "complete"


def ensure_step3_goal(session: dict) -> dict:
    s3 = session.get("step3") or {}
    if str(s3.get("goal_text") or "").strip():
        return session
    g = goal_text(session)
    if g:
        return set_step3_info(session, goal_text=g)
    return session


# 兼容旧名（step2_info 模块过渡期可删）
step2_complete = step3_info_complete
set_step2 = set_step3_info
step2_pending_questions = step3_pending_questions
step2_answers_map = step3_answers_map
step2_store_answer = step3_store_answer
step2_all_answered = step3_all_answered
ensure_step2_goal = ensure_step3_goal
