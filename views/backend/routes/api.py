import json
import os
import time

from flask import Blueprint, Response, jsonify, request, send_file, stream_with_context

from backend.agents import get_agent, list_agents, public_agent, run_agent
from backend.agents.envelope import (
    IDEMPOTENCY,
    agent_error,
    build_envelope,
    elapsed_ms,
    error_payload,
    idempotency_key,
    parse_run_payload,
)
from backend.agents.loader import load_manifest, load_workflow
from backend.config import SHARED_DIR
from backend.history.context import build_agent_context, resolve_agent_upstream_input
from backend.history.ephemeral import strip_ephemeral_audio
from backend.history.store import run_store
from backend.media_files import resolve_media_file

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


def _history_result_for_agent(agent_id: str, result: dict) -> dict:
    spec = get_agent(agent_id)
    if spec and callable(spec.get("strip_audio")):
        stripped = spec["strip_audio"](result)
        return stripped if isinstance(stripped, dict) else result
    stripped = strip_ephemeral_audio(result)
    return stripped if isinstance(stripped, dict) else result


@api_bp.get("/agents")
def api_list_agents():
    return jsonify({"agents": list_agents()})


@api_bp.get("/files")
def api_get_file():
    """
    Fetch a media file by path (absolute under MEDIA_ROOT, or relative like tts/<job>/audio.wav).
    Query: ?path=...
    curl -o out.wav "http://127.0.0.1:5000/api/files?path=/.../media/tts/f42f32216720/audio.wav"
    curl -o out.wav "http://127.0.0.1:5000/api/files?path=tts/f42f32216720/audio.wav"
    """
    path = request.args.get("path", "")
    target = resolve_media_file(path)
    if target is None:
        return jsonify({"error": "file not found or path not allowed"}), 404
    return send_file(target, as_attachment=False, download_name=target.name)


@api_bp.get("/agents/<agent_id>")
def api_get_agent(agent_id: str):
    agent = get_agent(agent_id)
    if not agent:
        return jsonify(error_payload("agent_not_found", "agent not found")), 404
    return jsonify(public_agent(agent, detail=True))


@api_bp.post("/agents/<agent_id>/run")
def api_run_agent(agent_id: str):
    spec = get_agent(agent_id)
    if not spec:
        return jsonify(error_payload("agent_not_found", "agent not found")), 404

    parsed = parse_run_payload(request.get_json(silent=True) or {})
    user_input = parsed["user_input"]
    options = parsed["options"]
    run_id = parsed["run_id"]
    request_id = parsed["request_id"]
    canonical_id = spec["id"]
    skill = spec.get("skill") or canonical_id

    if request_id:
        cached = IDEMPOTENCY.get(idempotency_key(skill, request_id))
        if cached is not None:
            status, body = cached
            return jsonify(body), status

    started = time.perf_counter()
    try:
        result = run_agent(canonical_id, user_input, **options)
    except KeyError:
        return jsonify(error_payload("agent_not_found", "agent not found")), 404
    except Exception as exc:  # noqa: BLE001 — surface agent errors to the UI
        body = error_payload(
            "internal_error",
            str(exc),
            request_id=request_id,
            skill=skill,
        )
        if request_id:
            IDEMPOTENCY.put(idempotency_key(skill, request_id), 500, body)
        return jsonify(body), 500

    response = build_envelope(
        spec=spec,
        request_id=request_id,
        user_input=user_input,
        result=result,
        latency_ms=elapsed_ms(started),
    )
    biz_error = agent_error(result)
    status = 400 if biz_error else 200
    if biz_error:
        response["error"] = biz_error

    if run_id:
        run = run_store.get_run(run_id)
        _, execution_order, node_map = _run_workflow_meta(run)
        agent_node_id = next(
            (nid for nid in execution_order if node_map.get(nid, {}).get("agent_id") == canonical_id),
            None,
        )
        record_node_id = agent_node_id or canonical_id
        run_store.record_agent_step(
            run_id,
            node_id=record_node_id,
            agent_id=canonical_id,
            params={"input": user_input, "options": options},
            result=_history_result_for_agent(canonical_id, result),
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
                response["run"], canonical_id, execution_order, node_map
            )

    if request_id:
        IDEMPOTENCY.put(idempotency_key(skill, request_id), status, response)
    return jsonify(response), status


@api_bp.post("/agents/<agent_id>/stream")
def api_stream_agent(agent_id: str):
    """SSE stream for agents that expose iter_synthesis_events (e.g. text-to-speech)."""
    spec = get_agent(agent_id)
    if not spec:
        return jsonify({"error": "agent not found"}), 404

    stream_fn = spec.get("stream")
    if not callable(stream_fn):
        return jsonify({"error": "agent does not support streaming"}), 400

    payload = request.get_json(silent=True) or {}
    user_input = payload.get("input", "")
    options = payload.get("options") or {}
    run_id = payload.get("run_id")

    def generate():
        sentences_meta: list[dict] = []
        error: str | None = None
        try:
            for event in stream_fn(user_input, **options):
                if not isinstance(event, dict):
                    continue
                ev = event.get("event")
                if ev == "sentence_start":
                    sentences_meta.append(
                        {
                            "index": event.get("sentence_index"),
                            "text": event.get("text") or "",
                            "duration_ms": None,
                        }
                    )
                elif ev == "sentence_end":
                    idx = event.get("sentence_index")
                    for row in sentences_meta:
                        if row.get("index") == idx:
                            if event.get("duration_ms") is not None:
                                row["duration_ms"] = event["duration_ms"]
                            break
                elif ev == "error":
                    error = event.get("error") or "tts_error"

                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as exc:  # noqa: BLE001
            err_payload = {"event": "error", "error": str(exc)}
            error = str(exc)
            yield f"data: {json.dumps(err_payload, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'event': 'done'}, ensure_ascii=False)}\n\n"

        if run_id:
            total = sum(int(s.get("duration_ms") or 0) for s in sentences_meta)
            history_result = {
                "output": (
                    f"合成 {len(sentences_meta)} 句"
                    + (f" / 总时长 {total}ms" if total else "")
                    + (f" · error={error}" if error else "")
                ),
                "text": user_input,
                "sentences": [
                    {
                        "index": s.get("index"),
                        "text": s.get("text"),
                        "duration_ms": s.get("duration_ms"),
                    }
                    for s in sentences_meta
                ],
                "meta": {
                    "agent": agent_id,
                    "ephemeral_audio": True,
                    "sentence_count": len(sentences_meta),
                    "total_duration_ms": total or None,
                    "streamed": True,
                },
            }
            if error:
                history_result["error"] = error
            history_result = strip_ephemeral_audio(history_result) or history_result

            run = run_store.get_run(run_id)
            _, execution_order, node_map = _run_workflow_meta(run)
            agent_node_id = next(
                (
                    nid
                    for nid in execution_order
                    if node_map.get(nid, {}).get("agent_id") == agent_id
                ),
                None,
            )
            record_node_id = agent_node_id or agent_id
            run_store.record_agent_step(
                run_id,
                node_id=record_node_id,
                agent_id=agent_id,
                params={"input": user_input, "options": options},
                result=history_result,
            )

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }
    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers=headers,
    )


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
        result=_history_result_for_agent(agent_id, result),
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
