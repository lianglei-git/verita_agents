"""GoalBridge 前后端共享契约 — 步骤、题型、问题结构。"""

from __future__ import annotations

from typing import Any, Literal

# --- 步骤 ---
STEP_GOAL = 1
STEP_BASIC = 2
STEP_INFO = 3
STEP_GAP = 4

STEP_LABELS: dict[int, str] = {
    STEP_GOAL: "目标是否明确",
    STEP_BASIC: "基础信息",
    STEP_INFO: "信息收集",
    STEP_GAP: "差距评估",
}

# --- 目标清晰度（Step 1）---
GoalClarity = Literal["pending", "unclear", "clear"]

# --- 题型（与前端 types.js 一致）---
QUESTION_OPEN = "open"
QUESTION_SINGLE = "single"
QUESTION_MULTI = "multi"

# --- 展示模式（前端）---
UI_MODE_SEQUENTIAL = "sequential"
UI_MODE_SURVEY = "survey"

UiMode = Literal["sequential", "survey"]


def empty_question() -> dict[str, Any]:
    return {
        "id": "",
        "step": STEP_GOAL,
        "type": QUESTION_OPEN,
        "text": "",
        "options": [],
        "required": True,
    }


def _normalize_options(raw_options: list | None) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for i, o in enumerate(raw_options or []):
        if isinstance(o, str) and o.strip():
            label = o.strip()
            out.append({"id": f"opt_{i}", "label": label})
        elif isinstance(o, dict) and str(o.get("label", "")).strip():
            out.append({
                "id": str(o.get("id", i)),
                "label": str(o.get("label", "")).strip(),
            })
    return out


def normalize_question(raw: dict | None) -> dict[str, Any] | None:
    if not raw:
        return None
    text = str(
        raw.get("text") or raw.get("question") or raw.get("label") or ""
    ).strip()
    if not text:
        return None
    q = empty_question()
    q["id"] = str(raw.get("id") or "q").strip() or "q"
    q["step"] = int(raw.get("step") or STEP_GOAL)
    qtype = str(raw.get("type") or QUESTION_OPEN).strip()
    if qtype not in (QUESTION_OPEN, QUESTION_SINGLE, QUESTION_MULTI):
        qtype = QUESTION_OPEN
    q["type"] = qtype
    q["text"] = text
    q["required"] = bool(raw.get("required", True))
    q["options"] = _normalize_options(raw.get("options"))
    if qtype in (QUESTION_SINGLE, QUESTION_MULTI) and not q["options"]:
        q["type"] = QUESTION_OPEN
    return q


def normalize_questions(raw: list | None) -> list[dict[str, Any]]:
    if not raw:
        return []
    out: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    for i, item in enumerate(raw):
        q = normalize_question(item)
        if not q:
            continue
        qid = q["id"]
        if not qid or qid == "q" or qid in used_ids:
            qid = f"q{i + 1}"
        while qid in used_ids:
            qid = f"q{i + 1}_{len(used_ids)}"
        q["id"] = qid
        used_ids.add(qid)
        out.append(q)
    return out
