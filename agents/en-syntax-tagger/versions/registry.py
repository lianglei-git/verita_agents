"""API version registry — v1 academic / v2 teaching / v3 json_data."""

from __future__ import annotations

from typing import Any

from versions.v1 import handler as v1_handler
from versions.v2 import handler as v2_handler
from versions.v3 import handler as v3_handler

DEFAULT_VERSION = "v1"
SUPPORTED_VERSIONS = ("v1", "v2", "v3")

_HANDLERS = {
    "v1": v1_handler,
    "v2": v2_handler,
    "v3": v3_handler,
}


def resolve_api_version(explicit: str | None = None, **kwargs: Any) -> str:
    raw = explicit or kwargs.get("version") or kwargs.get("api_version") or DEFAULT_VERSION
    ver = str(raw).strip().lower()
    if not ver.startswith("v") and ver.isdigit():
        ver = f"v{ver}"
    # aliases
    aliases = {
        "a": "v1",
        "academic": "v1",
        "b": "v2",
        "teaching": "v2",
        "c": "v3",
        "json": "v3",
        "json_data": "v3",
    }
    ver = aliases.get(ver, ver)
    if ver not in _HANDLERS:
        return DEFAULT_VERSION
    return ver


def get_handler(version: str):
    return _HANDLERS[resolve_api_version(version)]


def list_versions() -> list[dict[str, str]]:
    return [
        {
            "id": "v1",
            "status": "implemented",
            "profile": "academic",
            "summary": "详细学术版：主干/修饰/特殊结构/树形/成分表/语义角色",
            "prompt": "versions/v1/prompt.txt",
        },
        {
            "id": "v2",
            "status": "implemented",
            "profile": "teaching",
            "summary": "对比学习版：主干概括 + 片段表 + 结构树 + 难点说明",
            "prompt": "versions/v2/prompt.txt",
        },
        {
            "id": "v3",
            "status": "implemented",
            "profile": "json_data",
            "summary": "JSON数据版：clauses/constituents(含下标)/chunks/tokens/grammars",
            "prompt": "versions/v3/prompt.txt",
        },
    ]
