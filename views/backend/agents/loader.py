"""从 agents/ 目录与 manifest 加载 Agent SDK。"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

from backend.config import SHARED_DIR, VIEWS_ROOT

REPO_ROOT = Path(VIEWS_ROOT).parent
AGENTS_ROOT = REPO_ROOT / "agents"
MANIFEST_PATH = Path(SHARED_DIR) / "agents.manifest.json"


def _load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _import_agent_module(agent_dir: Path) -> ModuleType:
    agent_file = agent_dir / "agent.py"
    if not agent_file.is_file():
        raise FileNotFoundError(f"Missing agent.py in {agent_dir}")

    module_name = f"verita_agent_{agent_dir.name.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, agent_file)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {agent_file}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module

    # 保留 agents/ 与各 agent 目录在 sys.path，供运行时 import（如 llm_extract、_lib）
    for path in (AGENTS_ROOT.resolve(), agent_dir.resolve()):
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)

    spec.loader.exec_module(module)
    return module


def load_manifest() -> dict:
    if not MANIFEST_PATH.is_file():
        return {"agents": [], "default_workflow": "demo-pipeline", "workflows": {}}
    return _load_json(MANIFEST_PATH)


def resolve_workflow_path(workflow_name: str | None = None) -> Path:
    manifest = load_manifest()
    name = workflow_name or manifest.get("default_workflow", "demo-pipeline")
    workflows = manifest.get("workflows", {})

    if name in workflows:
        return Path(SHARED_DIR) / workflows[name]

    # 兼容旧路径
    legacy = Path(SHARED_DIR) / "workflow.json"
    if legacy.is_file():
        return legacy

    return Path(SHARED_DIR) / "workflows" / f"{name}.json"


def load_workflow(workflow_name: str | None = None) -> dict:
    path = resolve_workflow_path(workflow_name)
    return _load_json(path)


def _load_examples(agent_dir: Path) -> list[dict[str, Any]]:
    """读取 agents/{id}/examples/*.json，供工作台 API 文档面板。"""
    examples_dir = agent_dir / "examples"
    if examples_dir.is_dir():
        items: list[dict[str, Any]] = []
        for path in sorted(examples_dir.glob("*.json")):
            try:
                data = _load_json(path)
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(data, dict):
                data.setdefault("id", path.stem)
                items.append(data)
        return items

    single = agent_dir / "examples.json"
    if single.is_file():
        try:
            data = _load_json(single)
        except (OSError, json.JSONDecodeError):
            return []
        if isinstance(data, list):
            return [row for row in data if isinstance(row, dict)]
        if isinstance(data, dict):
            return [data]
    return []


def load_external_agents() -> dict[str, dict]:
    """加载 agents/ 下已在 manifest 启用的 agent。"""
    manifest = load_manifest()
    loaded: dict[str, dict] = {}

    for entry in manifest.get("agents", []):
        if not entry.get("enabled", True):
            continue
        if entry.get("builtin"):
            continue

        agent_id = entry["id"]
        agent_dir = AGENTS_ROOT / entry.get("dir", agent_id)
        config_path = agent_dir / "config.json"
        if not config_path.is_file():
            continue

        config = _load_json(config_path)
        module = _import_agent_module(agent_dir)
        run_fn: Callable[..., dict] = getattr(module, "run", None)
        if run_fn is None:
            raise AttributeError(f"{agent_dir}/agent.py must define run()")

        schema = None
        schema_ref = config.get("schema_ref")
        if schema_ref:
            schema_file = agent_dir / schema_ref
            if schema_file.is_file():
                schema = _load_json(schema_file)

        skill = str(config.get("skill") or "").strip() or None

        loaded[agent_id] = {
            "id": agent_id,
            "name": config.get("name", agent_id),
            "description": config.get("description", ""),
            "version": config.get("version"),
            "skill": skill,
            "skill_version": config.get("skill_version"),
            "phase": config.get("phase"),
            "view": config.get("view", {"type": "default"}),
            "schema": schema,
            "examples": _load_examples(agent_dir),
            "source": str(agent_dir.relative_to(REPO_ROOT)),
            "run": run_fn,
            "stream": getattr(module, "iter_synthesis_events", None),
            "strip_audio": getattr(module, "strip_audio_from_result", None),
            "module": module,
        }

    return loaded
