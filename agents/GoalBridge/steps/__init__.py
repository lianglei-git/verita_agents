"""GoalBridge 步骤注册与调度。"""

from __future__ import annotations

from typing import Any, Callable

from contract import STEP_BASIC, STEP_GAP, STEP_GOAL, STEP_INFO
from debug_log import gb_log
from steps import step1_goal, step2_basic, step2_info, step3_gap

StepRunner = Callable[..., dict[str, Any]]

STEP_HANDLERS: dict[int, StepRunner] = {
    STEP_GOAL: step1_goal.run,
    STEP_BASIC: step2_basic.run,
    STEP_INFO: step2_info.run,
    STEP_GAP: step3_gap.run,
}


def get_step_handler(step: int) -> StepRunner:
    return STEP_HANDLERS.get(step, step1_goal.run)


def run_current_step(
    session: dict,
    user_input: str,
    answer: dict | None = None,
    answers_batch: list[dict] | None = None,
    confirm_step: bool = False,
) -> dict[str, Any]:
    step = int(session.get("current_step") or STEP_GOAL)
    handler = get_step_handler(step)
    gb_log("steps.dispatch", step=step, handler=handler.__module__)
    if step in (STEP_GOAL, STEP_BASIC, STEP_INFO):
        return handler(
            session,
            user_input,
            answer,
            answers_batch=answers_batch,
            confirm_step=confirm_step,
        )
    return handler(session, user_input, answer)
