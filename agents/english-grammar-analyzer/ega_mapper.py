"""LLM-powered pedagogical structure mapper for English Grammar Analyzer."""

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

try:
    from _lib.llm import get_client, is_llm_available  # noqa: E402
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False

    def is_llm_available():  # type: ignore[misc]
        return False

    def get_client():  # type: ignore[misc]
        return None

try:
    import jsonschema
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False
    jsonschema = None


def load_schema() -> dict[str, Any]:
    """Load pedagogical analysis JSON Schema."""
    schema_path = _AGENT_DIR / "pedagogical.schema.json"
    with open(schema_path, encoding="utf-8") as f:
        return json.load(f)


def validate_pedagogical_output(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """
    Validate pedagogical analysis against JSON Schema.
    
    Args:
        data: Pedagogical analysis dictionary
    
    Returns:
        Tuple of (is_valid, error_messages)
    """
    if not JSONSCHEMA_AVAILABLE:
        return True, ["jsonschema not available, skipping validation"]
    
    schema = load_schema()
    errors = []
    
    try:
        jsonschema.validate(instance=data, schema=schema)
        return True, []
    except jsonschema.ValidationError as e:
        errors.append(f"Validation error: {e.message} at {'.'.join(str(p) for p in e.path)}")
    except jsonschema.SchemaError as e:
        errors.append(f"Schema error: {e.message}")
    
    return False, errors


def build_pedagogical_prompt(text: str, linguistic_evidence: dict[str, Any]) -> str:
    """
    Build LLM prompt for pedagogical structure mapping.
    
    Args:
        text: Original sentence
        linguistic_evidence: Output from ega_linguistic.analyze_sentence()
    
    Returns:
        System + user prompt string
    """
    tokens_summary = []
    for t in linguistic_evidence.get("tokens", []):
        tokens_summary.append(f"{t['text']}/{t['pos']}:{t['dep']}")
    
    token_str = " ".join(tokens_summary[:50])
    if len(linguistic_evidence.get("tokens", [])) > 50:
        token_str += " ..."
    
    noun_chunks_str = ", ".join([nc["text"] for nc in linguistic_evidence.get("noun_chunks", [])])
    
    verbs = linguistic_evidence.get("tense_features", {}).get("verbs", [])
    verb_str = ", ".join([f"{v['text']}({v['tense']})" for v in verbs])
    
    auxs = linguistic_evidence.get("tense_features", {}).get("auxiliaries", [])
    aux_str = ", ".join([a["text"] for a in auxs])
    
    modals = linguistic_evidence.get("tense_features", {}).get("modals", [])
    modal_str = ", ".join([m["text"] for m in modals])
    
    prompt = f"""You are a pedagogical grammar analyzer. Your task is to convert raw linguistic analysis into a structured pedagogical representation suitable for teaching English grammar.

**CRITICAL FORMATTING REQUIREMENTS:**
1. Sentence type MUST be detailed and descriptive, e.g.:
   - "imperative (negative)" NOT just "imperative"
   - "complex (adverbial clause + main clause + object clause)" NOT just "complex"
   - "simple (with formal subject and compound complement)" NOT just "simple"

2. For imperative sentences, subject MUST be null (not "you")

3. For formal subject "It", mark as {{"text": "It", "type": "formal subject"}}

4. Auxiliary verbs: only include actual auxiliaries (do, does, did, be, have, will, may, etc.), NOT prepositions or main verbs

5. Relations MUST explain specific clause relationships in pedagogical terms

**Input Sentence:**
"{text}"

**Linguistic Evidence (from spaCy dependency parser):**
- Tokens with POS and dependency labels: {token_str}
- Noun chunks: {noun_chunks_str}
- Verbs: {verb_str}
- Auxiliaries: {aux_str}
- Modals: {modal_str}

**Your Task:**
Generate a JSON object following this structure:

{{
  "original": "<exact input sentence>",
  "type": "<detailed sentence type classification>",
  "clauses": [
    {{
      "clause_type": "<main | adverbial subordinate | non-restrictive relative | ...>",
      "subordinator": "<conjunction if applicable>",
      "subject": {{"text": "...", "type": "..."}},
      "predicate": {{"verb": "...", "auxiliary": "..."}},
      "object": ...,
      "complement": ...,
      "adverbials": [...]
    }}
  ],
  "relations": "<natural language explanation of clause relationships>"
}}

**Example for reference:**

Example 1 - Imperative (negative):
Input: "Do not speak of your happiness to one less fortunate than yourself."
{{
  "type": "imperative (negative)",
  "clauses": [{{
    "clause_type": "main",
    "subject": null,
    "predicate": {{
      "verb": "speak",
      "auxiliary": "do not",
      "modifiers": [
        {{"type": "prepositional_phrase", "preposition": "of", "object": "your happiness", "function": "content (what to speak about)"}},
        {{"type": "prepositional_phrase", "preposition": "to", "object": {{"head": "one", "modifier": {{"type": "adjective_phrase", "text": "less fortunate than yourself"}}}}, "function": "recipient (to whom)"}}
      ]
    }},
    "object": null,
    "complement": null
  }}]
}}

Example 2 - Complex with adverbial + main + object clause:
Input: "When it comes to education, the majority of people believe that it is a lifetime study."
{{
  "type": "complex (adverbial clause + main clause + object clause)",
  "clauses": [
    {{
      "clause_type": "adverbial subordinate",
      "subordinator": "When",
      "subject": {{"text": "it", "type": "dummy pronoun"}},
      "predicate": {{"verb": "comes", "modifier": {{"type": "prepositional_phrase", "preposition": "to", "object": "education"}}}},
      "object": null
    }},
    {{
      "clause_type": "main",
      "subject": {{"text": "the majority of people", "head": "majority", "modifier": {{"type": "prepositional_phrase", "preposition": "of", "object": "people"}}}},
      "predicate": {{"verb": "believe"}},
      "object": {{
        "type": "noun_clause (object)",
        "subordinator": "that",
        "subject": {{"text": "it"}},
        "predicate": {{"verb": "is"}},
        "complement": {{"text": "a lifetime study", "modifier": {{"type": "attributive", "text": "lifetime", "modified": "study"}}}}
      }}
    }}
  ]
}}

**Guidelines:**
1. **Sentence type**: Be VERY specific. Examples:
   - "imperative (negative)" not just "imperative"
   - "complex (adverbial clause + main clause + object clause)" not just "complex" or "declarative"
   - "simple (with formal subject and compound complement)" for it-constructions
   - "simple (comparative)" for comparative structures

2. **Clauses**: Identify all clauses (main, subordinate, relative). For each:
   - `clause_type`: "main", "adverbial subordinate", "noun_clause (object)", "non-restrictive relative", etc.
   - `subordinator` or `relative_pronoun`: If present (e.g., "When", "that", "which"). Use `preposition` field for fronted prepositions like "for which"
   - `subject`: **MUST be null for imperative sentences** (do not include implicit "you"). Use {{"text": "it", "type": "dummy pronoun"}} or {{"text": "It", "type": "formal subject"}} for expletive constructions
   - `predicate`: Must include `verb`; include `auxiliary` if present (e.g., "do not", "may give"). Include `modifiers` array for prepositional phrases with `function` labels (e.g., "content (what to speak about)", "recipient (to whom)", "time", "place", "manner")
   - `object`, `complement`: Identify type (noun_clause, infinitive_phrase, adjective_phrase, etc.). For compound structures, use arrays
   - `adverbials`: List adverbial modifiers with `type`, `text`, and `function` (time, place, manner, degree, etc.)

3. **Relations**: Explain how clauses relate (e.g., "Predicate 'speak' governs two prepositional phrases as adverbial modifiers", "The 'that'-clause functions as object of 'believe'")

4. **Evidence-based**: Only include structures supported by the linguistic evidence. Do not invent text spans not in the original sentence.

5. **Special structures to handle**:
   - **Imperative**: subject MUST be null, not "you"
   - **Formal subject**: Use {{"text": "It", "type": "formal subject"}} and include `true_subject` field with infinitive phrases
   - **Compound objects/complements**: Use arrays with individual items (coordinate with "and"/"but")
   - **Prepositional phrases**: Include in `predicate.modifiers` with `function` field (e.g., "content", "recipient", "time", "place")
   - **Comparative structures**: Use `comparison_marker` and `comparison_object` in complement
   - **Non-restrictive relative clauses**: Use `relative_pronoun` field, note `preposition` for fronted prep (e.g., "for which"), include `antecedent`

6. **Critical formatting rules**:
   - Use exact field names from schema: `clause_type`, `subordinator`, `relative_pronoun`, `preposition`, `modifiers`, `function`
   - For type labels: use underscores (e.g., "noun_clause", "infinitive_phrase", "adjective_phrase", "prepositional_phrase")
   - Include detailed function annotations: "content (what to speak about)", "recipient (to whom)", "time", "place", "manner", "degree", "topic"

Output ONLY valid JSON matching the schema. No additional commentary.
"""
    return prompt


def map_to_pedagogical(
    text: str,
    linguistic_evidence: dict[str, Any],
    max_retries: int = 1
) -> dict[str, Any]:
    """
    Map linguistic evidence to pedagogical structure using LLM.
    
    Args:
        text: Original sentence
        linguistic_evidence: Output from ega_linguistic.analyze_sentence()
        max_retries: Number of retry attempts if validation fails
    
    Returns:
        Pedagogical analysis dictionary with status field
    """
    client = get_client()
    if client is None:
        return {
            "status": "unavailable",
            "message": "LLM not available. Install openai and set API key.",
            "original": text,
        }
    
    prompt = build_pedagogical_prompt(text, linguistic_evidence)
    
    for attempt in range(max_retries + 1):
        try:
            result = client.chat_json(prompt)
            
            if result is None:
                continue
            
            is_valid, errors = validate_pedagogical_output(result)
            
            if is_valid:
                result["status"] = "success"
                result["validation_errors"] = []
                return result
            else:
                if attempt < max_retries:
                    continue
                else:
                    result["status"] = "validation_failed"
                    result["validation_errors"] = errors
                    return result
        
        except Exception as e:
            if attempt < max_retries:
                continue
            else:
                return {
                    "status": "error",
                    "message": str(e),
                    "original": text,
                }
    
    return {
        "status": "failed_after_retries",
        "message": f"Failed after {max_retries + 1} attempts",
        "original": text,
    }


def main():
    """CLI entry point for testing pedagogical mapper."""
    if len(sys.argv) < 2:
        print("Usage: python ega_mapper.py '<sentence>'")
        sys.exit(1)
    
    sentence = sys.argv[1]
    
    try:
        from ega_linguistic import analyze_sentence, is_spacy_available, load_model
        
        if not is_spacy_available():
            print("Error: spaCy not available")
            sys.exit(1)
        
        nlp = load_model()
        linguistic = analyze_sentence(sentence, nlp)
        
        pedagogical = map_to_pedagogical(sentence, linguistic)
        
        print(json.dumps(pedagogical, indent=2, ensure_ascii=False))
    
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
