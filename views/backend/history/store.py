"""In-memory execution run history."""

from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RunStore:
    def __init__(self) -> None:
        self._runs: dict[str, dict[str, Any]] = {}

    def create_run(self, workflow_name: str, source_input: str) -> dict[str, Any]:
        run_id = uuid.uuid4().hex[:12]
        run = {
            "id": run_id,
            "workflow_name": workflow_name,
            "status": "in_progress",
            "created_at": _now(),
            "updated_at": _now(),
            "source_input": source_input,
            "steps": {
                "input": {
                    "node_id": "input",
                    "type": "source",
                    "params": {"input": source_input},
                    "result": {"output": source_input},
                    "status": "success",
                    "ran_at": _now(),
                }
            },
        }
        self._runs[run_id] = run
        return deepcopy(run)

    def list_runs(self) -> list[dict[str, Any]]:
        items = sorted(self._runs.values(), key=lambda r: r["created_at"], reverse=True)
        return [
            {
                "id": run["id"],
                "workflow_name": run["workflow_name"],
                "status": run["status"],
                "created_at": run["created_at"],
                "updated_at": run["updated_at"],
                "source_input": run["source_input"],
                "step_count": len(run["steps"]),
            }
            for run in items
        ]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        run = self._runs.get(run_id)
        return deepcopy(run) if run else None

    def record_agent_step(
        self,
        run_id: str,
        *,
        node_id: str,
        agent_id: str,
        params: dict[str, Any],
        result: dict[str, Any],
        status: str = "success",
    ) -> dict[str, Any] | None:
        run = self._runs.get(run_id)
        if not run:
            return None

        run["steps"][node_id] = {
            "node_id": node_id,
            "type": "agent",
            "agent_id": agent_id,
            "params": params,
            "result": result,
            "status": status,
            "ran_at": _now(),
        }
        run["updated_at"] = _now()
        run["status"] = "in_progress"
        return deepcopy(run["steps"][node_id])

    def mark_completed(self, run_id: str) -> None:
        run = self._runs.get(run_id)
        if run:
            run["status"] = "completed"
            run["updated_at"] = _now()

    def update_source_input(self, run_id: str, source_input: str) -> dict[str, Any] | None:
        run = self._runs.get(run_id)
        if not run:
            return None
        run["source_input"] = source_input
        run["updated_at"] = _now()
        input_step = run["steps"].get("input")
        if input_step:
            input_step["params"] = {"input": source_input}
            input_step["result"] = {"output": source_input}
            input_step["ran_at"] = _now()
        return deepcopy(run)


run_store = RunStore()
