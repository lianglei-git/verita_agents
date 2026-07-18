# English Grammar Analyzer - Acceptance Criteria

## Product Scope

### In Scope
- **Linguistic Analysis**: Token-level part-of-speech tagging, dependency parsing, lemmatization, named entity recognition for noun phrases
- **Pedagogical Structure**: Sentence type classification, clause segmentation, subject-predicate-object-complement identification, subordinate/coordinate clause relationships
- **Grammar Warnings**: Subject-verb agreement checking, tense consistency hints
- **Structured Export**: JSON (full analysis) and CSV (token-level + clause summary)
- **Visualization**: Dependency tree diagram, pedagogical clause tree display

### Out of Scope (v1)
- Multi-sentence discourse analysis or coreference resolution
- Chinese input or mixed Chinese-English parsing
- Writing improvement suggestions or stylistic rewrites
- Integration with course compiler pipeline (future work)

---

## Output Contract

Each analysis returns a three-layer result:

### Layer 1: `linguistic` (Deterministic Evidence)
Powered by spaCy `en_core_web_sm` or `en_core_web_md`. Fields:

| Field | Type | Description |
|-------|------|-------------|
| `tokens` | `list[dict]` | `text`, `lemma`, `pos`, `tag`, `dep`, `head_idx`, `is_stop` |
| `noun_chunks` | `list[dict]` | `text`, `start_idx`, `end_idx`, `root_text` |
| `sentence_count` | `int` | Number of sentences detected |
| `tense_features` | `dict` | Detected tense markers per clause (if identifiable) |
| `displacy_data` | `dict` | Compatible format for displacy dependency visualizer |

### Layer 2: `pedagogical` (Target Acceptance Format)
Generated via LLM with linguistic evidence. Must match the schema of golden cases:

| Field | Type | Description | Acceptance Weight |
|-------|------|-------------|-------------------|
| `original` | `str` | Original sentence (exact match required) | **High** |
| `type` | `str` | Sentence classification (e.g., "imperative (negative)", "complex (adverbial clause + main clause + object clause)") | **High** |
| `clauses` | `list[dict]` | Array of clause objects, each containing `clause_type`, `subject`, `predicate`, `object`, `complement`, `adverbials` | **High** |
| `clauses[].clause_type` | `str` | E.g., "main", "adverbial subordinate", "non-restrictive relative" | **High** |
| `clauses[].subordinator` | `str\|null` | E.g., "When", "that", "for which" | **High** |
| `clauses[].subject` | `dict\|null` | May include `text`, `type` (e.g., "dummy pronoun", "formal subject"), `head`, `modifier` | **High** |
| `clauses[].predicate` | `dict` | Must include `verb`; may include `auxiliary`, `modifiers` | **Medium** |
| `clauses[].object` | `dict\|null\|list` | May be noun_clause, infinitive_phrase, or plain text | **Medium** |
| `clauses[].complement` | `dict\|null\|list` | Adjective, infinitive, or compound structures | **Medium** |
| `relations` | `str` | Natural language explanation of inter-clause relationships | **Low** |

### Layer 3: `warnings` (Grammar Hints)
Powered by LanguageTool (fallback to heuristic rules if unavailable):

| Field | Type | Description |
|-------|------|-------------|
| `warnings` | `list[dict]` | `message`, `offset`, `length`, `rule_id`, `suggestions` |
| `checker_used` | `str` | "LanguageTool" or "spacy_heuristic" |

---

## Golden Test Cases

The following 7 sentences are **canonical acceptance fixtures**. Agent output must achieve field-level approximate match:

1. **Imperative (negative) with prepositional modifiers**  
   `"Do not speak of your happiness to one less fortunate than yourself."`
   - Key test: `subject: null`, `auxiliary: "do not"`, two PP modifiers with `function` labels

2. **Complex (adverbial + main + object clauses)**  
   `"When it comes to education, the majority of people believe that it is a lifetime study."`
   - Key test: three-clause structure, dummy pronoun `it`, noun clause object

3. **Complex (cause/reason clause)**  
   `"I'm so sorry that he should be so careless."`
   - Key test: `that`-clause as complement/adverbial of reason, degree adverbs

4. **Complex (main + non-restrictive relative)**  
   `"Later they may give performances in pubs or clubs, for which they are paid in cash."`
   - Key test: `for which` preposition fronting, antecedent tracking

5. **Simple (formal subject + compound complement)**  
   `"It is easy to open a shop but hard to keep it always open."`
   - Key test: `It` formal subject, parallel infinitive true subjects, object complement

6. **Simple (comparative)**  
   `"Nothing is more important than to receive education."`
   - Key test: comparative marker `than`, infinitive as comparison object

7. **Simple (compound infinitive object)**  
   `"People began to concentrate less on religious themes and adopt a more humanistic attitude to life."`
   - Key test: two coordinated infinitive phrases as direct object, each with adverbials/post-modifiers

---

## Approximate Match Scoring Algorithm

### Normalization Rules
Before comparing fields, apply:
- Lowercase conversion (except proper nouns in examples)
- Strip extra whitespace / punctuation variants (e.g., en-dash vs hyphen)
- Canonicalize article/determiner differences where semantically equivalent

### Field Weights & Thresholds

| Category | Fields | Weight | Acceptance Threshold |
|----------|--------|--------|----------------------|
| **Hard fields** | `original` (exact), `type` (normalized), `clause_type`, `subordinator`, subject nullness/formal status | 0.4 | ≥ 0.92 avg |
| **Structure fields** | `predicate.verb`, `auxiliary`, object/complement type labels, PP prepositions | 0.35 | ≥ 0.85 avg |
| **Soft fields** | `function` descriptions, `relations` narrative | 0.25 | Keyword coverage ≥ 0.70 |

### Per-Sentence Pass Criteria
- **Single sentence score**: ≥ 0.85
- **7-sentence average**: ≥ 0.88
- **Hard field subset average**: ≥ 0.92

### Score Calculation Details
1. For each golden case, compute field-by-field similarity (Levenshtein ratio for strings, structural recursion for nested dicts)
2. Weight by category, sum to sentence score
3. Aggregate across 7 cases
4. Output: `{sentence_id, score, field_diffs: [{field_path, expected, actual, similarity}]}`

---

## Operations Manual for Review Agents

### Running Acceptance Tests

```bash
cd /home/yizhun/桌面/zayne/verita_agents/agents/english-grammar-analyzer
python ega_score.py
```

Expected output:
```
=== Acceptance Score Report ===
Sentence 1: 0.89 (PASS)
Sentence 2: 0.91 (PASS)
...
Sentence 7: 0.87 (PASS)
---
Average: 0.88 | Hard Fields: 0.93
OVERALL: PASS
```

### Interpreting Diffs
When score < threshold, the report will show:
```json
{
  "sentence_id": 2,
  "score": 0.82,
  "status": "FAIL",
  "field_diffs": [
    {
      "path": "clauses[0].subject.type",
      "expected": "dummy pronoun",
      "actual": "expletive",
      "similarity": 0.60
    }
  ]
}
```

**Actions**:
- If `similarity < 0.7` on hard field: Flag as regression, block release
- If consistent pattern (e.g., all "dummy pronoun" → "expletive"): Review if LLM prompt/schema needs update
- If isolated failure: Investigate linguistic evidence layer first

### When to Update Golden Cases
Golden cases are **immutable** unless:
1. Discovered error in human annotation (requires 2+ reviewer consensus)
2. Major pedagogical standard change (e.g., adopting new grammar terminology)
3. Updating must go through approval + re-baseline all downstream tests

**Never** update golden cases to "fix" a failing test. Fix the agent logic instead.

---

## Machine-Readable Rules

See [`acceptance.rules.json`](acceptance.rules.json) for:
- Field path → weight mappings
- Normalization functions (regex patterns)
- Threshold constants
- Keyword sets for soft field matching

This file is consumed by `ega_score.py` and can be imported by external review agents.
