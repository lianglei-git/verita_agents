"""PRD v2 — 从文本理解 goal / current / universal（LLM 优先）。"""

from __future__ import annotations

from typing import Any

from llm_inference import understand_user_text
from universal_model import update_clarity


def absorb_text(
    universal: dict[str, Any],
    text: str,
    *,
    target: str | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """
    将自由文本并入 universal。
    target: anchor:goal | anchor:current | None(全量)
    返回 (universal, inferred_paths)
    """
    raw = (text or "").strip()
    if not raw:
        return universal, []

    if target and target.startswith("universal:"):
        universal, inferred, _source = understand_user_text(universal, raw, target=target)
        universal = update_clarity(universal)
        return universal, inferred

    universal, inferred, _source = understand_user_text(universal, raw, target=target)
    universal = update_clarity(universal)
    return universal, inferred
