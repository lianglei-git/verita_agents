"""规划闭环验证辅助 — 链式调用 Agent 与安全断言。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_AGENTS_ROOT = Path(__file__).resolve().parents[3]
_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

for path in (_AGENTS_ROOT,):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from _lib.planning import (  # noqa: E402
    audit_attributed_claim,
    scan_text_violations,
    validate_contract,
)

# Agent run 函数（延迟导入避免循环）
_AGENT_RUNNERS: dict[str, Any] = {}


def _load_agent_run(agent_id: str) -> Any:
    if agent_id in _AGENT_RUNNERS:
        return _AGENT_RUNNERS[agent_id]

    import importlib.util

    agent_dir = _AGENTS_ROOT / agent_id
    agent_path = agent_dir / "agent.py"
    d_str = str(agent_dir)
    if d_str not in sys.path:
        sys.path.insert(0, d_str)

    spec = importlib.util.spec_from_file_location(f"{agent_id}.agent", agent_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load agent: {agent_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    run_fn = module.run
    _AGENT_RUNNERS[agent_id] = run_fn
    return run_fn


def load_fixture(name: str) -> dict[str, Any]:
    path = _FIXTURES_DIR / name
    if not path.is_file():
        path = _FIXTURES_DIR / f"{name}.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def list_fixtures() -> list[Path]:
    return sorted(_FIXTURES_DIR.glob("*.json"))


def collect_text_fields(obj: Any, prefix: str = "") -> list[tuple[str, str]]:
    """递归收集契约中的字符串字段，供安全扫描。"""
    out: list[tuple[str, str]] = []
    if isinstance(obj, str) and obj.strip():
        out.append((prefix or "text", obj))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            child = f"{prefix}.{k}" if prefix else k
            out.extend(collect_text_fields(v, child))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            out.extend(collect_text_fields(item, f"{prefix}[{i}]"))
    return out


def assert_no_safety_violations(payload: dict[str, Any], label: str) -> list[str]:
    issues: list[str] = []
    for field, text in collect_text_fields(payload):
        for v in scan_text_violations(text):
            issues.append(f"{label}.{field}: {v['code']} — {v['message']}")
    return issues


def assert_claims_labeled(scenario_set: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    for scenario in scenario_set.get("scenarios") or []:
        for prem in scenario.get("premises") or []:
            issues.extend(
                f"scenario {scenario.get('id')}.premise: {msg}"
                for msg in audit_attributed_claim(prem)
            )
            text = str(prem.get("text") or "")
            kind = prem.get("kind")
            if kind == "fact" and ("未明确" in text or "未描述" in text):
                issues.append(
                    f"scenario {scenario.get('id')}: placeholder text labeled as fact: {text[:40]}"
                )
    return issues


def assert_contract_valid(payload: dict[str, Any], contract: str) -> list[str]:
    return validate_contract(payload, contract)


def run_gap(payload: dict[str, Any]) -> dict[str, Any]:
    raw = json.dumps(payload, ensure_ascii=False)
    return _load_agent_run("gap-diagnosis")(raw)


def run_scenario(payload: dict[str, Any]) -> dict[str, Any]:
    raw = json.dumps(payload, ensure_ascii=False)
    return _load_agent_run("story-scenario")(raw)


def run_roadmap(payload: dict[str, Any]) -> dict[str, Any]:
    raw = json.dumps(payload, ensure_ascii=False)
    return _load_agent_run("route-planner")(raw)


def run_narrative_start(payload: dict[str, Any]) -> dict[str, Any]:
    raw = json.dumps(payload, ensure_ascii=False)
    return _load_agent_run("life-script-author")(raw)


def run_full_chain(fixture: dict[str, Any], *, include_narrative: bool = False) -> dict[str, Any]:
    """执行 profile → gap → scenarios → select → roadmap → (optional narrative)。"""
    case_id = fixture.get("case_id", "unknown")
    expect = fixture.get("expect") or {}
    issues: list[str] = []
    steps: dict[str, Any] = {}

    base_payload = {
        "heuristic_only": fixture.get("heuristic_only", True),
        "profile": fixture.get("profile"),
    }

    # Step 1: Gap diagnosis
    gap_result = run_gap(base_payload)
    steps["gap"] = gap_result

    if expect.get("gap_blocked") or expect.get("gap_blocked_without_force"):
        if not gap_result.get("blocked"):
            issues.append(f"{case_id}: expected gap to be blocked")
        else:
            return {"case_id": case_id, "passed": len(issues) == 0, "issues": issues, "steps": steps}

    if gap_result.get("blocked"):
        issues.append(f"{case_id}: gap unexpectedly blocked")
        return {"case_id": case_id, "passed": False, "issues": issues, "steps": steps}

    gap_diagnosis = gap_result.get("gap_diagnosis")
    if not gap_diagnosis:
        issues.append(f"{case_id}: missing gap_diagnosis")
        return {"case_id": case_id, "passed": False, "issues": issues, "steps": steps}

    issues.extend(assert_contract_valid(gap_diagnosis, "gap_diagnosis"))
    issues.extend(assert_no_safety_violations(gap_diagnosis, f"{case_id}.gap"))

    min_gaps = expect.get("min_gaps", 1)
    if len(gap_diagnosis.get("gaps") or []) < min_gaps:
        issues.append(f"{case_id}: expected >= {min_gaps} gaps")

    # Step 2: Scenario simulation
    scenario_payload = {
        **base_payload,
        "gap_diagnosis": gap_diagnosis,
    }
    scenario_result = run_scenario(scenario_payload)
    steps["scenario"] = scenario_result

    scenario_set = scenario_result.get("scenario_set")
    if not scenario_set:
        issues.append(f"{case_id}: missing scenario_set")
        return {"case_id": case_id, "passed": False, "issues": issues, "steps": steps}

    issues.extend(assert_contract_valid(scenario_set, "scenario_set"))
    issues.extend(assert_no_safety_violations(scenario_set, f"{case_id}.scenario"))
    issues.extend(assert_claims_labeled(scenario_set))

    min_scenarios = expect.get("min_scenarios", 3)
    if len(scenario_set.get("scenarios") or []) < min_scenarios:
        issues.append(f"{case_id}: expected >= {min_scenarios} scenarios")

    disclaimer = scenario_set.get("disclaimer") or ""
    if "预测" not in disclaimer and "预言" not in disclaimer:
        issues.append(f"{case_id}: scenario disclaimer missing non-prediction notice")

    if expect.get("has_assumption_premises"):
        has_asm = any(
            p.get("kind") == "assumption"
            for s in scenario_set.get("scenarios") or []
            for p in s.get("premises") or []
        )
        if not has_asm:
            issues.append(f"{case_id}: expected assumption-labeled premises")

    # Step 3: Select scenario
    selected_id = fixture.get("selected_scenario_id") or "scenario_balanced"
    scenario_set["selected_scenario_id"] = selected_id
    if fixture.get("selection_rationale"):
        scenario_set["selection_rationale"] = fixture["selection_rationale"]

    # Step 4: Roadmap
    roadmap_payload = {
        **base_payload,
        "gap_diagnosis": gap_diagnosis,
        "scenario_set": scenario_set,
    }
    roadmap_result = run_roadmap(roadmap_payload)
    steps["roadmap"] = roadmap_result

    if roadmap_result.get("blocked"):
        issues.append(f"{case_id}: roadmap blocked unexpectedly")

    roadmap = roadmap_result.get("roadmap")
    if not roadmap:
        issues.append(f"{case_id}: missing roadmap")
        return {"case_id": case_id, "passed": False, "issues": issues, "steps": steps}

    issues.extend(assert_contract_valid(roadmap, "adaptive_roadmap"))
    issues.extend(assert_no_safety_violations(roadmap, f"{case_id}.roadmap"))

    min_phases = expect.get("min_roadmap_phases", 1)
    phases = roadmap.get("phases") or []
    if len(phases) < min_phases:
        issues.append(f"{case_id}: expected >= {min_phases} roadmap phases")

    for phase in phases:
        if not phase.get("milestones"):
            issues.append(f"{case_id}: phase {phase.get('id')} missing milestones")
        adj = (phase.get("if_not_met") or {}).get("adjustments") or []
        if not adj:
            issues.append(f"{case_id}: phase {phase.get('id')} missing if_not_met adjustments")

    # Step 5: Optional narrative start
    if include_narrative:
        narrative_payload = {
            "reset": True,
            "skip_setup_questions": True,
            "heuristic_only": True,
            "handoff": {
                "planning_profile": fixture.get("profile"),
                "gap_diagnosis": gap_diagnosis,
                "scenario_set": scenario_set,
                "scenario_id": selected_id,
            },
            "creative_intent": {
                "narrative_perspective": "第三人称有限视角",
                "time_span": "一年",
                "genre_intensity": "现实主义",
                "ending_openness": "semi_open",
                "taboos": ["真实姓名"],
            },
        }
        narrative_result = run_narrative_start(narrative_payload)
        steps["narrative"] = narrative_result
        phase = narrative_result.get("current_phase")
        if not phase:
            issues.append(f"{case_id}: narrative missing current_phase")
        output_text = narrative_result.get("output") or ""
        issues.extend(assert_no_safety_violations({"output": output_text}, f"{case_id}.narrative"))

    return {
        "case_id": case_id,
        "description": fixture.get("description", ""),
        "passed": len(issues) == 0,
        "issues": issues,
        "steps": {
            k: {
                "blocked": v.get("blocked"),
                "validation_issues": v.get("validation_issues"),
                "output_preview": (v.get("output") or "")[:120],
            }
            for k, v in steps.items()
        },
    }


def run_all_fixtures(*, include_narrative: bool = False) -> list[dict[str, Any]]:
    results = []
    for path in list_fixtures():
        fixture = load_fixture(path.name)
        results.append(run_full_chain(fixture, include_narrative=include_narrative))
    return results
