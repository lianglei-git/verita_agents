"""spaCy token layer for en-syntax-tagger."""

from __future__ import annotations

from typing import Any

try:
    import spacy

    SPACY_AVAILABLE = True
except ImportError:
    spacy = None
    SPACY_AVAILABLE = False

_NLP = None


def is_spacy_available() -> bool:
    return SPACY_AVAILABLE


def load_model(model_name: str = "en_core_web_sm") -> Any:
    global _NLP
    if not SPACY_AVAILABLE:
        raise RuntimeError(
            "spaCy not installed. pip install spacy && python -m spacy download en_core_web_sm"
        )
    if _NLP is not None:
        return _NLP
    try:
        _NLP = spacy.load(model_name)
    except OSError:
        if model_name != "en_core_web_sm":
            _NLP = spacy.load("en_core_web_sm")
        else:
            raise RuntimeError(
                f"Model '{model_name}' not found. "
                f"Run: python -m spacy download {model_name}"
            ) from None
    return _NLP


def extract_spacy_tokens(text: str, nlp: Any = None) -> list[dict[str, Any]]:
    """
    Return spaCy token list with POS / tag / dep types for each word.
    """
    if nlp is None:
        nlp = load_model()
    doc = nlp(text)
    out: list[dict[str, Any]] = []
    for i, tok in enumerate(doc):
        head = tok.head
        out.append({
            "index": i,
            "text": tok.text,
            "lemma": tok.lemma_,
            "pos": tok.pos_,          # coarse type: NOUN, VERB, ADP, ...
            "tag": tok.tag_,          # fine Penn tag: NN, VBD, IN, ...
            "dep": tok.dep_,          # dependency relation
            "head_idx": head.i if head != tok else i,
            "head_text": head.text if head != tok else tok.text,
            "char_start": tok.idx,
            "char_end": tok.idx + len(tok.text),
            "is_stop": tok.is_stop,
            "is_punct": tok.is_punct,
            "is_alpha": tok.is_alpha,
            "morph": str(tok.morph) if tok.morph else "",
        })
    return out


def analyze_spacy(text: str) -> dict[str, Any]:
    """Run spaCy; return tokens + status."""
    if not is_spacy_available():
        return {
            "status": "unavailable",
            "message": "spaCy not installed",
            "tokens": [],
        }
    try:
        nlp = load_model()
        tokens = extract_spacy_tokens(text, nlp)
        return {
            "status": "success",
            "model": nlp.meta.get("name") or "en_core_web_sm",
            "tokens": tokens,
        }
    except Exception as e:  # noqa: BLE001
        return {
            "status": "error",
            "message": str(e),
            "tokens": [],
        }
