"""Step 4 — 差距评估（占位，待实现）。"""

from __future__ import annotations

from typing import Any

from contract import STEP_GAP
from state import normalize_session

STEP = STEP_GAP
NOT_IMPLEMENTED = "步骤 4「差距评估」尚未实现。"


def run(session: dict, user_input: str, answer: dict | None = None) -> dict[str, Any]:
    session = normalize_session(session)
    return {
        "session": session,
        "reply": NOT_IMPLEMENTED,
        "current_step": STEP,
        "step_complete": False,
        "next_question": None,
        "source": "stub",
    }
