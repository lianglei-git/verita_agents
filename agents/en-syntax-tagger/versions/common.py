"""Shared LLM + spaCy runner for all api_versions."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

_AGENT_DIR = Path(__file__).resolve().parents[1]
if str(_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENT_DIR))

from spacy_tokens import analyze_spacy  # noqa: E402

try:
    from _lib.llm import get_client, is_llm_available
except ImportError:

    def is_llm_available() -> bool:  # type: ignore[misc]
        return False

    def get_client():  # type: ignore[misc]
        return None


def normalize_sentence(user_input: str, **kwargs: Any) -> str:
    sentence = (user_input or "").strip()
    if not sentence and isinstance(kwargs.get("sentence"), str):
        sentence = kwargs["sentence"].strip()
    return sentence


def build_output_summary(analysis: dict[str, Any], sentence: str) -> str:
    """Short human-readable output line."""
    parts = []
    for key in ("sentence_type", "type", "trunk"):
        val = analysis.get(key)
        if isinstance(val, str) and val.strip():
            parts.append(val.strip()[:80])
            break
    if analysis.get("translation"):
        parts.append(str(analysis["translation"])[:50])
    return " · ".join(parts) if parts else sentence


def run_llm_analysis(
    *,
    api_version: str,
    sentence: str,
    system_prompt: str,
    user_prompt: str | None = None,
    ensure_sentence_field: bool = True,
) -> dict[str, Any]:
    """
    Always attach spaCy tokens; call LLM with the given system prompt.
    Returns unified envelope with analysis / spacy_tokens / meta.
    """
    if not sentence:
        return {
            "input": sentence,
            "api_version": api_version,
            "analysis": {},
            "spacy_tokens": [],
            "error": "empty_input",
            "message": "Please provide an English sentence.",
            "meta": {"api_version": api_version, "llm_status": "skipped"},
        }

    spacy_result = analyze_spacy(sentence)
    spacy_tokens = spacy_result.get("tokens") or []

    result: dict[str, Any] = {
        "input": sentence,
        "api_version": api_version,
        "analysis": {},
        "spacy_tokens": spacy_tokens,
        "meta": {
            "api_version": api_version,
            "spacy_status": spacy_result.get("status"),
            "spacy_model": spacy_result.get("model"),
            "spacy_message": spacy_result.get("message"),
        },
    }

    if not is_llm_available():
        result["error"] = "llm_unavailable"
        result["message"] = "LLM unavailable. spaCy tokens (if any) are still returned."
        result["meta"]["llm_status"] = "unavailable"
        result["output"] = f"spaCy tokens={len(spacy_tokens)}; LLM unavailable"
        return result

    client = get_client()
    if client is None:
        result["error"] = "llm_unavailable"
        result["message"] = "Failed to create LLM client."
        result["meta"]["llm_status"] = "unavailable"
        result["output"] = f"spaCy tokens={len(spacy_tokens)}; LLM unavailable"
        return result

    prompt = user_prompt or f"待分析英文句子：\n{sentence}"

    try:
        analysis = client.chat_json(prompt, system=system_prompt)
        if not isinstance(analysis, dict):
            result["error"] = "invalid_llm_response"
            result["message"] = "LLM did not return a JSON object."
            result["meta"]["llm_status"] = "invalid"
            result["output"] = f"spaCy tokens={len(spacy_tokens)}; LLM invalid"
            return result

        if ensure_sentence_field and not analysis.get("sentence"):
            analysis["sentence"] = sentence

        result["analysis"] = analysis
        result["output"] = build_output_summary(analysis, sentence)
        result["meta"]["llm_status"] = "success"
        result["meta"]["llm_stats"] = client.stats()
        return result

    except Exception as e:  # noqa: BLE001
        import traceback

        result["error"] = "analysis_failed"
        result["message"] = str(e)
        result["traceback"] = traceback.format_exc()
        result["meta"]["llm_status"] = "error"
        result["output"] = f"spaCy tokens={len(spacy_tokens)}; LLM error"
        return result
