"""English Grammar Analyzer Agent - Main entry point."""

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

from ega_linguistic import analyze_sentence, is_spacy_available, load_model  # noqa: E402
from ega_mapper import map_to_pedagogical  # noqa: E402
from ega_warnings import check_grammar  # noqa: E402
from ega_export import export_to_csv, export_to_json  # noqa: E402


def run(user_input: str, **kwargs) -> dict[str, Any]:
    """
    Run English grammar analysis on input sentence.
    
    Args:
        user_input: English sentence to analyze
        **kwargs: Additional options (export_format: "json" | "csv")
    
    Returns:
        Analysis result dictionary with linguistic, pedagogical, warnings layers
    """
    sentence = user_input.strip()
    if not sentence:
        return {
            "error": "Empty input",
            "message": "Please provide an English sentence to analyze.",
        }
    
    result: dict[str, Any] = {
        "input": sentence,
        "linguistic": {},
        "pedagogical": {},
        "warnings": {},
        "export": {},
        "meta": {
            "agent": "english-grammar-analyzer",
            "version": "0.1.0",
        },
    }
    
    if not is_spacy_available():
        result["error"] = "spaCy not available"
        result["message"] = "Install spaCy and download en_core_web_sm model."
        return result
    
    try:
        nlp = load_model()
        
        linguistic = analyze_sentence(sentence, nlp)
        result["linguistic"] = linguistic
        result["meta"]["linguistic_status"] = "success"
        
        pedagogical = map_to_pedagogical(sentence, linguistic)
        result["pedagogical"] = pedagogical
        result["meta"]["pedagogical_status"] = pedagogical.get("status", "unknown")
        
        warnings_result = check_grammar(sentence, linguistic)
        result["warnings"] = warnings_result
        result["meta"]["warnings_checker"] = warnings_result.get("checker_used", "none")
        
        export_format = kwargs.get("export_format", "json")
        if export_format == "csv":
            result["export"]["csv"] = export_to_csv(result)
        else:
            result["export"]["json"] = export_to_json(result)
        
        result["output"] = f"Analyzed: {sentence[:60]}..."
        
        return result
    
    except Exception as e:
        result["error"] = "analysis_failed"
        result["message"] = str(e)
        import traceback
        result["traceback"] = traceback.format_exc()
        return result


def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: python agent.py '<English sentence>'")
        print("Example: python agent.py 'The quick brown fox jumps over the lazy dog.'")
        sys.exit(1)
    
    sentence = sys.argv[1]
    result = run(sentence)
    
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
