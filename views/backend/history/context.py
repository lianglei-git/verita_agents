"""Helpers for resolving upstream/downstream step context in a run."""

from __future__ import annotations

import json
from typing import Any

# Planning pipeline contract keys passed between agents
_PLANNING_KEYS = (
    "handoff",
    "universal",
    "collection",
    "twin",
    "profile",
    "planning_profile",
    "gap_diagnosis",
    "scenario_set",
    "selected_scenario",
    "roadmap",
    "plan",
)


def _step_output(step: dict[str, Any] | None) -> Any:
    if not step:
        return None
    result = step.get("result")
    if isinstance(result, dict) and "output" in result:
        return result["output"]
    return result


def _extract_structured_payload(result: dict[str, Any]) -> dict[str, Any]:
    """Pull planning-pipeline contracts from a single agent step result."""
    payload: dict[str, Any] = {}
    for key in _PLANNING_KEYS:
        val = result.get(key)
        if val is not None:
            payload[key] = val
    scenario_set = result.get("scenario_set")
    if isinstance(scenario_set, dict):
        if scenario_set.get("selected_scenario_id"):
            payload["selected_scenario_id"] = scenario_set["selected_scenario_id"]
        if scenario_set.get("selection_rationale"):
            payload["selection_rationale"] = scenario_set["selection_rationale"]
    return payload


def _merge_upstream_payloads(run: dict[str, Any], execution_order: list[str], idx: int) -> dict[str, Any]:
    """Merge structured outputs from all upstream steps (far → near, nearer wins)."""
    merged: dict[str, Any] = {}
    steps = run.get("steps") or {}
    for node_id in execution_order[:idx]:
        step = steps.get(node_id)
        if not step:
            continue
        result = step.get("result")
        if not isinstance(result, dict):
            continue
        extracted = _extract_structured_payload(result)
        if extracted:
            merged.update(extracted)
    return merged


def _agent_id_for_node(node_map: dict, node_id: str) -> str | None:
    node = node_map.get(node_id) or {}
    return node.get("agent_id")


def build_planning_handoff(
    merged: dict[str, Any],
    target_agent_id: str,
) -> dict[str, Any]:
    """Shape accumulated upstream data for a specific downstream agent."""
    if not merged:
        return {}

    handoff = dict(merged)

    if target_agent_id == "story-scenario":
        keys = ("profile", "planning_profile", "handoff", "gap_diagnosis", "heuristic_only")
        out = {k: handoff[k] for k in keys if k in handoff}
        if handoff.get("selected_scenario_id"):
            out["selected_scenario_id"] = handoff["selected_scenario_id"]
        if handoff.get("selection_rationale"):
            out["selection_rationale"] = handoff["selection_rationale"]
        scenario_set = handoff.get("scenario_set")
        if isinstance(scenario_set, dict):
            out["scenario_set"] = scenario_set
            if scenario_set.get("selected_scenario_id") and "selected_scenario_id" not in out:
                out["selected_scenario_id"] = scenario_set["selected_scenario_id"]
            if scenario_set.get("selection_rationale") and "selection_rationale" not in out:
                out["selection_rationale"] = scenario_set["selection_rationale"]
        return out

    if target_agent_id == "route-planner":
        out = {
            k: handoff[k]
            for k in ("profile", "planning_profile", "gap_diagnosis", "scenario_set", "heuristic_only")
            if k in handoff
        }
        scenario_set = handoff.get("scenario_set")
        if isinstance(scenario_set, dict) and scenario_set.get("selected_scenario_id"):
            out.setdefault("scenario_set", scenario_set)
        selected = handoff.get("selected_scenario")
        if selected and "scenario" not in out:
            out["scenario"] = selected
        return out

    if target_agent_id == "life-script-author":
        out: dict[str, Any] = {}
        nested: dict[str, Any] = {}
        for key in ("planning_profile", "profile", "gap_diagnosis", "scenario_set", "scenario_id"):
            if key in handoff:
                nested[key] = handoff[key]
        if nested:
            out["handoff"] = nested
        if handoff.get("roadmap"):
            out["roadmap"] = handoff["roadmap"]
        return out

    return handoff


def resolve_upstream_input(run: dict[str, Any], execution_order: list[str], node_map: dict) -> str:
    """Derive default agent input from the nearest upstream step output."""
    return str(run.get("source_input", ""))


def resolve_agent_upstream_input(
    run: dict[str, Any],
    agent_node_id: str,
    execution_order: list[str],
    node_map: dict,
) -> str:
    idx = execution_order.index(agent_node_id)
    target_agent_id = _agent_id_for_node(node_map, agent_node_id) or ""

    merged = _merge_upstream_payloads(run, execution_order, idx)
    if merged:
        shaped = build_planning_handoff(merged, target_agent_id)
        if shaped:
            return json.dumps(shaped, ensure_ascii=False)

    for node_id in reversed(execution_order[:idx]):
        step = run.get("steps", {}).get(node_id)
        if not step:
            continue
        result = step.get("result")
        if isinstance(result, dict):
            if result.get("twin") or result.get("universal"):
                payload: dict[str, Any] = {}
                if result.get("universal"):
                    payload["universal"] = result["universal"]
                if result.get("collection"):
                    payload["collection"] = result["collection"]
                if result.get("twin"):
                    payload["twin"] = result["twin"]
                if result.get("handoff"):
                    payload["handoff"] = result["handoff"]
                return json.dumps(payload, ensure_ascii=False)
            if result.get("plan"):
                return json.dumps({"plan": result["plan"]}, ensure_ascii=False)
        output = _step_output(step)
        if output is not None:
            return str(output)
    return str(run.get("source_input", ""))


def build_agent_context(
    run: dict[str, Any] | None,
    agent_id: str,
    execution_order: list[str],
    node_map: dict,
) -> dict[str, Any]:
    if not run:
        return {"upstream": [], "downstream": [], "current": None}

    agent_node_id = next(
        (nid for nid in execution_order if node_map.get(nid, {}).get("agent_id") == agent_id),
        None,
    )
    if not agent_node_id:
        return {"upstream": [], "downstream": [], "current": None}

    idx = execution_order.index(agent_node_id)
    steps = run.get("steps", {})

    def pack_node(node_id: str) -> dict[str, Any]:
        node = node_map.get(node_id, {"id": node_id})
        step = steps.get(node_id)
        return {
            "node_id": node_id,
            "label": node.get("label", node_id),
            "type": node.get("type"),
            "agent_id": node.get("agent_id"),
            "params": step.get("params") if step else None,
            "result": step.get("result") if step else None,
            "status": step.get("status") if step else "pending",
            "ran_at": step.get("ran_at") if step else None,
        }

    upstream = [pack_node(nid) for nid in execution_order[:idx]]
    downstream = [pack_node(nid) for nid in execution_order[idx + 1 :]]
    current = pack_node(agent_node_id)

    merged_upstream = _merge_upstream_payloads(run, execution_order, idx)
    suggested_input = build_planning_handoff(merged_upstream, agent_id) if merged_upstream else None

    return {
        "upstream": upstream,
        "downstream": downstream,
        "current": current,
        "suggested_input": suggested_input,
    }
