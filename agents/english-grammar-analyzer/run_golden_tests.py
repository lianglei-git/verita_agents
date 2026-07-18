"""Run agent on all golden cases and output pedagogical results for scoring."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_AGENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_AGENT_DIR))
sys.path.insert(0, str(_AGENT_DIR.parent))

from agent import run  # noqa: E402


def main():
    """Generate pedagogical outputs for all golden cases."""
    fixtures_path = _AGENT_DIR / "fixtures" / "golden_cases.json"
    
    with open(fixtures_path, encoding="utf-8") as f:
        golden_cases = json.load(f)
    
    print(f"Running agent on {len(golden_cases)} golden cases...")
    print("(This requires spaCy and LLM to be available)\n")
    
    pedagogical_outputs = []
    
    for i, case in enumerate(golden_cases, 1):
        sentence = case["original"]
        print(f"[{i}/{len(golden_cases)}] Analyzing: {sentence[:60]}...")
        
        try:
            result = run(sentence)
            pedagogical = result.get("pedagogical", {})
            
            if pedagogical.get("status") == "success":
                pedagogical_outputs.append(pedagogical)
                print(f"  ✓ Success")
            else:
                print(f"  ✗ Failed: {pedagogical.get('status')} - {pedagogical.get('message', 'unknown')}")
                pedagogical_outputs.append({
                    "original": sentence,
                    "type": "unknown",
                    "clauses": [],
                    "relations": "",
                    "status": pedagogical.get("status"),
                })
        
        except Exception as e:
            print(f"  ✗ Error: {e}")
            pedagogical_outputs.append({
                "original": sentence,
                "type": "unknown",
                "clauses": [],
                "relations": "",
                "error": str(e),
            })
    
    output_path = _AGENT_DIR / "test_outputs.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(pedagogical_outputs, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'='*60}")
    print(f"Outputs saved to: {output_path}")
    print(f"\nRun scoring with:")
    print(f"  python ega_score.py {output_path}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
