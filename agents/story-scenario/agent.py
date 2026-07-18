"""故事情景 Agent — 从 PlanningProfile + 差距生成三情景推演。"""

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
    SCENARIO_ARCHETYPES,
    audit_document_text_fields,
    build_safety_system_prompt,
    empty_scenario_set,
    normalize_scenario_set,
    validate_contract,
)
from _lib.planning.input import (  # noqa: E402
    _parse_json_payload,
    resolve_gap_diagnosis,
    resolve_planning_profile,
)

from _lib.cli import resolve_cli_input  # noqa: E402
from simulate_prompt import build_user_prompt  # noqa: E402

try:
    from _lib.llm import get_client, is_llm_available  # noqa: E402
except ImportError:

    def is_llm_available() -> bool:  # type: ignore[misc]
        return False

    def get_client():  # type: ignore[misc]
        return None


AGENT_ID = "story-scenario"
VERSION = "0.2.0"

_ARCHETYPE_LABELS = {
    "conservative": "稳健路径",
    "balanced": "平衡路径",
    "aggressive": "进取路径",
}


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _claim(text: str, kind: str = "assumption", confidence: float = 0.55) -> dict[str, Any]:
    return {
        "id": _new_id("prem"),
        "text": text,
        "kind": kind,
        "source": "model_assumed" if kind != "fact" else "user_stated",
        "confidence": confidence,
        "evidence_refs": [],
        "requires_confirmation": kind in ("assumption", "uncertainty"),
    }


def _heuristic_scenarios(
    profile: dict[str, Any],
    gap_diagnosis: dict[str, Any] | None,
) -> dict[str, Any]:
    anchors = profile.get("anchors") or {}
    goal_raw = anchors.get("goal") or ""
    current_raw = anchors.get("current") or ""
    goal = goal_raw or "未明确目标"
    current = current_raw or "未描述现状"
    profile_id = profile.get("profile_id") or _new_id("profile")
    gap_id = (gap_diagnosis or {}).get("diagnosis_id") or ""

    gap_titles = [g.get("title", "") for g in (gap_diagnosis or {}).get("gaps") or []]
    gap_hint = gap_titles[0] if gap_titles else "核心能力/资源差距"

    scenarios: list[dict[str, Any]] = []
    templates = {
        "conservative": {
            "title": f"稳健推进：在现有基础上渐进补齐",
            "tagline": "低风险、可逆，节奏慢但稳",
            "decisions": ["保持当前主业稳定", "利用碎片时间补齐短板", "优先可验证的小步实验"],
            "costs": ["进展较慢", "可能错过部分窗口期"],
            "failures": ["动力不足导致拖延", "目标被日常事务淹没"],
            "warnings": ["连续 2 周无可见产出", "对目标表述开始模糊"],
            "reversible": ["缩减每周投入", "切换为更小的子目标"],
        },
        "balanced": {
            "title": f"平衡路径：主业+系统备考并行",
            "tagline": "中等风险，兼顾稳定与突破",
            "decisions": ["设定固定学习/演练时段", "每 4 周做一次里程碑复盘", "寻求 1 位可反馈的伙伴"],
            "costs": ["精力分散", "短期社交/娱乐减少"],
            "failures": ["计划过满无法坚持", "反馈不足导致方向偏差"],
            "warnings": ["里程碑连续未达成", "压力上升影响睡眠或情绪"],
            "reversible": ["降低并行任务数", "延长单阶段时间窗"],
        },
        "aggressive": {
            "title": f"进取路径：集中火力冲刺",
            "tagline": "高投入高波动，适合可承受代价者",
            "decisions": ["集中 3–6 个月高强度投入", "主动争取可展示的项目/面试机会", "接受短期收入或舒适区牺牲"],
            "costs": ["Burnout 风险", "机会成本显著"],
            "failures": ["准备不足仓促上场", "身心透支导致中断"],
            "warnings": ["出现持续焦虑或失眠", "关键指标 4 周无改善"],
            "reversible": ["立即降档到平衡路径", "暂停并重新评估约束"],
        },
    }

    for archetype in SCENARIO_ARCHETYPES:
        tpl = templates[archetype]
        scenarios.append({
            "id": f"scenario_{archetype}",
            "archetype": archetype,
            "title": tpl["title"],
            "tagline": tpl["tagline"],
            "premises": [
                _claim(
                    f"目标：{goal}",
                    "fact" if goal_raw else "uncertainty",
                    0.85 if goal_raw else 0.35,
                ),
                _claim(
                    f"现状：{current}",
                    "fact" if current_raw else "uncertainty",
                    0.85 if current_raw else 0.35,
                ),
                _claim(f"关键差距：{gap_hint}", "assumption", 0.5),
            ],
            "key_decisions": tpl["decisions"],
            "staged_outcomes": [
                {"phase": "短期（1–3 月）", "outcome": f"针对「{goal[:20]}…」完成首轮能力验证", "timeframe": "1-3 月"},
                {"phase": "中期（3–6 月）", "outcome": "达到可对外展示的阶段成果", "timeframe": "3-6 月"},
                {"phase": "长期（6–12 月）", "outcome": "根据复盘结果决定是否加码或调整路径", "timeframe": "6-12 月"},
            ],
            "opportunity_costs": tpl["costs"],
            "failure_modes": tpl["failures"],
            "early_warning_signals": tpl["warnings"],
            "reversible_actions": tpl["reversible"],
            "confidence_notes": "启发式情景，需结合用户约束确认假设。",
        })

    base = empty_scenario_set()
    base.update({
        "set_id": _new_id("scenarios"),
        "profile_id": profile_id,
        "gap_diagnosis_id": gap_id,
        "scenarios": scenarios,
        "meta": {"agent": AGENT_ID, "version": VERSION, "source": "heuristic"},
    })
    return normalize_scenario_set(base)


def _generate_with_llm(
    profile: dict[str, Any],
    gap_diagnosis: dict[str, Any] | None,
) -> dict[str, Any] | None:
    client = get_client()
    if client is None:
        return None
    system = build_safety_system_prompt("scenario")
    prompt = build_user_prompt(profile, gap_diagnosis)
    try:
        raw = client.chat_json(prompt, system=system)
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(raw, dict):
        return None
    if not raw.get("profile_id"):
        raw["profile_id"] = profile.get("profile_id") or _new_id("profile")
    if gap_diagnosis and not raw.get("gap_diagnosis_id"):
        raw["gap_diagnosis_id"] = gap_diagnosis.get("diagnosis_id") or ""
    if not raw.get("set_id"):
        raw["set_id"] = _new_id("scenarios")
    raw["meta"] = {"agent": AGENT_ID, "version": VERSION, "source": "llm"}
    return normalize_scenario_set(raw)


def _format_output(scenario_set: dict[str, Any]) -> str:
    lines = ["三种互斥情景（非预测，供比较选择）："]
    for s in scenario_set.get("scenarios") or []:
        arch = _ARCHETYPE_LABELS.get(s.get("archetype", ""), s.get("archetype"))
        lines.append(f"- [{arch}] {s.get('title')} — {s.get('tagline', '')}")
    lines.append("")
    lines.append(scenario_set.get("disclaimer", ""))
    return "\n".join(lines)


def run(user_input: str = "", **kwargs) -> dict[str, Any]:
    payload = _parse_json_payload(user_input, kwargs)
    profile = resolve_planning_profile(payload)
    gap_diagnosis = resolve_gap_diagnosis(payload)

    if not profile.get("profile_id"):
        profile["profile_id"] = _new_id("profile")

    scenario_set = None
    source = "heuristic"
    if is_llm_available() and not payload.get("heuristic_only"):
        scenario_set = _generate_with_llm(profile, gap_diagnosis)
        if scenario_set:
            source = "llm"

    if scenario_set is None:
        scenario_set = _heuristic_scenarios(profile, gap_diagnosis)

    # 保留用户已选主线
    if payload.get("selected_scenario_id"):
        scenario_set["selected_scenario_id"] = str(payload["selected_scenario_id"])
    if payload.get("selection_rationale"):
        scenario_set["selection_rationale"] = str(payload["selection_rationale"])

    issues = validate_contract(scenario_set, "scenario_set")
    issues.extend(audit_document_text_fields(scenario_set, ["disclaimer"]))

    return {
        "output": _format_output(scenario_set),
        "scenario_set": scenario_set,
        "profile": profile,
        "gap_diagnosis": gap_diagnosis,
        "validation_issues": issues,
        "meta": {"agent": AGENT_ID, "version": VERSION, "source": source},
    }


if __name__ == "__main__":
    gap_fixture = Path(__file__).parent.parent / "gap-diagnosis" / "fixtures" / "sample_profile.json"
    default = json.dumps({
        "profile": {
            "anchors": {"goal": "转行产品经理", "current": "运营 2 年"},
            "readiness": {"status": "conditional"},
        },
        "heuristic_only": True,
    }, ensure_ascii=False)
    raw = resolve_cli_input(default=default, fixture=gap_fixture)
    print(json.dumps(run(raw), ensure_ascii=False, indent=2))
