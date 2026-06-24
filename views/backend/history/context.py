"""Helpers for resolving upstream/downstream step context in a run."""

from __future__ import annotations

import json
from typing import Any


def _step_output(step: dict[str, Any] | None) -> Any:
    if not step:
        return None
    result = step.get("result")
    if isinstance(result, dict) and "output" in result:
        return result["output"]
    return result


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

    return {
        "upstream": upstream,
        "downstream": downstream,
        "current": current,
    }
