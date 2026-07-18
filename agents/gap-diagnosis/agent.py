"""差距诊断 Agent — 从 PlanningProfile 输出结构化 GapDiagnosis。"""

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
    normalize_gap_diagnosis,
    profile_ready_for_gap,
    validate_contract,
)
from _lib.planning.input import _parse_json_payload, resolve_planning_profile  # noqa: E402

from _lib.cli import resolve_cli_input  # noqa: E402
from diagnose_prompt import build_user_prompt  # noqa: E402

try:
    from _lib.llm import get_client, is_llm_available  # noqa: E402
except ImportError:

    def is_llm_available() -> bool:  # type: ignore[misc]
        return False

    def get_client():  # type: ignore[misc]
        return None


AGENT_ID = "gap-diagnosis"
VERSION = "0.2.0"


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _heuristic_gaps(profile: dict[str, Any]) -> dict[str, Any]:
    anchors = profile.get("anchors") or {}
    goal = anchors.get("goal") or ""
    current = anchors.get("current") or ""
    profile_id = profile.get("profile_id") or _new_id("profile")

    gaps: list[dict[str, Any]] = []
    if goal and current:
        gaps.append({
            "id": "gap_core",
            "title": "目标与现状之间的核心能力/资源差距",
            "category": "skill",
            "evidence": [
                {
                    "id": "ev_goal",
                    "text": f"目标：{goal}",
                    "kind": "fact",
                    "source": "user_stated",
                    "confidence": 0.85,
                    "evidence_refs": [],
                    "requires_confirmation": False,
                },
                {
                    "id": "ev_current",
                    "text": f"现状：{current}",
                    "kind": "fact",
                    "source": "user_stated",
                    "confidence": 0.85,
                    "evidence_refs": [],
                    "requires_confirmation": False,
                },
            ],
            "baseline": {
                "description": current,
                "indicators": ["能描述当前状态与日常实践"],
            },
            "target_threshold": {
                "description": f"达到目标「{goal}」的最低可验证标准",
                "indicators": ["能列出 1–2 个可检验的里程碑"],
            },
            "verifiable_metrics": ["完成一次与目标相关的可展示成果"],
            "priority": "blocking",
            "closure_options": ["拆解子目标并设定 2 周验证实验", "补齐关键未知信息后再规划"],
            "status": "open",
        })

    for i, unknown in enumerate(profile.get("unknowns") or []):
        text = str(unknown.get("text") or "").strip()
        if not text:
            continue
        gaps.append({
            "id": f"gap_unknown_{i + 1}",
            "title": f"信息缺口：{text[:40]}",
            "category": "other",
            "evidence": [unknown],
            "baseline": {"description": "尚未确认", "indicators": []},
            "target_threshold": {"description": "用户确认或补充证据", "indicators": []},
            "verifiable_metrics": ["用户明确回答或提供样例"],
            "priority": "important" if unknown.get("requires_confirmation") else "optional",
            "closure_options": ["在访谈中追问", "标注假设后继续"],
            "status": "open",
        })

    caps = (profile.get("current_state") or {}).get("capabilities") or []
    if goal and not caps:
        gaps.append({
            "id": "gap_capability_map",
            "title": "能力与目标匹配度未结构化",
            "category": "skill",
            "evidence": [{
                "id": "ev_assume_cap",
                "text": "画像中尚未列出结构化能力项，需假设或追问",
                "kind": "assumption",
                "source": "model_assumed",
                "confidence": 0.4,
                "evidence_refs": [],
                "requires_confirmation": True,
            }],
            "baseline": {"description": "能力清单缺失", "indicators": []},
            "target_threshold": {
                "description": "列出与目标相关的 3 项强项与 2 项短板",
                "indicators": ["自评 + 可验证样例"],
            },
            "verifiable_metrics": ["完成能力自评表"],
            "priority": "important",
            "closure_options": ["补充能力快照", "用近期项目经历代替自评"],
            "status": "open",
        })

    if not gaps:
        gaps.append({
            "id": "gap_goal_clarity",
            "title": "目标或现状描述不足",
            "category": "other",
            "evidence": [{
                "id": "ev_sparse",
                "text": "当前画像缺少足够的目标/现状锚点",
                "kind": "uncertainty",
                "source": "model_inferred",
                "confidence": 0.5,
                "evidence_refs": [],
                "requires_confirmation": True,
            }],
            "baseline": {"description": "信息稀疏", "indicators": []},
            "target_threshold": {"description": "明确可陈述的目标与现状", "indicators": []},
            "verifiable_metrics": ["用户用一句话描述目标与现状"],
            "priority": "blocking",
            "closure_options": ["回到画像采集补充"],
            "status": "open",
        })

    return normalize_gap_diagnosis({
        "diagnosis_id": _new_id("diag"),
        "profile_id": profile_id,
        "summary": f"基于当前画像识别 {len(gaps)} 项差距（启发式，未调用 LLM）。",
        "gaps": gaps,
        "meta": {"agent": AGENT_ID, "version": VERSION, "source": "heuristic"},
    })


def _generate_with_llm(profile: dict[str, Any]) -> dict[str, Any] | None:
    client = get_client()
    if client is None:
        return None
    system = build_safety_system_prompt("gap")
    prompt = build_user_prompt(profile)
    try:
        raw = client.chat_json(prompt, system=system)
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(raw, dict):
        return None
    if not raw.get("profile_id"):
        raw["profile_id"] = profile.get("profile_id") or _new_id("profile")
    if not raw.get("diagnosis_id"):
        raw["diagnosis_id"] = _new_id("diag")
    raw["meta"] = {"agent": AGENT_ID, "version": VERSION, "source": "llm"}
    return normalize_gap_diagnosis(raw)


def _format_output(diagnosis: dict[str, Any]) -> str:
    gaps = diagnosis.get("gaps") or []
    lines = [diagnosis.get("summary") or f"识别 {len(gaps)} 项差距："]
    for g in gaps[:6]:
        pri = g.get("priority", "")
        lines.append(f"- [{pri}] {g.get('title')}")
    return "\n".join(lines)


def run(user_input: str = "", **kwargs) -> dict[str, Any]:
    payload = _parse_json_payload(user_input, kwargs)
    profile = resolve_planning_profile(payload)

    if not profile.get("profile_id"):
        profile["profile_id"] = _new_id("profile")

    readiness_ok = profile_ready_for_gap(profile)
    force = bool(payload.get("force") or payload.get("allow_incomplete"))

    if not readiness_ok and not force:
        return {
            "output": "画像尚未达到差距诊断放行条件（需 ready 或 conditional）。",
            "gap_diagnosis": None,
            "profile": profile,
            "blocked": True,
            "meta": {"agent": AGENT_ID, "version": VERSION},
        }

    diagnosis = None
    source = "heuristic"
    if is_llm_available() and not payload.get("heuristic_only"):
        diagnosis = _generate_with_llm(profile)
        if diagnosis:
            source = "llm"

    if diagnosis is None:
        diagnosis = _heuristic_gaps(profile)

    issues = validate_contract(diagnosis, "gap_diagnosis")
    issues.extend(audit_document_text_fields(diagnosis, ["summary"]))

    return {
        "output": _format_output(diagnosis),
        "gap_diagnosis": diagnosis,
        "profile": profile,
        "validation_issues": issues,
        "meta": {"agent": AGENT_ID, "version": VERSION, "source": source},
    }


if __name__ == "__main__":
    fixture = Path(__file__).parent / "fixtures" / "sample_profile.json"
    default = json.dumps({
        "profile": {
            "anchors": {
                "goal": "6 个月内拿到海外前端面试机会",
                "current": "国内 3 年前端，口语一般，无英文项目叙述经验",
                "goal_clarity": "medium",
                "current_clarity": "medium",
            },
            "readiness": {"status": "conditional", "allow_proceed_with_assumptions": True},
        }
    }, ensure_ascii=False)
    raw = resolve_cli_input(default=default, fixture=fixture)
    print(json.dumps(run(raw), ensure_ascii=False, indent=2))
