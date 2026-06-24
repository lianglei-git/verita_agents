import json
import os

from flask import Blueprint, jsonify, request

from backend.agents import get_agent, list_agents, run_agent
from backend.agents.loader import load_manifest, load_workflow
from backend.config import SHARED_DIR
from backend.history.context import build_agent_context, resolve_agent_upstream_input
from backend.history.store import run_store

api_bp = Blueprint("api", __name__, url_prefix="/api")


def _load_json(filename: str) -> dict:
    path = os.path.join(SHARED_DIR, filename)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _workflow_meta(workflow_name: str | None = None) -> tuple[dict, list[str], dict]:
    workflow = load_workflow(workflow_name)
    execution_order = workflow.get("execution_order", [])
    node_map = {node["id"]: node for node in workflow.get("nodes", [])}
    return workflow, execution_order, node_map


def _run_workflow_meta(run: dict | None) -> tuple[dict, list[str], dict]:
    name = run.get("workflow_name") if run else None
    return _workflow_meta(name)


@api_bp.get("/agents")
def api_list_agents():
    return jsonify({"agents": list_agents()})


@api_bp.get("/agents/<agent_id>")
def api_get_agent(agent_id: str):
    agent = get_agent(agent_id)
    if not agent:
        return jsonify({"error": "agent not found"}), 404
    return jsonify(
        {
            "id": agent["id"],
            "name": agent["name"],
            "description": agent["description"],
            "view": agent.get("view", {"type": "default"}),
            "schema": agent.get("schema"),
            "source": agent.get("source"),
        }
    )


@api_bp.post("/agents/<agent_id>/run")
def api_run_agent(agent_id: str):
    payload = request.get_json(silent=True) or {}
    user_input = payload.get("input", "")
    options = payload.get("options") or {}
    run_id = payload.get("run_id")

    try:
        result = run_agent(agent_id, user_input, **options)
    except KeyError:
        return jsonify({"error": "agent not found"}), 404
    except Exception as exc:  # noqa: BLE001 — surface agent errors to the UI
        return jsonify({"error": str(exc)}), 500

    response = {
        "agent_id": agent_id,
        "input": user_input,
        "result": result,
    }

    if run_id:
        run = run_store.get_run(run_id)
        _, execution_order, node_map = _run_workflow_meta(run)
        agent_node_id = next(
            (nid for nid in execution_order if node_map.get(nid, {}).get("agent_id") == agent_id),
            None,
        )
        record_node_id = agent_node_id or agent_id
        run_store.record_agent_step(
            run_id,
            node_id=record_node_id,
            agent_id=agent_id,
            params={"input": user_input, "options": options},
            result=result,
        )
        if isinstance(user_input, str) and user_input.strip().startswith("{"):
            run_store.update_source_input(run_id, user_input)
        run = run_store.get_run(run_id)
        if run and agent_node_id:
            if all(nid in run["steps"] for nid in execution_order if node_map[nid]["type"] == "agent"):
                run_store.mark_completed(run_id)
        response["run"] = run_store.get_run(run_id)
        if agent_node_id:
            response["context"] = build_agent_context(
                response["run"], agent_id, execution_order, node_map
            )

    return jsonify(response)


@api_bp.get("/workflow")
def api_workflow():
    workflow_name = request.args.get("name")
    return jsonify(load_workflow(workflow_name))


@api_bp.get("/workflows")
def api_list_workflows():
    manifest = load_manifest()
    items = []
    for wf_id, rel_path in manifest.get("workflows", {}).items():
        wf = load_workflow(wf_id)
        items.append(
            {
                "id": wf_id,
                "name": wf.get("name", wf_id),
                "description": wf.get("description", ""),
                "path": rel_path,
            }
        )
    return jsonify(
        {
            "default": manifest.get("default_workflow", "demo-pipeline"),
            "workflows": items,
        }
    )


@api_bp.get("/spec")
def api_spec():
    return jsonify(_load_json("api-spec.json"))


@api_bp.post("/runs")
def api_create_run():
    payload = request.get_json(silent=True) or {}
    source_input = payload.get("source_input", "")
    workflow_key = payload.get("workflow") or payload.get("workflow_name")
    workflow, _, _ = _workflow_meta(workflow_key)
    run = run_store.create_run(workflow.get("name", "workflow"), source_input)
    return jsonify({"run": run}), 201


@api_bp.patch("/runs/<run_id>/input")
def api_update_run_input(run_id: str):
    payload = request.get_json(silent=True) or {}
    source_input = payload.get("source_input", "")
    run = run_store.update_source_input(run_id, source_input)
    if not run:
        return jsonify({"error": "run not found"}), 404
    return jsonify({"run": run})


@api_bp.get("/runs")
def api_list_runs():
    return jsonify({"runs": run_store.list_runs()})


@api_bp.get("/runs/<run_id>")
def api_get_run(run_id: str):
    run = run_store.get_run(run_id)
    if not run:
        return jsonify({"error": "run not found"}), 404
    return jsonify({"run": run})


@api_bp.get("/runs/<run_id>/context/<agent_id>")
def api_run_context(run_id: str, agent_id: str):
    run = run_store.get_run(run_id)
    if not run:
        return jsonify({"error": "run not found"}), 404
    _, execution_order, node_map = _run_workflow_meta(run)
    context = build_agent_context(run, agent_id, execution_order, node_map)
    return jsonify({"run_id": run_id, "agent_id": agent_id, **context})


@api_bp.post("/runs/<run_id>/execute/<agent_id>")
def api_execute_in_run(run_id: str, agent_id: str):
    run = run_store.get_run(run_id)
    if not run:
        return jsonify({"error": "run not found"}), 404

    payload = request.get_json(silent=True) or {}
    options = payload.get("options") or {}
    _, execution_order, node_map = _run_workflow_meta(run)

    agent_node_id = next(
        (nid for nid in execution_order if node_map.get(nid, {}).get("agent_id") == agent_id),
        None,
    )
    if not agent_node_id:
        return jsonify({"error": "agent not in workflow"}), 400

    user_input = payload.get("input")
    if user_input is None:
        user_input = resolve_agent_upstream_input(run, agent_node_id, execution_order, node_map)

    try:
        result = run_agent(agent_id, user_input, **options)
    except KeyError:
        return jsonify({"error": "agent not found"}), 404
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 500

    run_store.record_agent_step(
        run_id,
        node_id=agent_node_id,
        agent_id=agent_id,
        params={"input": user_input, "options": options},
        result=result,
    )

    if isinstance(user_input, str) and user_input.strip().startswith("{"):
        run_store.update_source_input(run_id, user_input)

    updated_run = run_store.get_run(run_id)
    agent_node_ids = [nid for nid in execution_order if node_map.get(nid, {}).get("type") == "agent"]
    if updated_run and all(nid in updated_run["steps"] for nid in agent_node_ids):
        run_store.mark_completed(run_id)
        updated_run = run_store.get_run(run_id)

    context = build_agent_context(updated_run, agent_id, execution_order, node_map)
    return jsonify(
        {
            "run": updated_run,
            "agent_id": agent_id,
            "input": user_input,
            "result": result,
            "context": context,
        }
    )
