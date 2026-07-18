"""Agent CLI 输入解析 — 支持 JSON 字符串或文件路径。"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def resolve_cli_input(
    argv: list[str] | None = None,
    *,
    default: str = "",
    fixture: Path | str | None = None,
) -> str:
    """解析 CLI 输入：argv[1] 为存在的文件路径时读取文件，否则当作 JSON/文本。"""
    args = argv if argv is not None else sys.argv
    if len(args) > 1:
        candidate = Path(args[1])
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
        return args[1]
    if fixture:
        path = Path(fixture)
        if path.is_file():
            return path.read_text(encoding="utf-8")
    return default
