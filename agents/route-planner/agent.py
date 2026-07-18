"""路线规划 Agent — 消费确认情景与差距，输出 AdaptiveRoadmap。"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import Any

_AGENTS_ROOT = Path(__file__).resolve().parents[1]
_AGENT_DIR = Path(__file__).resolve().parent
for path in (_AGENTS_ROOT, _AGENT_DIR):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from _lib.planning import (  # noqa: E402
    audit_document_text_fields,
    build_safety_system_prompt,
    normalize_adaptive_roadmap,
    validate_contract,
)
from _lib.planning.input import (  # noqa: E402
    _parse_json_payload,
    resolve_gap_diagnosis,
    resolve_planning_profile,
    resolve_scenario_set,
    selected_scenario,
)

from _lib.cli import resolve_cli_input  # noqa: E402
from roadmap_prompt import build_user_prompt  # noqa: E402

try:
    from _lib.llm import get_client, is_llm_available  # noqa: E402
except ImportError:

    def is_llm_available() -> bool:  # type: ignore[misc]
        return False

    def get_client():  # type: ignore[misc]
        return None


AGENT_ID = "route-planner"
VERSION = "0.2.0"


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _heuristic_roadmap(
    profile: dict[str, Any],
    gap_diagnosis: dict[str, Any] | None,
    scenario: dict[str, Any],
) -> dict[str, Any]:
    anchors = profile.get("anchors") or {}
    goal = anchors.get("goal") or scenario.get("title") or "目标"
    profile_id = profile.get("profile_id") or _new_id("profile")
    scenario_id = scenario.get("id") or "scenario_balanced"
    archetype = scenario.get("archetype") or "balanced"

    gap_items = (gap_diagnosis or {}).get("gaps") or []
    gap_actions = [
        f"针对差距「{g.get('title')}」：{ (g.get('closure_options') or ['制定验证实验'])[0] }"
        for g in gap_items[:3]
    ]
    if not gap_actions:
        gap_actions = ["列出与目标相关的 3 项可验证行动"]
    decisions = scenario.get("key_decisions") or ["设定周复盘"]

    staged = scenario.get("staged_outcomes") or []
    phases: list[dict[str, Any]] = []

    time_labels = ["month", "quarter", "quarter"]
    for i, stage in enumerate(staged[:4] or [{"phase": "阶段一", "outcome": goal, "timeframe": "1-3月"}]):
        phase_goal = stage.get("outcome") or goal
        phases.append({
            "id": f"phase_{i + 1}",
            "title": stage.get("phase") or f"第 {i + 1} 阶段",
            "goal": phase_goal,
            "time_window": {
                "label": time_labels[i] if i < len(time_labels) else "quarter",
                "start": "",
                "end": stage.get("timeframe") or "",
            },
            "actions": [
                {"id": f"action_{i + 1}_1", "description": gap_actions[i % len(gap_actions)], "effort": "中", "owner": "user"},
                {
                    "id": f"action_{i + 1}_2",
                    "description": decisions[i % len(decisions)],
                    "effort": "低",
                    "owner": "user",
                },
            ],
            "deliverables": [f"阶段 {i + 1} 可展示成果或记录"],
            "success_thresholds": [f"完成至少 1 项与「{phase_goal[:24]}」相关的可验证产出"],
            "resource_costs": {
                "time": {"conservative": "每周 5h", "balanced": "每周 8h", "aggressive": "每周 12h+"}.get(archetype, "每周 8h"),
                "money": "按用户约束（待确认）",
                "energy": "中等",
            },
            "milestones": [{
                "id": f"milestone_{i + 1}",
                "description": f"里程碑：{phase_goal[:40]}",
                "due": stage.get("timeframe") or f"阶段结束",
                "verifiable": True,
            }],
            "risk_signals": (scenario.get("early_warning_signals") or ["连续两周无进展"])[:2],
            "if_not_met": {
                "description": "若本阶段未达阈值，降档或延长窗口，避免硬推进",
                "adjustments": (scenario.get("reversible_actions") or ["缩小目标范围", "寻求外部反馈"])[:2],
            },
            "review_checkpoint": {
                "when": "阶段结束前 1 周",
                "questions": [
                    "本阶段最关键假设是否仍成立？",
                    "下一步是否仍符合所选情景的风险偏好？",
                ],
            },
        })

    return normalize_adaptive_roadmap({
        "roadmap_id": _new_id("roadmap"),
        "profile_id": profile_id,
        "scenario_id": scenario_id,
        "title": f"{scenario.get('title') or '自适应路线图'} — 执行计划",
        "summary": (
            f"基于「{archetype}」情景主线，将目标「{goal}」拆解为 {len(phases)} 个可复盘阶段。"
            "（启发式生成，建议结合用户约束确认。）"
        ),
        "phases": phases,
        "assumptions": [
            {
                "id": "asm_scenario",
                "text": f"用户已选择 {archetype} 情景作为规划主线",
                "kind": "assumption",
                "source": "user_inferred",
                "confidence": 0.7,
                "evidence_refs": [scenario_id],
                "requires_confirmation": False,
            }
        ],
        "version": 1,
        "revision_log": [],
        "meta": {"agent": AGENT_ID, "version": VERSION, "source": "heuristic"},
    })


def _generate_with_llm(
    profile: dict[str, Any],
    gap_diagnosis: dict[str, Any] | None,
    scenario: dict[str, Any],
    scenario_set: dict[str, Any] | None,
) -> dict[str, Any] | None:
    client = get_client()
    if client is None:
        return None
    system = build_safety_system_prompt("roadmap")
    prompt = build_user_prompt(profile, gap_diagnosis, scenario, scenario_set)
    try:
        raw = client.chat_json(prompt, system=system)
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(raw, dict):
        return None
    if not raw.get("profile_id"):
        raw["profile_id"] = profile.get("profile_id") or _new_id("profile")
    if not raw.get("scenario_id"):
        raw["scenario_id"] = scenario.get("id") or ""
    if not raw.get("roadmap_id"):
        raw["roadmap_id"] = _new_id("roadmap")
    raw["meta"] = {"agent": AGENT_ID, "version": VERSION, "source": "llm"}
    return normalize_adaptive_roadmap(raw)


def _format_output(roadmap: dict[str, Any]) -> str:
    phases = roadmap.get("phases") or []
    titles = " → ".join(p.get("title", "") for p in phases)
    return f"{roadmap.get('title', '路线图')}：{titles}"


def run(user_input: str = "", **kwargs) -> dict[str, Any]:
    payload = _parse_json_payload(user_input, kwargs)
    profile = resolve_planning_profile(payload)
    gap_diagnosis = resolve_gap_diagnosis(payload)
    scenario_set = resolve_scenario_set(payload)

    if not profile.get("profile_id"):
        profile["profile_id"] = _new_id("profile")

    scenario = selected_scenario(scenario_set)
    if scenario is None and payload.get("scenario"):
        scenario = payload["scenario"]

    if scenario is None:
        return {
            "output": "缺少已确认的情景主线（scenario_set.selected_scenario_id 或 scenario）。",
            "roadmap": None,
            "blocked": True,
            "meta": {"agent": AGENT_ID, "version": VERSION},
        }

    # 写回选线（便于下游引用）
    if scenario_set and scenario.get("id"):
        scenario_set["selected_scenario_id"] = scenario["id"]

    roadmap = None
    source = "heuristic"
    if is_llm_available() and not payload.get("heuristic_only"):
        roadmap = _generate_with_llm(profile, gap_diagnosis, scenario, scenario_set)
        if roadmap:
            source = "llm"

    if roadmap is None:
        roadmap = _heuristic_roadmap(profile, gap_diagnosis, scenario)

    issues = validate_contract(roadmap, "adaptive_roadmap")
    issues.extend(audit_document_text_fields(roadmap, ["title", "summary"]))

    return {
        "output": _format_output(roadmap),
        "roadmap": roadmap,
        "profile": profile,
        "gap_diagnosis": gap_diagnosis,
        "scenario_set": scenario_set,
        "selected_scenario": scenario,
        "validation_issues": issues,
        "meta": {"agent": AGENT_ID, "version": VERSION, "source": source},
    }


if __name__ == "__main__":
    default = json.dumps({
            "profile": {
                "profile_id": "profile_demo",
                "anchors": {
                    "goal": "6 个月内拿到海外前端面试机会",
                    "current": "国内 3 年前端",
                },
                "readiness": {"status": "conditional"},
            },
            "gap_diagnosis": {
                "diagnosis_id": "diag_demo",
                "gaps": [{
                    "id": "gap_1",
                    "title": "英文项目叙述能力不足",
                    "category": "skill",
                    "baseline": {"description": "无英文叙述练习", "indicators": []},
                    "target_threshold": {"description": "能完成 5 分钟英文项目介绍", "indicators": []},
                    "priority": "blocking",
                }],
            },
            "scenario_set": {
                "set_id": "set_demo",
                "selected_scenario_id": "scenario_balanced",
                "scenarios": [{
                    "id": "scenario_balanced",
                    "archetype": "balanced",
                    "title": "平衡路径",
                    "tagline": "主业+备考并行",
                    "premises": [{"text": "目标明确", "kind": "fact", "source": "user_stated", "confidence": 0.8}],
                    "key_decisions": ["每周固定 8h 练习"],
                    "staged_outcomes": [
                        {"phase": "基础期", "outcome": "完成英文项目稿", "timeframe": "1-2月"},
                        {"phase": "冲刺期", "outcome": "完成 2 次模拟面试", "timeframe": "3-5月"},
                    ],
                    "early_warning_signals": ["两周无练习"],
                    "reversible_actions": ["降低强度"],
                }],
            },
            "heuristic_only": True,
        }, ensure_ascii=False)
    raw = resolve_cli_input(default=default)
    print(json.dumps(run(raw), ensure_ascii=False, indent=2))
