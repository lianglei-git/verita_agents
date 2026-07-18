"""Acceptance scorer for English Grammar Analyzer - field-level approximate matching."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

_AGENT_DIR = Path(__file__).resolve().parent


def load_rules() -> dict[str, Any]:
    """Load acceptance rules."""
    rules_path = _AGENT_DIR / "acceptance.rules.json"
    with open(rules_path, encoding="utf-8") as f:
        return json.load(f)


def load_golden_cases() -> list[dict[str, Any]]:
    """Load golden test cases."""
    golden_path = _AGENT_DIR / "fixtures" / "golden_cases.json"
    with open(golden_path, encoding="utf-8") as f:
        return json.load(f)


def normalize_text(text: str, rules: dict[str, Any]) -> str:
    """
    Normalize text for comparison.
    
    Args:
        text: Input text
        rules: Normalization rules from acceptance.rules.json
    
    Returns:
        Normalized text
    """
    if not isinstance(text, str):
        return str(text)
    
    norm_config = rules.get("normalization", {}).get("text", {})
    
    normalized = text
    
    if norm_config.get("lowercase"):
        normalized = normalized.lower()
    
    punc_variants = norm_config.get("punctuation_variants", {})
    for old, new in punc_variants.items():
        normalized = normalized.replace(old, new)
    
    if norm_config.get("strip_whitespace"):
        normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    return normalized


def levenshtein_ratio(s1: str, s2: str) -> float:
    """
    Calculate Levenshtein similarity ratio (0-1).
    
    Args:
        s1, s2: Strings to compare
    
    Returns:
        Similarity ratio
    """
    if s1 == s2:
        return 1.0
    
    if not s1 or not s2:
        return 0.0
    
    len1, len2 = len(s1), len(s2)
    if abs(len1 - len2) > max(len1, len2) * 0.5:
        return 0.0
    
    matrix = [[0] * (len2 + 1) for _ in range(len1 + 1)]
    
    for i in range(len1 + 1):
        matrix[i][0] = i
    for j in range(len2 + 1):
        matrix[0][j] = j
    
    for i in range(1, len1 + 1):
        for j in range(1, len2 + 1):
            cost = 0 if s1[i-1] == s2[j-1] else 1
            matrix[i][j] = min(
                matrix[i-1][j] + 1,
                matrix[i][j-1] + 1,
                matrix[i-1][j-1] + cost
            )
    
    distance = matrix[len1][len2]
    max_len = max(len1, len2)
    return 1.0 - (distance / max_len) if max_len > 0 else 1.0


def compare_field(expected: Any, actual: Any, field_path: str, rules: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    """
    Compare a single field with approximate matching.
    
    Args:
        expected: Expected value
        actual: Actual value
        field_path: Dot-separated field path
        rules: Acceptance rules
    
    Returns:
        Tuple of (similarity_score, diff_details)
    """
    if expected is None and actual is None:
        return 1.0, {}
    
    if expected is None or actual is None:
        return 0.0, {"path": field_path, "expected": expected, "actual": actual, "reason": "one_is_null"}
    
    if isinstance(expected, str) and isinstance(actual, str):
        norm_exp = normalize_text(expected, rules)
        norm_act = normalize_text(actual, rules)
        
        if norm_exp == norm_act:
            return 1.0, {}
        
        similarity = levenshtein_ratio(norm_exp, norm_act)
        
        return similarity, {
            "path": field_path,
            "expected": expected,
            "actual": actual,
            "normalized_expected": norm_exp,
            "normalized_actual": norm_act,
            "similarity": similarity,
        }
    
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        if expected == actual:
            return 1.0, {}
        else:
            return 0.0, {"path": field_path, "expected": expected, "actual": actual}
    
    if isinstance(expected, list) and isinstance(actual, list):
        if not expected and not actual:
            return 1.0, {}
        
        if not expected or not actual:
            return 0.5, {"path": field_path, "expected_len": len(expected) if expected else 0, "actual_len": len(actual) if actual else 0}
        
        min_len = min(len(expected), len(actual))
        max_len = max(len(expected), len(actual))
        
        similarities = []
        for i in range(min_len):
            exp_item = expected[i]
            act_item = actual[i]
            item_sim, _ = compare_field(exp_item, act_item, f"{field_path}[{i}]", rules)
            similarities.append(item_sim)
        
        penalty = (max_len - min_len) / max_len if max_len > 0 else 0
        avg_sim = (sum(similarities) / len(similarities) if similarities else 0.0) * (1 - penalty * 0.5)
        
        return avg_sim, {} if avg_sim >= 0.7 else {"path": field_path, "avg_similarity": avg_sim, "length_diff": max_len - min_len}
    
    if isinstance(expected, dict) and isinstance(actual, dict):
        if not expected and not actual:
            return 1.0, {}
        
        all_keys = set(expected.keys()) | set(actual.keys())
        if not all_keys:
            return 1.0, {}
        
        similarities = []
        for key in all_keys:
            exp_val = expected.get(key)
            act_val = actual.get(key)
            field_sim, _ = compare_field(exp_val, act_val, f"{field_path}.{key}", rules)
            similarities.append(field_sim)
        
        avg_sim = sum(similarities) / len(similarities) if similarities else 1.0
        return avg_sim, {} if avg_sim >= 0.8 else {"path": field_path, "avg_similarity": avg_sim}
    
    if type(expected) != type(actual):
        return 0.0, {"path": field_path, "expected_type": type(expected).__name__, "actual_type": type(actual).__name__}
    
    return 1.0 if expected == actual else 0.0, {}


def score_sentence(expected: dict[str, Any], actual: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
    """
    Score a single sentence against golden case.
    
    Args:
        expected: Golden case
        actual: Agent output pedagogical layer
        rules: Acceptance rules
    
    Returns:
        Score report dictionary
    """
    weights = rules.get("field_weights", {})
    
    hard_fields = weights.get("hard", {}).get("fields", [])
    structure_fields = weights.get("structure", {}).get("fields", [])
    soft_fields = weights.get("soft", {}).get("fields", [])
    
    hard_weight = weights.get("hard", {}).get("weight", 0.4)
    structure_weight = weights.get("structure", {}).get("weight", 0.35)
    soft_weight = weights.get("soft", {}).get("weight", 0.25)
    
    hard_scores = []
    structure_scores = []
    soft_scores = []
    field_diffs = []
    
    def extract_field_value(obj: dict, path: str) -> Any:
        """Extract field value from nested structure, handling arrays."""
        if '[]' in path:
            array_path, field_path = path.split('[]', 1)
            field_path = field_path.lstrip('.')
            
            array_obj = obj
            for part in array_path.split('.'):
                if not isinstance(array_obj, dict):
                    return None
                array_obj = array_obj.get(part)
                if array_obj is None:
                    return None
            
            if not isinstance(array_obj, list):
                return None
            
            if not field_path:
                return array_obj
            
            result = []
            for item in array_obj:
                parts = field_path.split('.')
                current = item
                for part in parts:
                    if not isinstance(current, dict):
                        current = None
                        break
                    current = current.get(part)
                    if current is None:
                        break
                if current is not None:
                    result.append(current)
            
            return result if result else None
        
        parts = path.split(".")
        current = obj
        for part in parts:
            if not isinstance(current, (dict, list)):
                return None
            if isinstance(current, list):
                if not current:
                    return None
                current = current[0]
            elif isinstance(current, dict):
                current = current.get(part)
            if current is None:
                return None
        return current
    
    for field in hard_fields:
        exp_val = extract_field_value(expected, field)
        act_val = extract_field_value(actual, field)
        similarity, diff = compare_field(exp_val, act_val, field, rules)
        hard_scores.append(similarity)
        if diff:
            field_diffs.append({"category": "hard", **diff})
    
    for field in structure_fields:
        exp_val = extract_field_value(expected, field)
        act_val = extract_field_value(actual, field)
        similarity, diff = compare_field(exp_val, act_val, field, rules)
        structure_scores.append(similarity)
        if diff:
            field_diffs.append({"category": "structure", **diff})
    
    for field in soft_fields:
        exp_val = extract_field_value(expected, field)
        act_val = extract_field_value(actual, field)
        similarity, diff = compare_field(exp_val, act_val, field, rules)
        soft_scores.append(similarity)
        if diff:
            field_diffs.append({"category": "soft", **diff})
    
    hard_avg = sum(hard_scores) / len(hard_scores) if hard_scores else 1.0
    structure_avg = sum(structure_scores) / len(structure_scores) if structure_scores else 1.0
    soft_avg = sum(soft_scores) / len(soft_scores) if soft_scores else 1.0
    
    total_score = (hard_avg * hard_weight + 
                   structure_avg * structure_weight + 
                   soft_avg * soft_weight)
    
    thresholds = rules.get("thresholds", {})
    single_min = thresholds.get("single_sentence_min", 0.85)
    
    return {
        "total_score": total_score,
        "hard_score": hard_avg,
        "structure_score": structure_avg,
        "soft_score": soft_avg,
        "status": "PASS" if total_score >= single_min else "FAIL",
        "field_diffs": field_diffs,
    }


def run_acceptance_test(agent_outputs: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Run full acceptance test on agent outputs.
    
    Args:
        agent_outputs: List of agent pedagogical outputs (must match golden cases order)
    
    Returns:
        Full acceptance report
    """
    rules = load_rules()
    golden_cases = load_golden_cases()
    
    if len(agent_outputs) != len(golden_cases):
        return {
            "status": "ERROR",
            "message": f"Expected {len(golden_cases)} outputs, got {len(agent_outputs)}",
        }
    
    sentence_scores = []
    all_hard_scores = []
    
    for i, (golden, actual) in enumerate(zip(golden_cases, agent_outputs)):
        score_report = score_sentence(golden, actual, rules)
        sentence_scores.append({
            "sentence_id": i + 1,
            "original": golden.get("original", ""),
            **score_report,
        })
        all_hard_scores.append(score_report["hard_score"])
    
    total_scores = [s["total_score"] for s in sentence_scores]
    avg_score = sum(total_scores) / len(total_scores) if total_scores else 0.0
    hard_avg = sum(all_hard_scores) / len(all_hard_scores) if all_hard_scores else 0.0
    
    thresholds = rules.get("thresholds", {})
    avg_min = thresholds.get("average_min", 0.88)
    hard_min = thresholds.get("hard_fields_min", 0.92)
    
    overall_pass = (avg_score >= avg_min and hard_avg >= hard_min)
    
    return {
        "status": "PASS" if overall_pass else "FAIL",
        "average_score": avg_score,
        "hard_fields_average": hard_avg,
        "sentence_scores": sentence_scores,
        "thresholds": {
            "average_min": avg_min,
            "hard_fields_min": hard_min,
        },
    }


def main():
    """CLI entry point for acceptance scoring."""
    print("=== English Grammar Analyzer Acceptance Test ===\n")
    
    golden_cases = load_golden_cases()
    print(f"Loaded {len(golden_cases)} golden test cases.\n")
    
    print("To run full test, provide agent outputs JSON file:")
    print("  python ega_score.py outputs.json")
    print("\nExpected format: List of pedagogical outputs matching golden cases order\n")
    
    if len(sys.argv) > 1:
        output_file = Path(sys.argv[1])
        if not output_file.exists():
            print(f"Error: File not found: {output_file}")
            sys.exit(1)
        
        with open(output_file, encoding="utf-8") as f:
            agent_outputs = json.load(f)
        
        report = run_acceptance_test(agent_outputs)
        
        print("=== Test Report ===")
        print(f"Overall: {report['status']}")
        print(f"Average Score: {report['average_score']:.3f} (threshold: {report['thresholds']['average_min']})")
        print(f"Hard Fields Avg: {report['hard_fields_average']:.3f} (threshold: {report['thresholds']['hard_fields_min']})")
        print()
        
        for sentence_score in report.get("sentence_scores", []):
            status_icon = "✓" if sentence_score["status"] == "PASS" else "✗"
            print(f"{status_icon} Sentence {sentence_score['sentence_id']}: {sentence_score['total_score']:.3f}")
            if sentence_score["field_diffs"]:
                print(f"  {len(sentence_score['field_diffs'])} field differences")
        
        if report["status"] == "FAIL":
            print("\n=== Failed Fields ===")
            for sentence_score in report.get("sentence_scores", []):
                if sentence_score["status"] == "FAIL":
                    print(f"\nSentence {sentence_score['sentence_id']}: {sentence_score['original'][:60]}...")
                    for diff in sentence_score["field_diffs"][:5]:
                        print(f"  - {diff.get('path', 'unknown')}: similarity={diff.get('similarity', 'N/A')}")
        
        print(f"\n{'='*50}")
        print(f"FINAL: {report['status']}")
        sys.exit(0 if report["status"] == "PASS" else 1)
    
    else:
        print("Golden cases loaded. Ready for testing.")
        print(f"\nExample golden case 1:")
        print(json.dumps(golden_cases[0], indent=2, ensure_ascii=False)[:500] + "...")


if __name__ == "__main__":
    main()
