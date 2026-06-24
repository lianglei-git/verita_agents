"""无 LLM 时的启发式路径与追问规划。"""

from __future__ import annotations

import re
from typing import Any

from collection import (
    baseline_missing,
    baseline_question_for,
    field_is_satisfied,
    is_baseline_complete,
)
from planner_guard import should_ask_field


def _infer_path_from_twin(twin: dict) -> dict[str, Any]:
    goal = (twin.get("growth") or {}).get("goal") or ""
    occ = (twin.get("identity") or {}).get("occupation") or "学习者"
    text = f"{goal} {occ}".lower()

    milestones = ["夯实基础表达", "场景化实战", "目标冲刺"]
    required: list[str] = []
    blocking: list[dict[str, str]] = []

    if re.search(r"面试|interview|offer", text, re.I):
        milestones = ["自我介绍与项目叙述", "技术深挖问答", "模拟面试冲刺"]
        required = [
            "scenario.interview_type",
            "scenario.target_market",
            "growth.timeline_urgency",
            "capability.speaking",
        ]
        blocking = [
            {"field": "scenario.interview_type", "reason": "面试形式决定练习话术"},
            {"field": "capability.speaking", "reason": "面试场景核心在口语表达"},
        ]
    elif re.search(r"雅思|托福|ielts|toefl|留学", text, re.I):
        milestones = ["考试题型熟悉", "专项突破", "模考与冲刺"]
        required = ["scenario.target_exam", "scenario.target_score_band", "growth.deadline"]
        blocking = [
            {"field": "scenario.target_exam", "reason": "考试类型决定备考策略"},
        ]
    elif re.search(r"远程|remote|协作", text, re.I):
        milestones = ["工作区沟通", "会议表达", "异步写作"]
        required = ["scenario.work_mode", "capability.writing", "capability.speaking"]
        blocking = [
            {"field": "scenario.work_mode", "reason": "远程协作侧重异步或同步沟通"},
        ]
    else:
        required = ["growth.timeline_urgency", "capability.bottleneck_for_goal"]
        blocking = [
            {"field": "growth.timeline_urgency", "reason": "时间压力影响路线节奏"},
        ]

    return {
        "title": f"达成「{goal or '英语学习目标'}」的定制路线",
        "summary": f"基于目标「{goal}」与身份「{occ}」推断的学习路径（启发式）。",
        "interpretation": goal or "目标尚待明确",
        "milestones": milestones,
        "confidence": 0.55 if goal else 0.35,
        "required_fields": required,
        "blocking_gaps": blocking,
        "blocking_fields": [b["field"] for b in blocking],
        "optional_gaps": [],
    }


FALLBACK_QUESTIONS: dict[str, dict[str, Any]] = {
    "scenario.interview_type": {
        "question": "你准备的面试更偏哪一类？",
        "hint": "行为面 / 技术深挖 / 全英文 HR / 混合",
        "why": "不同面试形式需要不同的表达训练。",
        "depth": 4,
        "phase": "scenario",
        "skippable": False,
    },
    "scenario.target_market": {
        "question": "你的目标市场或地区是哪里？",
        "hint": "美国 / 欧洲 / 东南亚 / 国内外企 / 其他",
        "why": "地区影响面试风格与用语习惯。",
        "depth": 4,
        "phase": "scenario",
        "skippable": True,
    },
    "growth.timeline_urgency": {
        "question": "你大概什么时候需要用到英语达成目标？",
        "hint": "1 个月内 / 1–3 个月 / 半年以上 / 暂无硬性期限",
        "why": "时间线决定路线节奏与强度。",
        "depth": 3,
        "phase": "path_blocking",
        "skippable": True,
    },
    "capability.speaking": {
        "question": "口语自评（0–100，不及格≈40，良好≈70）",
        "hint": "0-100",
        "why": "口语水平是面试类路径的关键校准项。",
        "depth": 5,
        "phase": "calibration",
        "skippable": True,
    },
    "scenario.target_exam": {
        "question": "你准备哪类考试？",
        "hint": "雅思 / 托福 / GRE / 其他",
        "why": "考试类型决定专项训练内容。",
        "depth": 4,
        "phase": "scenario",
        "skippable": False,
    },
    "scenario.target_score_band": {
        "question": "你的目标分数大概是多少？",
        "hint": "例：雅思 7.0、托福 100",
        "why": "目标分决定备考强度与周期。",
        "depth": 5,
        "phase": "calibration",
        "skippable": True,
    },
    "growth.deadline": {
        "question": "考试或申请的截止日期大概是什么时候？",
        "hint": "例：2025 年 12 月",
        "why": "截止日期影响阶段安排。",
        "depth": 3,
        "phase": "path_blocking",
        "skippable": True,
    },
    "scenario.work_mode": {
        "question": "你的远程协作更偏哪种？",
        "hint": "异步文字为主 / 实时会议为主 / 两者兼有",
        "why": "工作模式决定听说读写的优先级。",
        "depth": 4,
        "phase": "scenario",
        "skippable": False,
    },
    "capability.writing": {
        "question": "写作自评（0–100）",
        "hint": "0-100",
        "why": "远程协作常依赖书面表达。",
        "depth": 5,
        "phase": "calibration",
        "skippable": True,
    },
}


def _path_confirm_question(path: dict) -> dict[str, Any]:
    title = path.get("title") or "当前推断路线"
    summary = path.get("summary") or ""
    milestones = path.get("milestones") or []
    ms = " → ".join(milestones[:3]) if milestones else ""
    return {
        "field": "collection.path_confirmed",
        "question": f"根据你的情况，我推断的路线是：「{title}」。{summary} 阶段：{ms}。这条方向符合你的预期吗？",
        "hint": "符合 / 需要调整（请说明）",
        "why": "确认路径后，后续问题会围绕该路线由浅入深展开。",
        "depth": 2,
        "phase": "path_confirm",
        "skippable": False,
        "choices": ["符合", "需要调整"],
    }


def _field_filled(twin: dict, field: str) -> bool:
    return field_is_satisfied(twin, field)


def plan_fallback(twin: dict, collection: dict) -> dict[str, Any]:
    path = collection.get("path") or _infer_path_from_twin(twin)
    path_confirmed = bool(collection.get("path_confirmed"))

    next_question: dict[str, Any] | None = None

    if not is_baseline_complete(twin):
        for field in baseline_missing(twin):
            if should_ask_field(twin, collection, field):
                next_question = baseline_question_for(field)
                break
    elif not path_confirmed and should_ask_field(twin, collection, "collection.path_confirmed"):
        next_question = _path_confirm_question(path)
    else:
        for gap in path.get("blocking_gaps") or []:
            field = gap["field"] if isinstance(gap, dict) else gap
            if should_ask_field(twin, collection, field):
                spec = FALLBACK_QUESTIONS.get(field, {})
                next_question = {
                    "field": field,
                    "question": spec.get("question", f"请补充：{field}"),
                    "hint": spec.get("hint", ""),
                    "why": spec.get("why", gap.get("reason", "") if isinstance(gap, dict) else ""),
                    "depth": spec.get("depth", 4),
                    "phase": spec.get("phase", "path_blocking"),
                    "skippable": spec.get("skippable", True),
                }
                break

        if not next_question:
            for field in path.get("required_fields") or []:
                if should_ask_field(twin, collection, field):
                    spec = FALLBACK_QUESTIONS.get(field, {})
                    next_question = {
                        "field": field,
                        "question": spec.get("question", f"请补充：{field}"),
                        "hint": spec.get("hint", ""),
                        "why": spec.get("why", "完善路径所需信息"),
                        "depth": spec.get("depth", 4),
                        "phase": spec.get("phase", "scenario"),
                        "skippable": True,
                    }
                    break

    blocking_fields = [
        g["field"] if isinstance(g, dict) else g
        for g in (path.get("blocking_gaps") or [])
        if not _field_filled(twin, g["field"] if isinstance(g, dict) else g)
    ]

    return {
        "path": path,
        "next_question": next_question,
        "path_confirm_needed": not path_confirmed and is_baseline_complete(twin),
        "assumptions": [],
        "release_recommendation": "continue",
        "blocking_fields": blocking_fields,
        "source": "heuristic",
    }
