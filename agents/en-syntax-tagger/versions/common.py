"""Shared LLM + spaCy runner for all api_versions."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

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


DEFAULT_NATIVE_LANG = "中文"
DEFAULT_LEARN_LANG = "英语"


def normalize_sentence(user_input: str, **kwargs: Any) -> str:
    sentence = (user_input or "").strip()
    if not sentence and isinstance(kwargs.get("sentence"), str):
        sentence = kwargs["sentence"].strip()
    if not sentence and isinstance(kwargs.get("text"), str):
        sentence = kwargs["text"].strip()
    return sentence


def resolve_lang_options(**kwargs: Any) -> tuple[str, str]:
    """Return (native_lang, learn_lang) with defaults."""
    native = kwargs.get("native_lang")
    learn = kwargs.get("learn_lang")
    native_lang = str(native).strip() if native is not None else ""
    learn_lang = str(learn).strip() if learn is not None else ""
    if not native_lang:
        native_lang = DEFAULT_NATIVE_LANG
    if not learn_lang:
        learn_lang = DEFAULT_LEARN_LANG
    return native_lang, learn_lang


def render_prompt(template: str, *, native_lang: str, learn_lang: str) -> str:
    """Inject language options. Placeholders: {{native_lang}} / {{learn_lang}}."""
    return (
        template.replace("{{native_lang}}", native_lang).replace(
            "{{learn_lang}}", learn_lang
        )
    )


def build_user_prompt(sentence: str, *, learn_lang: str) -> str:
    return f"待分析的{learn_lang}句子：\n{sentence}"


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
    native_lang: str = DEFAULT_NATIVE_LANG,
    learn_lang: str = DEFAULT_LEARN_LANG,
    ensure_sentence_field: bool = True,
) -> dict[str, Any]:
    """
    Always attach spaCy tokens; call LLM with the given system prompt.
    Returns unified envelope with analysis / spacy_tokens / meta.
    """
    lang_meta = {
        "native_lang": native_lang,
        "learn_lang": learn_lang,
    }

    if not sentence:
        return {
            "input": sentence,
            "api_version": api_version,
            "analysis": {},
            "spacy_tokens": [],
            "error": "empty_input",
            "message": f"Please provide a {learn_lang} sentence.",
            "meta": {
                "api_version": api_version,
                "llm_status": "skipped",
                **lang_meta,
            },
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
            **lang_meta,
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

    prompt = user_prompt or build_user_prompt(sentence, learn_lang=learn_lang)

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
