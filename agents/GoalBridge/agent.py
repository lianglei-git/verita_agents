"""GoalBridge Agent — 三步架构，当前实现 Step 1–2。"""

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

from contract import STEP_LABELS  # noqa: E402
from debug_log import gb_log  # noqa: E402
from state import empty_session, goal_text, normalize_session, step1_complete, step2_complete  # noqa: E402
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
    batch = payload.get("answers_batch")
    if isinstance(batch, list) and batch:
        return "", None, batch
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
        s2 = session.get("step2") or {}
        g = str(s2.get("goal_text") or goal_text(session) or "")
        if step_complete:
            return f"步骤 2 完成 · 已收集基础信息"
        suff = s2.get("sufficiency") or "pending"
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

    # 进入步骤 2 且尚无问卷：自动调用 AI 出题（步骤 1 刚完成时也触发）
    s2 = session.get("step2") or {}
    need_plan = (
        step == 2
        and not s2.get("pending_questions")
        and s2.get("sufficiency") != "enough"
        and s2.get("status") != "complete"
    )
    if need_plan and not answers_batch:
        plan_turn = run_current_step(session, "", None, answers_batch=None)
        if plan_turn.get("source") not in ("error",):
            llm_calls.extend(plan_turn.get("llm_calls") or [])
            turn = plan_turn
            session = turn["session"]
            step = int(session.get("current_step") or 2)

    # step_complete 表示「当前步骤」是否完成，不能沿用上一步 handler 的返回值
    if step == 1:
        step_complete = step1_complete(session)
    elif step == 2:
        step_complete = step2_complete(session)
    else:
        step_complete = bool(turn.get("step_complete"))

    next_questions = list(turn.get("next_questions") or [])
    if not next_questions and turn.get("next_question"):
        next_questions = [turn["next_question"]]

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
            "version": "1.3.0-profile",
            "turn_source": turn.get("source"),
            "llm_available": is_llm_available(),
            "step_label": STEP_LABELS.get(step, ""),
            "ui_mode": turn.get("ui_mode"),
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
        meta=result["meta"],
    )
    return result


if __name__ == "__main__":
    raw = sys.argv[1] if len(sys.argv) > 1 else json.dumps({"reset": True}, ensure_ascii=False)
    print(json.dumps(run(raw), ensure_ascii=False, indent=2))
