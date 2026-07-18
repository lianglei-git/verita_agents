"""英文句法全量标记 Agent — LLM 全量标记 + spaCy token 类型。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_AGENT_DIR = Path(__file__).resolve().parent
_AGENTS_ROOT = _AGENT_DIR.parent
for path in (_AGENTS_ROOT, _AGENT_DIR):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from spacy_tokens import analyze_spacy  # noqa: E402

try:
    from _lib.llm import get_client, is_llm_available
except ImportError:

    def is_llm_available() -> bool:  # type: ignore[misc]
        return False

    def get_client():  # type: ignore[misc]
        return None


AGENT_ID = "en-syntax-tagger"
VERSION = "1.1.0"


def _load_prompt() -> str:
    return (_AGENT_DIR / "prompt.txt").read_text(encoding="utf-8").strip()


def run(user_input: str, **kwargs) -> dict[str, Any]:
    sentence = (user_input or "").strip()
    if not sentence:
        return {
            "error": "empty_input",
            "message": "Please provide an English sentence.",
            "meta": {"agent": AGENT_ID, "version": VERSION},
        }

    # spaCy first (always attempt; independent of LLM)
    spacy_result = analyze_spacy(sentence)
    spacy_tokens = spacy_result.get("tokens") or []

    result: dict[str, Any] = {
        "input": sentence,
        "analysis": {},
        "spacy_tokens": spacy_tokens,
        "meta": {
            "agent": AGENT_ID,
            "version": VERSION,
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

    system = _load_prompt()
    user_prompt = f"待分析英文句子：\n{sentence}"

    try:
        analysis = client.chat_json(user_prompt, system=system)
        if not isinstance(analysis, dict):
            result["error"] = "invalid_llm_response"
            result["message"] = "LLM did not return a JSON object."
            result["meta"]["llm_status"] = "invalid"
            result["output"] = f"spaCy tokens={len(spacy_tokens)}; LLM invalid"
            return result

        if not analysis.get("sentence"):
            analysis["sentence"] = sentence

        translation = (analysis.get("translation") or "")[:60]
        summary = " · ".join(
            p
            for p in (
                analysis.get("sentence_type"),
                analysis.get("tense_voice"),
                translation,
            )
            if p
        )

        result["analysis"] = analysis
        result["output"] = summary or sentence
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


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python agent.py '<English sentence>'")
        sys.exit(1)
    print(json.dumps(run(sys.argv[1]), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
