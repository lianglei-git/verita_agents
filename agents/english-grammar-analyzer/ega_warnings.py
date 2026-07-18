"""Grammar warnings for English Grammar Analyzer (LanguageTool + heuristic fallback)."""

from __future__ import annotations

from typing import Any

try:
    import language_tool_python
    LANGUAGETOOL_AVAILABLE = True
except ImportError:
    LANGUAGETOOL_AVAILABLE = False
    language_tool_python = None


def is_languagetool_available() -> bool:
    """Check if LanguageTool is available."""
    return LANGUAGETOOL_AVAILABLE


def check_with_languagetool(text: str) -> tuple[str, list[dict[str, Any]]]:
    """
    Check grammar using LanguageTool.
    
    Args:
        text: Input sentence
    
    Returns:
        Tuple of (checker_name, warnings_list)
    """
    if not LANGUAGETOOL_AVAILABLE:
        return "unavailable", []
    
    try:
        with language_tool_python.LanguageTool("en-US") as tool:
            matches = tool.check(text)
            
            warnings = []
            for match in matches:
                warnings.append({
                    "message": match.message,
                    "offset": match.offset,
                    "length": match.errorLength,
                    "rule_id": match.ruleId,
                    "category": match.category if hasattr(match, "category") else None,
                    "suggestions": match.replacements[:3] if match.replacements else [],
                })
            
            return "LanguageTool", warnings
    
    except Exception as e:
        return "LanguageTool (error)", [{"message": f"LanguageTool error: {e}", "offset": 0, "length": 0}]


def check_with_heuristic(linguistic_evidence: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Heuristic grammar checks based on spaCy linguistic analysis.
    
    Args:
        linguistic_evidence: Output from ega_linguistic.analyze_sentence()
    
    Returns:
        List of warning dictionaries
    """
    warnings = []
    tokens = linguistic_evidence.get("tokens", [])
    
    for i, token in enumerate(tokens):
        if token["dep"] == "nsubj" and i + 1 < len(tokens):
            verb_idx = token["head_idx"]
            if verb_idx < len(tokens):
                verb = tokens[verb_idx]
                
                if verb["pos"] == "VERB":
                    subject_is_plural = _is_plural_subject(token, tokens)
                    verb_is_plural = _is_plural_verb(verb)
                    
                    if subject_is_plural != verb_is_plural:
                        warnings.append({
                            "message": f"Possible subject-verb agreement issue: '{token['text']}' with '{verb['text']}'",
                            "offset": token["index"],
                            "length": 1,
                            "rule_id": "HEURISTIC_SV_AGREEMENT",
                            "suggestions": [],
                        })
    
    return warnings


def _is_plural_subject(token: dict[str, Any], tokens: list[dict[str, Any]]) -> bool | None:
    """Heuristic check if subject is plural."""
    tag = token["tag"]
    if tag in ("NNS", "NNPS"):
        return True
    if tag in ("NN", "NNP"):
        return False
    if token["text"].lower() in ("i", "you", "we", "they"):
        return True
    if token["text"].lower() in ("he", "she", "it"):
        return False
    return None


def _is_plural_verb(verb: dict[str, Any]) -> bool | None:
    """Heuristic check if verb form is plural."""
    tag = verb["tag"]
    if tag == "VBZ":
        return False
    if tag in ("VBP", "VB"):
        return True
    return None


def check_grammar(text: str, linguistic_evidence: dict[str, Any]) -> dict[str, Any]:
    """
    Check grammar using best available method.
    
    Args:
        text: Input sentence
        linguistic_evidence: Output from ega_linguistic.analyze_sentence()
    
    Returns:
        Dictionary with checker_used and warnings
    """
    if LANGUAGETOOL_AVAILABLE:
        checker, warnings = check_with_languagetool(text)
        return {
            "checker_used": checker,
            "warnings": warnings,
        }
    else:
        warnings = check_with_heuristic(linguistic_evidence)
        return {
            "checker_used": "spacy_heuristic",
            "warnings": warnings,
        }
