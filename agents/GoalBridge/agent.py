"""GoalBridge Agent — 四步架构：目标 → 基础画像 → AI 信息收集 → 差距评估。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_AGENT_DIR = Path(__file__).resolve().parent
_AGENTS_ROOT = _AGENT_DIR.parent
for path in (_AGENTS_ROOT, _AGENT_DIR):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from basic_profile import get_schema_for_client  # noqa: E402
from contract import STEP_INFO, STEP_LABELS  # noqa: E402
from debug_log import gb_log  # noqa: E402
from state import (  # noqa: E402
    basic_profile_complete,
    empty_session,
    goal_text,
    normalize_session,
    step1_complete,
    step3_info_complete,
)
from steps import run_current_step  # noqa: E402

try:
    from _lib.llm import is_llm_available  # noqa: E402
except ImportError:

    def is_llm_available() -> bool:  # type: ignore[misc]
        return False


def _parse_payload(user_input: str, kwargs: dict) -> dict:
    if kwargs:
        return kwargs
    if not user_input.strip():
        return {}
    try:
        data = json.loads(user_input)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    return {"message": user_input}


def _extract_input(payload: dict) -> tuple[str, dict | None, list[dict] | None]:
    if "answers_batch" in payload and isinstance(payload.get("answers_batch"), list):
        return "", None, payload["answers_batch"]
    answer = payload.get("answer")
    if isinstance(answer, dict) and answer:
        return "", answer, None
    for key in ("message", "story"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip(), None, None
    legacy = payload.get("answers") or {}
    if isinstance(legacy.get("reply"), str) and legacy["reply"].strip():
        return legacy["reply"].strip(), None, None
    return "", None, None


def _summary(session: dict, step: int, step_complete: bool) -> str:
    label = STEP_LABELS.get(step, f"步骤{step}")
    if step == 1:
        goal = goal_text(session)
        if step_complete and goal:
            return f"步骤 1 完成 · 目标：{goal}"
        clarity = (session.get("step1") or {}).get("clarity") or "pending"
        return f"{label} · {clarity}"
    if step == 2:
        if step_complete:
            return f"步骤 2 完成 · 基础信息已记录"
        return label
    if step == 3:
        s3 = session.get("step3") or {}
        g = str(s3.get("goal_text") or goal_text(session) or "")
        if step_complete:
            return f"步骤 3 完成 · 已收集补充信息"
        suff = s3.get("sufficiency") or "pending"
        return f"{label} · {suff}" + (f" · {g}" if g else "")
    return label


def run(user_input: str, **kwargs) -> dict:
    payload = _parse_payload(user_input, kwargs)
    session = normalize_session(payload.get("session"))
    if payload.get("reset"):
        session = empty_session()

    text, answer, answers_batch = _extract_input(payload)
    confirm_step = bool(payload.get("confirm_step"))
    gb_log(
        "agent.run ▶ 输入",
        payload=payload,
        message=text or None,
        answer=answer,
        answers_batch=answers_batch,
        confirm_step=confirm_step,
        session_in=session,
        reset=bool(payload.get("reset")),
    )

    turn = run_current_step(
        session,
        text,
        answer,
        answers_batch=answers_batch,
        confirm_step=confirm_step,
    )
    session = turn["session"]
    step = int(session.get("current_step") or 1)
    llm_calls = list(turn.get("llm_calls") or [])

    # 进入步骤 3 且尚无问卷：自动调用 AI 出题
    s3 = session.get("step3") or {}
    need_plan = (
        step == STEP_INFO
        and basic_profile_complete(session)
        and not s3.get("pending_questions")
        and s3.get("sufficiency") != "enough"
        and s3.get("status") != "complete"
    )
    if need_plan and not answers_batch and not confirm_step:
        plan_turn = run_current_step(session, "", None, answers_batch=None)
        if plan_turn.get("source") not in ("error",):
            llm_calls.extend(plan_turn.get("llm_calls") or [])
            turn = plan_turn
            session = turn["session"]
            step = int(session.get("current_step") or STEP_INFO)

    if step == 1:
        step_complete = step1_complete(session)
    elif step == 2:
        step_complete = basic_profile_complete(session)
    elif step == 3:
        step_complete = step3_info_complete(session)
    else:
        step_complete = bool(turn.get("step_complete"))

    next_questions = list(turn.get("next_questions") or [])
    if not next_questions and turn.get("next_question"):
        next_questions = [turn["next_question"]]

    basic_schema = turn.get("basic_profile_schema") or get_schema_for_client()

    result = {
        "output": _summary(session, step, step_complete),
        "reply": turn.get("reply") or "",
        "session": session,
        "current_step": step,
        "step_complete": step_complete,
        "next_question": turn.get("active_question") or turn.get("next_question"),
        "next_questions": next_questions,
        "active_question": turn.get("active_question"),
        "question_progress": turn.get("question_progress"),
        "ui_mode": turn.get("ui_mode"),
        "user_profile": session.get("user_profile"),
        "llm_calls": llm_calls,
        "meta": {
            "agent": "goal-bridge",
            "version": "1.4.0-basic-profile",
            "turn_source": turn.get("source"),
            "llm_available": is_llm_available(),
            "step_label": STEP_LABELS.get(step, ""),
            "ui_mode": turn.get("ui_mode"),
            "basic_profile_schema": basic_schema,
        },
    }
    gb_log(
        "agent.run ◀ 输出",
        source=turn.get("source"),
        step=step,
        step_complete=step_complete,
        reply=result["reply"],
        question_progress=turn.get("question_progress"),
        active_question=turn.get("active_question"),
        next_questions_count=len(next_questions),
        step1=session.get("step1"),
        step2=session.get("step2"),
        step3=session.get("step3"),
        meta=result["meta"],
    )
    return result


if __name__ == "__main__":
    raw = sys.argv[1] if len(sys.argv) > 1 else json.dumps({"reset": True}, ensure_ascii=False)
    print(json.dumps(run(raw), ensure_ascii=False, indent=2))
