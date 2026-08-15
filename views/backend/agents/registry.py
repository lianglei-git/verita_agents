"""Agent registry — 合并 agents/ 外部 SDK 与 views 内置示例。"""

from __future__ import annotations

from typing import Any

from backend.agents.envelope import ENVELOPE_ERRORS
from backend.agents.loader import load_external_agents


def _summarize_agent(user_input: str, **kwargs) -> dict:
    words = [w for w in user_input.split() if w.strip()]
    return {
        "output": f"字数: {len(user_input)}，词数: {len(words)}",
        "meta": {"agent": "summarize", "char_count": len(user_input), "word_count": len(words)},
    }


_BUILTIN: dict[str, dict] = {
    "summarize": {
        "id": "summarize",
        "name": "Summarize Agent",
        "description": "统计输入文本的字数与词数",
        "view": {"type": "default"},
        "source": "views/backend/agents/registry.py",
        "run": _summarize_agent,
        "examples": [],
    },
}


def _index_lookup(specs: dict[str, dict]) -> dict[str, dict]:
    """id 与 skill 都指向同一 spec；不覆盖已有 id。"""
    lookup: dict[str, dict] = {}
    for spec in specs.values():
        lookup[spec["id"]] = spec
    for spec in specs.values():
        skill = str(spec.get("skill") or "").strip()
        if skill and skill not in lookup:
            lookup[skill] = spec
    return lookup


def _build_registry() -> dict[str, dict]:
    specs: dict[str, dict] = {}
    specs.update(_BUILTIN)
    specs.update(load_external_agents())
    return _index_lookup(specs)


AGENTS: dict[str, dict] = _build_registry()


def _unique_specs() -> list[dict]:
    seen: set[str] = set()
    items: list[dict] = []
    for spec in AGENTS.values():
        agent_id = spec["id"]
        if agent_id in seen:
            continue
        seen.add(agent_id)
        items.append(spec)
    return items


def public_agent(spec: dict[str, Any], *, detail: bool = False) -> dict[str, Any]:
    skill = spec.get("skill")
    body: dict[str, Any] = {
        "id": spec["id"],
        "name": spec["name"],
        "description": spec["description"],
        "view": spec.get("view", {"type": "default"}),
        "schema": spec.get("schema"),
        "source": spec.get("source"),
        "phase": spec.get("phase"),
        "version": spec.get("version"),
        "skill": skill,
        "endpoint": f"/api/agents/{skill or spec['id']}/run",
    }
    if detail:
        body["examples"] = spec.get("examples") or []
        body["errors"] = ENVELOPE_ERRORS
    return body


def list_agents() -> list[dict]:
    return [public_agent(spec) for spec in _unique_specs()]


def get_agent(agent_id: str) -> dict | None:
    return AGENTS.get(agent_id)


def run_agent(agent_id: str, user_input: str, **kwargs) -> dict:
    spec = get_agent(agent_id)
    if not spec:
        raise KeyError(f"Unknown agent: {agent_id}")
    return spec["run"](user_input, **kwargs)


def reload_agents() -> None:
    """开发时重新扫描 manifest（可选调用）。"""
    global AGENTS
    AGENTS = _build_registry()
