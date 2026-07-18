"""Step 4 — 差距评估（调用 gap-diagnosis Agent）。"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from contract import STEP_GAP
from state import (
    goal_text,
    normalize_session,
    record_turn,
    step3_info_complete,
)

STEP = STEP_GAP
_AGENTS_ROOT = Path(__file__).resolve().parents[2]


def _load_gap_agent():
    agent_path = _AGENTS_ROOT / "gap-diagnosis" / "agent.py"
    gap_dir = str(_AGENTS_ROOT / "gap-diagnosis")
    if gap_dir not in sys.path:
        sys.path.insert(0, gap_dir)
    spec = importlib.util.spec_from_file_location("gap_diagnosis_agent", agent_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load gap-diagnosis agent: {agent_path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["gap_diagnosis_agent"] = mod
    spec.loader.exec_module(mod)
    return mod


def _profile_from_session(session: dict) -> dict[str, Any]:
    from _lib.planning import normalize_planning_profile

    goal = goal_text(session)
    profile_doc = get_user_profile_summary(session)
    basic = (session.get("step2") or {}).get("answers") or {}
    s3 = session.get("step3") or {}

    stated_facts: list[dict[str, Any]] = []
    if profile_doc:
        stated_facts.append({
            "id": "fact_profile",
            "text": profile_doc[:500],
            "kind": "fact",
            "source": "user_stated",
            "confidence": 0.8,
            "evidence_refs": [],
            "requires_confirmation": False,
        })

    identity: dict[str, str] = {}
    for key in ("occupation", "age_range", "region", "education"):
        val = basic.get(key, {})
        if isinstance(val, dict):
            text = str(val.get("value") or "").strip()
        else:
            text = str(val).strip()
        if text:
            field = "region_anchor" if key == "region" else key
            identity[field] = text

    readiness_status = "ready" if s3.get("sufficiency") == "enough" else "conditional"

    return normalize_planning_profile({
        "anchors": {
            "goal": goal,
            "current": profile_doc[:200] if profile_doc else "",
            "goal_clarity": "high" if goal else "low",
            "current_clarity": "medium" if profile_doc else "low",
        },
        "stated_facts": stated_facts,
        "current_state": {"identity": identity},
        "readiness": {
            "status": readiness_status,
            "confidence": 0.7 if readiness_status == "ready" else 0.55,
            "allow_proceed_with_assumptions": True,
        },
        "provenance": {"source_agent": "goal-bridge"},
    })


def get_user_profile_summary(session: dict) -> str:
    from user_profile import get_user_profile

    profile = get_user_profile(session)
    return str(profile.get("summary") or "").strip()


def run(session: dict, user_input: str, answer: dict | None = None) -> dict[str, Any]:
    session = normalize_session(session)

    if not step3_info_complete(session):
        return {
            "session": session,
            "reply": "请先完成信息收集步骤，再进行差距评估。",
            "current_step": STEP,
            "step_complete": False,
            "next_question": None,
            "source": "guard",
        }

    gap_mod = _load_gap_agent()
    profile = _profile_from_session(session)
    result = gap_mod.run(profile=profile, force=True)

    diagnosis = result.get("gap_diagnosis")
    session = dict(session)
    session["step4"] = {
        "status": "complete" if diagnosis else "pending",
        "data": {
            "gap_diagnosis": diagnosis,
            "profile": result.get("profile"),
            "validation_issues": result.get("validation_issues") or [],
        },
    }

    reply = result.get("output") or "差距评估完成。"
    if user_input.strip():
        session = record_turn(session, user_input, reply)

    return {
        "session": session,
        "reply": reply,
        "current_step": STEP,
        "step_complete": bool(diagnosis),
        "next_question": None,
        "gap_diagnosis": diagnosis,
        "source": (result.get("meta") or {}).get("source", "gap-diagnosis"),
    }
