"""v1 — 详细学术版句法成分分析。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from versions.common import normalize_sentence, run_llm_analysis

_DIR = Path(__file__).resolve().parent
API_VERSION = "v1"
PROFILE = "academic"


def load_prompt() -> str:
    return (_DIR / "prompt.txt").read_text(encoding="utf-8").strip()


def normalize_input(user_input: str, **kwargs: Any) -> dict[str, Any]:
    return {"sentence": normalize_sentence(user_input, **kwargs)}


def run(user_input: str, **kwargs: Any) -> dict[str, Any]:
    sentence = normalize_sentence(user_input, **kwargs)
    result = run_llm_analysis(
        api_version=API_VERSION,
        sentence=sentence,
        system_prompt=load_prompt(),
    )
    result.setdefault("meta", {})["profile"] = PROFILE
    result["meta"]["profile_label"] = "详细学术版"
    return result
