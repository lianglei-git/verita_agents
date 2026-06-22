"""Agent registry — 合并 agents/ 外部 SDK 与 views 内置示例。"""

from __future__ import annotations

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
    },
}


def _build_registry() -> dict[str, dict]:
    registry: dict[str, dict] = {}
    registry.update(_BUILTIN)
    registry.update(load_external_agents())
    return registry


AGENTS: dict[str, dict] = _build_registry()


def list_agents() -> list[dict]:
    return [
        {
            "id": spec["id"],
            "name": spec["name"],
            "description": spec["description"],
            "view": spec.get("view", {"type": "default"}),
            "schema": spec.get("schema"),
            "source": spec.get("source"),
            "phase": spec.get("phase"),
            "version": spec.get("version"),
        }
        for spec in AGENTS.values()
    ]


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
