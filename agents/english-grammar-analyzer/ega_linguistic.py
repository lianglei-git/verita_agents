"""spaCy linguistic analysis layer for English Grammar Analyzer."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

try:
    import spacy
    from spacy.tokens import Doc, Token
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    spacy = None
    Doc = None
    Token = None


def is_spacy_available() -> bool:
    """Check if spaCy is installed and can be used."""
    return SPACY_AVAILABLE


def load_model(model_name: str = "en_core_web_sm") -> Any:
    """
    Load spaCy model. Falls back to en_core_web_sm if specified model unavailable.
    
    Args:
        model_name: spaCy model name (default: en_core_web_sm)
    
    Returns:
        Loaded spaCy nlp object
    
    Raises:
        RuntimeError: If spaCy not available or no English model can be loaded
    """
    if not SPACY_AVAILABLE:
        raise RuntimeError(
            "spaCy not available. Install with: pip install spacy && "
            "python -m spacy download en_core_web_sm"
        )
    
    try:
        nlp = spacy.load(model_name)
        return nlp
    except OSError:
        if model_name != "en_core_web_sm":
            try:
                nlp = spacy.load("en_core_web_sm")
                return nlp
            except OSError:
                pass
        raise RuntimeError(
            f"spaCy model '{model_name}' not found. "
            f"Download with: python -m spacy download {model_name}"
        )


def extract_tokens(doc: Doc) -> list[dict[str, Any]]:
    """
    Extract token-level linguistic features.
    
    Args:
        doc: spaCy Doc object
    
    Returns:
        List of token dictionaries with text, lemma, pos, tag, dep, head_idx, is_stop
    """
    tokens = []
    for i, token in enumerate(doc):
        tokens.append({
            "index": i,
            "text": token.text,
            "lemma": token.lemma_,
            "pos": token.pos_,
            "tag": token.tag_,
            "dep": token.dep_,
            "head_idx": token.head.i if token.head != token else i,
            "is_stop": token.is_stop,
            "is_punct": token.is_punct,
            "is_alpha": token.is_alpha,
        })
    return tokens


def extract_noun_chunks(doc: Doc) -> list[dict[str, Any]]:
    """
    Extract noun phrase chunks.
    
    Args:
        doc: spaCy Doc object
    
    Returns:
        List of noun chunk dictionaries
    """
    chunks = []
    for chunk in doc.noun_chunks:
        chunks.append({
            "text": chunk.text,
            "start_idx": chunk.start,
            "end_idx": chunk.end,
            "root_text": chunk.root.text,
            "root_dep": chunk.root.dep_,
        })
    return chunks


def detect_tense_features(doc: Doc) -> dict[str, Any]:
    """
    Detect tense and aspect features from verb forms.
    
    Args:
        doc: spaCy Doc object
    
    Returns:
        Dictionary with tense markers per sentence/clause
    """
    tense_info: dict[str, Any] = {
        "verbs": [],
        "auxiliaries": [],
        "modals": [],
    }
    
    for token in doc:
        if token.pos_ == "VERB":
            tense_info["verbs"].append({
                "text": token.text,
                "lemma": token.lemma_,
                "tag": token.tag_,
                "tense": _infer_tense(token),
                "index": token.i,
            })
        elif token.pos_ == "AUX":
            tense_info["auxiliaries"].append({
                "text": token.text,
                "lemma": token.lemma_,
                "tag": token.tag_,
                "index": token.i,
                "head_verb": token.head.text if token.head.pos_ == "VERB" else None,
            })
        elif token.tag_ == "MD":
            tense_info["modals"].append({
                "text": token.text,
                "index": token.i,
                "head_verb": token.head.text if token.head.pos_ in ("VERB", "AUX") else None,
            })
    
    return tense_info


def _infer_tense(token: Token) -> str:
    """
    Infer tense from verb tag.
    
    Args:
        token: spaCy Token
    
    Returns:
        Tense label string
    """
    tag = token.tag_
    if tag == "VB":
        return "base/infinitive"
    elif tag == "VBD":
        return "past"
    elif tag == "VBG":
        return "gerund/present_participle"
    elif tag == "VBN":
        return "past_participle"
    elif tag == "VBP":
        return "present (non-3rd person)"
    elif tag == "VBZ":
        return "present (3rd person singular)"
    else:
        return "unknown"


def generate_displacy_data(doc: Doc) -> dict[str, Any]:
    """
    Generate displacy-compatible dependency visualization data.
    
    Args:
        doc: spaCy Doc object
    
    Returns:
        Dictionary compatible with displacy.render(manual=True)
    """
    words = []
    arcs = []
    
    for token in doc:
        words.append({"text": token.text, "tag": token.pos_})
    
    for token in doc:
        if token.head != token:
            start = min(token.i, token.head.i)
            end = max(token.i, token.head.i)
            direction = "left" if token.i < token.head.i else "right"
            arcs.append({
                "start": start,
                "end": end,
                "label": token.dep_,
                "dir": direction,
            })
    
    return {"words": words, "arcs": arcs}


def analyze_sentence(text: str, nlp: Any = None) -> dict[str, Any]:
    """
    Perform full linguistic analysis on a sentence.
    
    Args:
        text: Input English sentence
        nlp: Pre-loaded spaCy model (optional, will load if None)
    
    Returns:
        Dictionary with tokens, noun_chunks, tense_features, displacy_data, sentence_count
    """
    if nlp is None:
        nlp = load_model()
    
    doc = nlp(text)
    
    result = {
        "text": text,
        "tokens": extract_tokens(doc),
        "noun_chunks": extract_noun_chunks(doc),
        "sentence_count": len(list(doc.sents)),
        "tense_features": detect_tense_features(doc),
        "displacy_data": generate_displacy_data(doc),
    }
    
    return result


def main():
    """CLI entry point for testing linguistic layer."""
    if len(sys.argv) < 2:
        print("Usage: python ega_linguistic.py '<sentence>'")
        print("Example: python ega_linguistic.py 'The quick brown fox jumps.'")
        sys.exit(1)
    
    sentence = sys.argv[1]
    
    if not is_spacy_available():
        print("Error: spaCy not available.")
        print("Install with: pip install spacy")
        print("Then download model: python -m spacy download en_core_web_sm")
        sys.exit(1)
    
    try:
        nlp = load_model()
        result = analyze_sentence(sentence, nlp)
        
        import json
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
