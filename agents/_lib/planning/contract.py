"""规划流水线统一契约 — empty/normalize/bridge 工厂。"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .safety import audit_attributed_claim
from .types import SCHEMA_VERSION, SCENARIO_ARCHETYPES

_SCHEMAS_DIR = Path(__file__).resolve().parent / "schemas"

# ---------------------------------------------------------------------------
# 通用工具
# ---------------------------------------------------------------------------


def _filled(val: Any) -> bool:
    if val is None:
        return False
    if isinstance(val, str):
        return bool(val.strip())
    return bool(val)


def _strip_str(val: Any, default: str = "") -> str:
    if val is None:
        return default
    return str(val).strip()


def _enum(val: Any, allowed: tuple[str, ...], default: str) -> str:
    s = _strip_str(val, default)
    return s if s in allowed else default


def _clamp_confidence(val: Any, default: float = 0.5) -> float:
    try:
        c = float(val)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, c))


def _list_of_dicts(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    return [dict(x) for x in raw if isinstance(x, dict)]


def schema_path(name: str) -> Path:
    """返回 JSON Schema 文件路径（不含 .schema.json 后缀）。"""
    stem = name if name.endswith(".schema.json") else f"{name}.schema.json"
    return _SCHEMAS_DIR / stem


def load_schema(name: str) -> dict[str, Any]:
    path = schema_path(name)
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"schema must be object: {path}")
    return data


# ---------------------------------------------------------------------------
# AttributedClaim — 事实 / 假设 / 不确定性
# ---------------------------------------------------------------------------


def empty_attributed_claim() -> dict[str, Any]:
    return {
        "id": "",
        "text": "",
        "kind": "assumption",
        "source": "model_assumed",
        "confidence": 0.5,
        "evidence_refs": [],
        "requires_confirmation": False,
    }


def normalize_attributed_claim(raw: dict | None) -> dict[str, Any] | None:
    if not raw:
        return None
    text = _strip_str(raw.get("text"))
    if not text:
        return None
    out = empty_attributed_claim()
    out["id"] = _strip_str(raw.get("id")) or out["id"]
    out["text"] = text
    out["kind"] = _enum(
        raw.get("kind"),
        ("fact", "assumption", "uncertainty"),
        "assumption",
    )
    out["source"] = _enum(
        raw.get("source"),
        ("user_stated", "user_inferred", "model_assumed", "model_inferred"),
        "model_assumed" if out["kind"] != "fact" else "user_stated",
    )
    if out["kind"] == "fact" and out["source"].startswith("model_"):
        out["source"] = "user_stated"
    out["confidence"] = _clamp_confidence(raw.get("confidence"), 0.5)
    refs = raw.get("evidence_refs")
    out["evidence_refs"] = [
        _strip_str(r) for r in (refs or []) if _strip_str(r)
    ]
    out["requires_confirmation"] = bool(raw.get("requires_confirmation", False))
    if out["kind"] == "fact":
        out["requires_confirmation"] = False
    return out


def normalize_attributed_claims(raw: list | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, item in enumerate(_list_of_dicts(raw)):
        claim = normalize_attributed_claim(item)
        if not claim:
            continue
        if not claim["id"]:
            claim["id"] = f"claim_{i + 1}"
        out.append(claim)
    return out


# ---------------------------------------------------------------------------
# PlanningProfile
# ---------------------------------------------------------------------------


def empty_goal_item() -> dict[str, Any]:
    return {
        "id": "",
        "description": "",
        "acceptance_criteria": [],
        "priority": "primary",
        "time_horizon": "",
    }


def normalize_goal_item(raw: dict | None) -> dict[str, Any] | None:
    if not raw:
        return None
    desc = _strip_str(raw.get("description"))
    if not desc:
        return None
    out = empty_goal_item()
    out["id"] = _strip_str(raw.get("id"))
    out["description"] = desc
    criteria = raw.get("acceptance_criteria")
    out["acceptance_criteria"] = [
        _strip_str(c) for c in (criteria or []) if _strip_str(c)
    ]
    out["priority"] = _enum(raw.get("priority"), ("primary", "secondary"), "primary")
    out["time_horizon"] = _strip_str(raw.get("time_horizon"))
    return out


def empty_planning_profile() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "profile_id": "",
        "anchors": {
            "goal": "",
            "current": "",
            "goal_clarity": "low",
            "current_clarity": "low",
        },
        "stated_facts": [],
        "goals": [],
        "current_state": {
            "capabilities": [],
            "resources": [],
            "constraints": [],
            "identity": {
                "age_range": "",
                "occupation": "",
                "region_anchor": "",
                "native_language": "",
                "role_anchor": "",
            },
            "capability_snapshot": {
                "self_assessed_level": "",
                "strongest": "",
                "weakest": "",
            },
        },
        "values_preferences": [],
        "acceptable_costs": {
            "time": "",
            "money": "",
            "energy": "",
            "tradeoffs": [],
        },
        "unknowns": [],
        "assumptions": [],
        "inferences": [],
        "readiness": {
            "status": "collecting",
            "confidence": 0.0,
            "blocking_gaps": [],
            "allow_proceed_with_assumptions": False,
        },
        "provenance": {
            "input_snapshot_id": "",
            "version": 1,
            "user_profile_release": "",
            "source_agent": "",
        },
    }


def normalize_planning_profile(raw: dict | None) -> dict[str, Any]:
    base = empty_planning_profile()
    if not raw:
        return base

    base["schema_version"] = _strip_str(raw.get("schema_version"), SCHEMA_VERSION)
    base["profile_id"] = _strip_str(raw.get("profile_id"))

    anchors = {**base["anchors"], **(raw.get("anchors") or {})}
    anchors["goal"] = _strip_str(anchors.get("goal"))
    anchors["current"] = _strip_str(anchors.get("current"))
    anchors["goal_clarity"] = _enum(
        anchors.get("goal_clarity"), ("low", "medium", "high"), "low"
    )
    anchors["current_clarity"] = _enum(
        anchors.get("current_clarity"), ("low", "medium", "high"), "low"
    )
    base["anchors"] = anchors

    base["stated_facts"] = normalize_attributed_claims(raw.get("stated_facts"))

    goals: list[dict[str, Any]] = []
    for i, g in enumerate(_list_of_dicts(raw.get("goals"))):
        item = normalize_goal_item(g)
        if not item:
            continue
        if not item["id"]:
            item["id"] = f"goal_{i + 1}"
        goals.append(item)
    if not goals and anchors["goal"]:
        goals.append({
            **empty_goal_item(),
            "id": "goal_primary",
            "description": anchors["goal"],
            "priority": "primary",
        })
    base["goals"] = goals

    cs = base["current_state"]
    incoming = raw.get("current_state") or {}
    for key in ("capabilities", "resources", "constraints"):
        cs[key] = normalize_attributed_claims(incoming.get(key))
    ident = {**cs["identity"], **(incoming.get("identity") or {})}
    for k in cs["identity"]:
        ident[k] = _strip_str(ident.get(k))
    cs["identity"] = ident
    snap = {**cs["capability_snapshot"], **(incoming.get("capability_snapshot") or {})}
    for k in cs["capability_snapshot"]:
        snap[k] = _strip_str(snap.get(k))
    cs["capability_snapshot"] = snap
    base["current_state"] = cs

    base["values_preferences"] = normalize_attributed_claims(raw.get("values_preferences"))

    costs = {**base["acceptable_costs"], **(raw.get("acceptable_costs") or {})}
    for k in ("time", "money", "energy"):
        costs[k] = _strip_str(costs.get(k))
    costs["tradeoffs"] = [
        _strip_str(t) for t in (costs.get("tradeoffs") or []) if _strip_str(t)
    ]
    base["acceptable_costs"] = costs

    base["unknowns"] = normalize_attributed_claims(raw.get("unknowns"))
    base["assumptions"] = normalize_attributed_claims(raw.get("assumptions"))
    base["inferences"] = normalize_attributed_claims(raw.get("inferences"))

    readiness = {**base["readiness"], **(raw.get("readiness") or {})}
    readiness["status"] = _enum(
        readiness.get("status"),
        ("collecting", "conditional", "ready"),
        "collecting",
    )
    readiness["confidence"] = _clamp_confidence(readiness.get("confidence"), 0.0)
    readiness["blocking_gaps"] = [
        _strip_str(g) for g in (readiness.get("blocking_gaps") or []) if _strip_str(g)
    ]
    readiness["allow_proceed_with_assumptions"] = bool(
        readiness.get("allow_proceed_with_assumptions", False)
    )
    base["readiness"] = readiness

    prov = {**base["provenance"], **(raw.get("provenance") or {})}
    prov["input_snapshot_id"] = _strip_str(prov.get("input_snapshot_id"))
    prov["version"] = int(prov.get("version") or 1)
    prov["user_profile_release"] = _strip_str(prov.get("user_profile_release"))
    prov["source_agent"] = _strip_str(prov.get("source_agent"))
    base["provenance"] = prov

    return base


def planning_profile_from_handoff(handoff: dict | None) -> dict[str, Any]:
    """将 user-profile handoff 转为 PlanningProfile（Phase 2 入口桥接）。"""
    profile = empty_planning_profile()
    if not handoff:
        return profile

    universal = handoff.get("universal") or {}
    anchors = universal.get("anchors") or {}
    ident = universal.get("identity") or {}
    cap = universal.get("capability_snapshot") or {}

    profile["anchors"] = {
        "goal": _strip_str(anchors.get("goal")),
        "current": _strip_str(anchors.get("current")),
        "goal_clarity": _enum(
            anchors.get("goal_clarity"), ("low", "medium", "high"), "low"
        ),
        "current_clarity": _enum(
            anchors.get("current_clarity"), ("low", "medium", "high"), "low"
        ),
    }
    profile["current_state"]["identity"] = {
        k: _strip_str(ident.get(k)) for k in profile["current_state"]["identity"]
    }
    profile["current_state"]["capability_snapshot"] = {
        k: _strip_str(cap.get(k))
        for k in profile["current_state"]["capability_snapshot"]
    }

    if profile["anchors"]["goal"]:
        profile["goals"] = [{
            **empty_goal_item(),
            "id": "goal_primary",
            "description": profile["anchors"]["goal"],
            "priority": "primary",
        }]
    if profile["anchors"]["current"]:
        profile["stated_facts"].append({
            **empty_attributed_claim(),
            "id": "fact_current",
            "text": profile["anchors"]["current"],
            "kind": "fact",
            "source": "user_stated",
            "confidence": 0.9,
        })

    for i, item in enumerate(handoff.get("assumptions") or []):
        if isinstance(item, str) and item.strip():
            profile["assumptions"].append({
                **empty_attributed_claim(),
                "id": f"assumption_{i + 1}",
                "text": item.strip(),
                "kind": "assumption",
                "source": "model_assumed",
                "confidence": 0.5,
            })
        elif isinstance(item, dict):
            claim = normalize_attributed_claim(item)
            if claim:
                profile["assumptions"].append(claim)

    for key in handoff.get("unresolved_meta") or []:
        if _strip_str(key):
            profile["unknowns"].append({
                **empty_attributed_claim(),
                "id": f"unknown_{_strip_str(key)}",
                "text": f"待确认：{_strip_str(key)}",
                "kind": "uncertainty",
                "source": "model_inferred",
                "confidence": 0.3,
                "requires_confirmation": True,
            })

    release = _strip_str(handoff.get("release_type"), "collecting")
    profile["readiness"]["status"] = {
        "sufficient": "ready",
        "conditional": "conditional",
        "collecting": "collecting",
    }.get(release, "collecting")
    profile["readiness"]["confidence"] = _clamp_confidence(
        handoff.get("confidence"), 0.0
    )
    profile["readiness"]["allow_proceed_with_assumptions"] = release == "conditional"
    profile["provenance"]["user_profile_release"] = release
    profile["provenance"]["source_agent"] = "user-profile"

    return normalize_planning_profile(profile)


def profile_ready_for_gap(profile: dict[str, Any]) -> bool:
    """是否可进入差距诊断（允许 conditional 放行）。"""
    r = (profile.get("readiness") or {}).get("status")
    return r in ("ready", "conditional")


def pending_confirmation_claims(profile: dict[str, Any]) -> list[dict[str, Any]]:
    """收集需用户确认的高影响假设/未知项。"""
    pending: list[dict[str, Any]] = []
    for bucket in ("assumptions", "unknowns", "inferences"):
        for claim in profile.get(bucket) or []:
            if claim.get("requires_confirmation"):
                pending.append(claim)
    return pending


# ---------------------------------------------------------------------------
# GapDiagnosis
# ---------------------------------------------------------------------------


def empty_gap_item() -> dict[str, Any]:
    return {
        "id": "",
        "title": "",
        "category": "other",
        "evidence": [],
        "baseline": {"description": "", "indicators": []},
        "target_threshold": {"description": "", "indicators": []},
        "verifiable_metrics": [],
        "priority": "important",
        "closure_options": [],
        "status": "open",
    }


def normalize_gap_item(raw: dict | None) -> dict[str, Any] | None:
    if not raw:
        return None
    title = _strip_str(raw.get("title"))
    if not title:
        return None
    out = empty_gap_item()
    out["id"] = _strip_str(raw.get("id"))
    out["title"] = title
    out["category"] = _enum(
        raw.get("category"),
        ("skill", "resource", "time", "credential", "network", "mindset", "other"),
        "other",
    )
    out["evidence"] = normalize_attributed_claims(raw.get("evidence"))
    for side in ("baseline", "target_threshold"):
        block = {**out[side], **(raw.get(side) or {})}
        block["description"] = _strip_str(block.get("description"))
        block["indicators"] = [
            _strip_str(x) for x in (block.get("indicators") or []) if _strip_str(x)
        ]
        out[side] = block
    out["verifiable_metrics"] = [
        _strip_str(m) for m in (raw.get("verifiable_metrics") or []) if _strip_str(m)
    ]
    out["priority"] = _enum(
        raw.get("priority"), ("blocking", "important", "optional"), "important"
    )
    out["closure_options"] = [
        _strip_str(o) for o in (raw.get("closure_options") or []) if _strip_str(o)
    ]
    out["status"] = _enum(raw.get("status"), ("open", "partial", "closed"), "open")
    return out


def empty_gap_diagnosis() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "diagnosis_id": "",
        "profile_id": "",
        "summary": "",
        "gaps": [],
        "meta": {"agent": "", "version": ""},
    }


def normalize_gap_diagnosis(raw: dict | None) -> dict[str, Any]:
    base = empty_gap_diagnosis()
    if not raw:
        return base
    base["schema_version"] = _strip_str(raw.get("schema_version"), SCHEMA_VERSION)
    base["diagnosis_id"] = _strip_str(raw.get("diagnosis_id"))
    base["profile_id"] = _strip_str(raw.get("profile_id"))
    base["summary"] = _strip_str(raw.get("summary"))
    gaps: list[dict[str, Any]] = []
    for i, g in enumerate(_list_of_dicts(raw.get("gaps"))):
        item = normalize_gap_item(g)
        if not item:
            continue
        if not item["id"]:
            item["id"] = f"gap_{i + 1}"
        gaps.append(item)
    base["gaps"] = gaps
    meta = raw.get("meta")
    base["meta"] = dict(meta) if isinstance(meta, dict) else base["meta"]
    return base


# ---------------------------------------------------------------------------
# ScenarioSet
# ---------------------------------------------------------------------------


def empty_scenario_item() -> dict[str, Any]:
    return {
        "id": "",
        "archetype": "balanced",
        "title": "",
        "tagline": "",
        "premises": [],
        "key_decisions": [],
        "staged_outcomes": [],
        "opportunity_costs": [],
        "failure_modes": [],
        "early_warning_signals": [],
        "reversible_actions": [],
        "confidence_notes": "",
    }


def normalize_scenario_item(raw: dict | None) -> dict[str, Any] | None:
    if not raw:
        return None
    title = _strip_str(raw.get("title"))
    if not title:
        return None
    out = empty_scenario_item()
    out["id"] = _strip_str(raw.get("id"))
    out["title"] = title
    out["archetype"] = _enum(raw.get("archetype"), SCENARIO_ARCHETYPES, "balanced")
    out["tagline"] = _strip_str(raw.get("tagline"))
    out["premises"] = normalize_attributed_claims(raw.get("premises"))
    out["key_decisions"] = [
        _strip_str(d) for d in (raw.get("key_decisions") or []) if _strip_str(d)
    ]
    staged: list[dict[str, Any]] = []
    for s in _list_of_dicts(raw.get("staged_outcomes")):
        staged.append({
            "phase": _strip_str(s.get("phase")),
            "outcome": _strip_str(s.get("outcome")),
            "timeframe": _strip_str(s.get("timeframe")),
        })
    out["staged_outcomes"] = [x for x in staged if x.get("outcome")]
    for field in (
        "opportunity_costs",
        "failure_modes",
        "early_warning_signals",
        "reversible_actions",
    ):
        out[field] = [_strip_str(x) for x in (raw.get(field) or []) if _strip_str(x)]
    out["confidence_notes"] = _strip_str(raw.get("confidence_notes"))
    return out


def empty_scenario_set() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "set_id": "",
        "profile_id": "",
        "gap_diagnosis_id": "",
        "comparison_axes": ["risk", "upside", "reversibility", "effort"],
        "scenarios": [],
        "disclaimer": (
            "以下情景为基于当前信息与假设的互斥路径推演，"
            "不是对未来的确定性预测。请选择最符合你风险偏好的主线。"
        ),
        "selected_scenario_id": "",
        "selection_rationale": "",
    }


def normalize_scenario_set(raw: dict | None) -> dict[str, Any]:
    base = empty_scenario_set()
    if not raw:
        return base
    base["schema_version"] = _strip_str(raw.get("schema_version"), SCHEMA_VERSION)
    base["set_id"] = _strip_str(raw.get("set_id"))
    base["profile_id"] = _strip_str(raw.get("profile_id"))
    base["gap_diagnosis_id"] = _strip_str(raw.get("gap_diagnosis_id"))
    axes = raw.get("comparison_axes")
    base["comparison_axes"] = [
        _strip_str(a) for a in (axes or base["comparison_axes"]) if _strip_str(a)
    ]
    scenarios: list[dict[str, Any]] = []
    for i, s in enumerate(_list_of_dicts(raw.get("scenarios"))):
        item = normalize_scenario_item(s)
        if not item:
            continue
        if not item["id"]:
            item["id"] = f"scenario_{i + 1}"
        scenarios.append(item)
    base["scenarios"] = scenarios
    if _strip_str(raw.get("disclaimer")):
        base["disclaimer"] = _strip_str(raw.get("disclaimer"))
    base["selected_scenario_id"] = _strip_str(raw.get("selected_scenario_id"))
    base["selection_rationale"] = _strip_str(raw.get("selection_rationale"))
    return base


# ---------------------------------------------------------------------------
# AdaptiveRoadmap
# ---------------------------------------------------------------------------


def empty_roadmap_action() -> dict[str, Any]:
    return {"id": "", "description": "", "effort": "", "owner": "user"}


def empty_roadmap_phase() -> dict[str, Any]:
    return {
        "id": "",
        "title": "",
        "goal": "",
        "time_window": {"label": "month", "start": "", "end": ""},
        "actions": [],
        "deliverables": [],
        "success_thresholds": [],
        "resource_costs": {"time": "", "money": "", "energy": ""},
        "milestones": [],
        "risk_signals": [],
        "if_not_met": {"description": "", "adjustments": []},
        "review_checkpoint": {"when": "", "questions": []},
    }


def normalize_roadmap_phase(raw: dict | None) -> dict[str, Any] | None:
    if not raw:
        return None
    title = _strip_str(raw.get("title"))
    goal = _strip_str(raw.get("goal"))
    if not title and not goal:
        return None
    out = empty_roadmap_phase()
    out["id"] = _strip_str(raw.get("id"))
    out["title"] = title or goal[:40]
    out["goal"] = goal
    tw = {**out["time_window"], **(raw.get("time_window") or {})}
    tw["label"] = _enum(tw.get("label"), ("week", "month", "quarter", "year"), "month")
    tw["start"] = _strip_str(tw.get("start"))
    tw["end"] = _strip_str(tw.get("end"))
    out["time_window"] = tw
    actions: list[dict[str, Any]] = []
    for i, a in enumerate(_list_of_dicts(raw.get("actions"))):
        desc = _strip_str(a.get("description"))
        if not desc:
            continue
        actions.append({
            "id": _strip_str(a.get("id")) or f"action_{i + 1}",
            "description": desc,
            "effort": _strip_str(a.get("effort")),
            "owner": _strip_str(a.get("owner"), "user") or "user",
        })
    out["actions"] = actions
    out["deliverables"] = [
        _strip_str(d) for d in (raw.get("deliverables") or []) if _strip_str(d)
    ]
    out["success_thresholds"] = [
        _strip_str(s) for s in (raw.get("success_thresholds") or []) if _strip_str(s)
    ]
    costs = {**out["resource_costs"], **(raw.get("resource_costs") or {})}
    for k in ("time", "money", "energy"):
        costs[k] = _strip_str(costs.get(k))
    out["resource_costs"] = costs
    milestones: list[dict[str, Any]] = []
    for i, m in enumerate(_list_of_dicts(raw.get("milestones"))):
        desc = _strip_str(m.get("description"))
        if not desc:
            continue
        milestones.append({
            "id": _strip_str(m.get("id")) or f"milestone_{i + 1}",
            "description": desc,
            "due": _strip_str(m.get("due")),
            "verifiable": bool(m.get("verifiable", True)),
        })
    out["milestones"] = milestones
    out["risk_signals"] = [
        _strip_str(r) for r in (raw.get("risk_signals") or []) if _strip_str(r)
    ]
    adj = {**out["if_not_met"], **(raw.get("if_not_met") or {})}
    adj["description"] = _strip_str(adj.get("description"))
    adj["adjustments"] = [
        _strip_str(x) for x in (adj.get("adjustments") or []) if _strip_str(x)
    ]
    out["if_not_met"] = adj
    rc = {**out["review_checkpoint"], **(raw.get("review_checkpoint") or {})}
    rc["when"] = _strip_str(rc.get("when"))
    rc["questions"] = [
        _strip_str(q) for q in (rc.get("questions") or []) if _strip_str(q)
    ]
    out["review_checkpoint"] = rc
    return out


def empty_adaptive_roadmap() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "roadmap_id": "",
        "profile_id": "",
        "scenario_id": "",
        "title": "",
        "summary": "",
        "phases": [],
        "assumptions": [],
        "version": 1,
        "revision_log": [],
    }


def normalize_adaptive_roadmap(raw: dict | None) -> dict[str, Any]:
    base = empty_adaptive_roadmap()
    if not raw:
        return base
    base["schema_version"] = _strip_str(raw.get("schema_version"), SCHEMA_VERSION)
    for key in ("roadmap_id", "profile_id", "scenario_id", "title", "summary"):
        base[key] = _strip_str(raw.get(key))
    phases: list[dict[str, Any]] = []
    for i, p in enumerate(_list_of_dicts(raw.get("phases"))):
        item = normalize_roadmap_phase(p)
        if not item:
            continue
        if not item["id"]:
            item["id"] = f"phase_{i + 1}"
        phases.append(item)
    base["phases"] = phases
    base["assumptions"] = normalize_attributed_claims(raw.get("assumptions"))
    base["version"] = int(raw.get("version") or 1)
    rev = raw.get("revision_log")
    base["revision_log"] = list(rev) if isinstance(rev, list) else []
    return base


# ---------------------------------------------------------------------------
# StoryBible
# ---------------------------------------------------------------------------


def empty_story_bible() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "bible_id": "",
        "profile_id": "",
        "scenario_id": "",
        "adaptation_mode": "deidentified",
        "creative_intent": {
            "narrative_perspective": "",
            "time_span": "",
            "genre_intensity": "",
            "taboos": [],
            "ending_openness": "semi_open",
        },
        "fact_boundary": {
            "confirmed_facts": [],
            "fictionalized_elements": [],
            "do_not_identify": [],
        },
        "characters": [],
        "relationships": [],
        "core_conflict": "",
        "themes": [],
        "world_rules": [],
        "timeline": [],
        "key_events": [],
        "foreshadowing": [],
        "chapter_summaries": [],
        "style_constraints": {"tone": "", "pov": "", "tense": ""},
        "unresolved_threads": [],
        "continuity_notes": [],
    }


def normalize_story_bible(raw: dict | None) -> dict[str, Any]:
    base = empty_story_bible()
    if not raw:
        return base
    base["schema_version"] = _strip_str(raw.get("schema_version"), SCHEMA_VERSION)
    for key in ("bible_id", "profile_id", "scenario_id", "core_conflict"):
        base[key] = _strip_str(raw.get(key))
    base["adaptation_mode"] = _enum(
        raw.get("adaptation_mode"),
        ("faithful", "deidentified", "fictionalized"),
        "deidentified",
    )
    ci = {**base["creative_intent"], **(raw.get("creative_intent") or {})}
    for k in ("narrative_perspective", "time_span", "genre_intensity"):
        ci[k] = _strip_str(ci.get(k))
    ci["taboos"] = [_strip_str(t) for t in (ci.get("taboos") or []) if _strip_str(t)]
    ci["ending_openness"] = _enum(
        ci.get("ending_openness"), ("open", "semi_open", "closed"), "semi_open"
    )
    base["creative_intent"] = ci
    fb = {**base["fact_boundary"], **(raw.get("fact_boundary") or {})}
    fb["confirmed_facts"] = normalize_attributed_claims(fb.get("confirmed_facts"))
    fb["fictionalized_elements"] = [
        _strip_str(x) for x in (fb.get("fictionalized_elements") or []) if _strip_str(x)
    ]
    fb["do_not_identify"] = [
        _strip_str(x) for x in (fb.get("do_not_identify") or []) if _strip_str(x)
    ]
    base["fact_boundary"] = fb
    chars: list[dict[str, Any]] = []
    for i, c in enumerate(_list_of_dicts(raw.get("characters"))):
        name = _strip_str(c.get("name"))
        if not name:
            continue
        chars.append({
            "id": _strip_str(c.get("id")) or f"char_{i + 1}",
            "name": name,
            "role": _strip_str(c.get("role")),
            "arc": _strip_str(c.get("arc")),
            "traits": [_strip_str(t) for t in (c.get("traits") or []) if _strip_str(t)],
            "state": dict(c.get("state") or {}) if isinstance(c.get("state"), dict) else {},
        })
    base["characters"] = chars
    rels: list[dict[str, Any]] = []
    for r in _list_of_dicts(raw.get("relationships")):
        if _strip_str(r.get("from")) and _strip_str(r.get("to")):
            rels.append({
                "from": _strip_str(r.get("from")),
                "to": _strip_str(r.get("to")),
                "type": _strip_str(r.get("type")),
                "dynamic": _strip_str(r.get("dynamic")),
            })
    base["relationships"] = rels
    base["themes"] = [_strip_str(t) for t in (raw.get("themes") or []) if _strip_str(t)]
    base["world_rules"] = [
        _strip_str(w) for w in (raw.get("world_rules") or []) if _strip_str(w)
    ]
    timeline: list[dict[str, Any]] = []
    for i, t in enumerate(_list_of_dicts(raw.get("timeline"))):
        event = _strip_str(t.get("event"))
        if not event:
            continue
        timeline.append({
            "id": _strip_str(t.get("id")) or f"evt_{i + 1}",
            "when": _strip_str(t.get("when")),
            "event": event,
            "chapter_refs": [
                int(x) for x in (t.get("chapter_refs") or []) if str(x).isdigit()
            ],
        })
    base["timeline"] = timeline
    base["key_events"] = [
        _strip_str(e) for e in (raw.get("key_events") or []) if _strip_str(e)
    ]
    foreshadow: list[dict[str, Any]] = []
    for i, f in enumerate(_list_of_dicts(raw.get("foreshadowing"))):
        setup = _strip_str(f.get("setup"))
        if not setup:
            continue
        foreshadow.append({
            "id": _strip_str(f.get("id")) or f"fore_{i + 1}",
            "setup": setup,
            "payoff_planned": _strip_str(f.get("payoff_planned")),
            "status": _enum(
                f.get("status"), ("planted", "resolved", "abandoned"), "planted"
            ),
        })
    base["foreshadowing"] = foreshadow
    summaries: list[dict[str, Any]] = []
    for s in _list_of_dicts(raw.get("chapter_summaries")):
        num = s.get("chapter_number")
        try:
            chapter_number = int(num)
        except (TypeError, ValueError):
            continue
        summaries.append({
            "chapter_number": chapter_number,
            "title": _strip_str(s.get("title")),
            "summary": _strip_str(s.get("summary")),
        })
    base["chapter_summaries"] = summaries
    style = {**base["style_constraints"], **(raw.get("style_constraints") or {})}
    for k in ("tone", "pov", "tense"):
        style[k] = _strip_str(style.get(k))
    base["style_constraints"] = style
    base["unresolved_threads"] = [
        _strip_str(u) for u in (raw.get("unresolved_threads") or []) if _strip_str(u)
    ]
    base["continuity_notes"] = [
        _strip_str(n) for n in (raw.get("continuity_notes") or []) if _strip_str(n)
    ]
    return base


# ---------------------------------------------------------------------------
# ChapterPlan & ChapterDraft
# ---------------------------------------------------------------------------


def empty_chapter_plan() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "plan_id": "",
        "bible_id": "",
        "chapter_number": 1,
        "title": "",
        "objectives": [],
        "conflict": "",
        "character_state_changes": [],
        "threads_to_continue": [],
        "threads_to_plant": [],
        "expected_word_count": {"min": 2500, "max": 3500},
        "beats": [],
        "approval": {"status": "draft", "user_notes": ""},
    }


def normalize_chapter_plan(raw: dict | None) -> dict[str, Any]:
    base = empty_chapter_plan()
    if not raw:
        return base
    base["schema_version"] = _strip_str(raw.get("schema_version"), SCHEMA_VERSION)
    base["plan_id"] = _strip_str(raw.get("plan_id"))
    base["bible_id"] = _strip_str(raw.get("bible_id"))
    try:
        base["chapter_number"] = max(1, int(raw.get("chapter_number") or 1))
    except (TypeError, ValueError):
        base["chapter_number"] = 1
    base["title"] = _strip_str(raw.get("title"))
    base["objectives"] = [
        _strip_str(o) for o in (raw.get("objectives") or []) if _strip_str(o)
    ]
    base["conflict"] = _strip_str(raw.get("conflict"))
    changes: list[dict[str, Any]] = []
    for c in _list_of_dicts(raw.get("character_state_changes")):
        cid = _strip_str(c.get("character_id"))
        if not cid:
            continue
        changes.append({
            "character_id": cid,
            "from_state": _strip_str(c.get("from_state")),
            "to_state": _strip_str(c.get("to_state")),
        })
    base["character_state_changes"] = changes
    base["threads_to_continue"] = [
        _strip_str(t) for t in (raw.get("threads_to_continue") or []) if _strip_str(t)
    ]
    base["threads_to_plant"] = [
        _strip_str(t) for t in (raw.get("threads_to_plant") or []) if _strip_str(t)
    ]
    ewc = {**base["expected_word_count"], **(raw.get("expected_word_count") or {})}
    try:
        ewc["min"] = max(500, int(ewc.get("min") or 2500))
        ewc["max"] = max(ewc["min"], int(ewc.get("max") or 3500))
    except (TypeError, ValueError):
        ewc = {"min": 2500, "max": 3500}
    base["expected_word_count"] = ewc
    base["beats"] = [_strip_str(b) for b in (raw.get("beats") or []) if _strip_str(b)]
    approval = {**base["approval"], **(raw.get("approval") or {})}
    approval["status"] = _enum(
        approval.get("status"), ("draft", "approved", "rejected"), "draft"
    )
    approval["user_notes"] = _strip_str(approval.get("user_notes"))
    base["approval"] = approval
    return base


def empty_chapter_draft() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "draft_id": "",
        "plan_id": "",
        "chapter_number": 1,
        "title": "",
        "content": "",
        "word_count": 0,
        "fiction_disclaimer": (
            "本章为基于用户所选情景创作的虚构叙事，不代表现实预测或真实经历。"
        ),
        "extracted_events": [],
        "character_state_updates": [],
        "new_threads": [],
        "continuity_flags": [],
        "revision": {"version": 1, "status": "draft", "user_notes": ""},
    }


def normalize_chapter_draft(raw: dict | None) -> dict[str, Any]:
    base = empty_chapter_draft()
    if not raw:
        return base
    base["schema_version"] = _strip_str(raw.get("schema_version"), SCHEMA_VERSION)
    base["draft_id"] = _strip_str(raw.get("draft_id"))
    base["plan_id"] = _strip_str(raw.get("plan_id"))
    try:
        base["chapter_number"] = max(1, int(raw.get("chapter_number") or 1))
    except (TypeError, ValueError):
        base["chapter_number"] = 1
    base["title"] = _strip_str(raw.get("title"))
    base["content"] = _strip_str(raw.get("content"))
    base["word_count"] = len(base["content"]) if base["content"] else 0
    if _strip_str(raw.get("fiction_disclaimer")):
        base["fiction_disclaimer"] = _strip_str(raw.get("fiction_disclaimer"))
    base["extracted_events"] = [
        _strip_str(e) for e in (raw.get("extracted_events") or []) if _strip_str(e)
    ]
    updates: list[dict[str, Any]] = []
    for u in _list_of_dicts(raw.get("character_state_updates")):
        cid = _strip_str(u.get("character_id"))
        if not cid:
            continue
        updates.append({
            "character_id": cid,
            "state": dict(u.get("state") or {}) if isinstance(u.get("state"), dict) else {},
        })
    base["character_state_updates"] = updates
    base["new_threads"] = [
        _strip_str(t) for t in (raw.get("new_threads") or []) if _strip_str(t)
    ]
    flags: list[dict[str, Any]] = []
    for f in _list_of_dicts(raw.get("continuity_flags")):
        msg = _strip_str(f.get("message"))
        if not msg:
            continue
        flags.append({
            "severity": _enum(f.get("severity"), ("info", "warning", "error"), "warning"),
            "code": _strip_str(f.get("code")),
            "message": msg,
        })
    base["continuity_flags"] = flags
    rev = {**base["revision"], **(raw.get("revision") or {})}
    rev["version"] = int(rev.get("version") or 1)
    rev["status"] = _enum(rev.get("status"), ("draft", "review", "accepted"), "draft")
    rev["user_notes"] = _strip_str(rev.get("user_notes"))
    base["revision"] = rev
    return base


# ---------------------------------------------------------------------------
# 契约校验（轻量，不依赖 jsonschema）
# ---------------------------------------------------------------------------


def validate_contract(
    payload: dict[str, Any],
    contract: str,
) -> list[str]:
    """返回校验问题列表；空列表表示通过基本结构检查。"""
    issues: list[str] = []
    normalizers = {
        "planning_profile": normalize_planning_profile,
        "gap_diagnosis": normalize_gap_diagnosis,
        "scenario_set": normalize_scenario_set,
        "adaptive_roadmap": normalize_adaptive_roadmap,
        "story_bible": normalize_story_bible,
        "chapter_plan": normalize_chapter_plan,
        "chapter_draft": normalize_chapter_draft,
    }
    norm_fn = normalizers.get(contract)
    if not norm_fn:
        return [f"unknown contract: {contract}"]

    normalized = norm_fn(payload)
    if normalized.get("schema_version") != SCHEMA_VERSION:
        issues.append("schema_version mismatch")

    if contract == "planning_profile":
        if not normalized.get("anchors", {}).get("goal"):
            issues.append("anchors.goal is required for planning")
        for claim in normalized.get("stated_facts") or []:
            issues.extend(audit_attributed_claim(claim))
    elif contract == "gap_diagnosis":
        if not normalized.get("gaps"):
            issues.append("gaps must not be empty")
    elif contract == "scenario_set":
        if len(normalized.get("scenarios") or []) < 1:
            issues.append("scenarios must contain at least one item")
    elif contract == "adaptive_roadmap":
        for phase in normalized.get("phases") or []:
            if not phase.get("milestones"):
                issues.append(f"phase {phase.get('id')} missing milestones")
            if not phase.get("if_not_met", {}).get("adjustments"):
                issues.append(f"phase {phase.get('id')} missing if_not_met adjustments")
    elif contract == "chapter_plan":
        if not normalized.get("title") and not normalized.get("objectives"):
            issues.append("chapter plan needs title or objectives")
    elif contract == "chapter_draft":
        if not normalized.get("content"):
            issues.append("chapter draft content is empty")

    return issues


def snapshot_contract(payload: dict[str, Any]) -> dict[str, Any]:
    """深拷贝契约对象，供版本快照存储。"""
    return deepcopy(payload)
