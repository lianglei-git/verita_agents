"""Export utilities for English Grammar Analyzer (JSON and CSV formats)."""

from __future__ import annotations

import csv
import io
import json
from typing import Any


def export_to_json(analysis_result: dict[str, Any]) -> str:
    """
    Export full analysis result to JSON string.
    
    Args:
        analysis_result: Complete analysis from agent.run()
    
    Returns:
        JSON string
    """
    return json.dumps(analysis_result, indent=2, ensure_ascii=False)


def export_to_csv(analysis_result: dict[str, Any]) -> str:
    """
    Export analysis to CSV format (token-level rows + optional clause summary).
    
    Args:
        analysis_result: Complete analysis from agent.run()
    
    Returns:
        CSV string
    """
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(["Layer", "Type", "Index", "Text", "POS", "Lemma", "Dep", "Head", "Details"])
    
    linguistic = analysis_result.get("linguistic", {})
    tokens = linguistic.get("tokens", [])
    
    for token in tokens:
        writer.writerow([
            "linguistic",
            "token",
            token.get("index", ""),
            token.get("text", ""),
            token.get("pos", ""),
            token.get("lemma", ""),
            token.get("dep", ""),
            token.get("head_idx", ""),
            "",
        ])
    
    pedagogical = analysis_result.get("pedagogical", {})
    if pedagogical and pedagogical.get("status") == "success":
        writer.writerow([])
        writer.writerow(["Layer", "Type", "Clause_Type", "Subject", "Verb", "Object", "Details"])
        
        clauses = pedagogical.get("clauses", [])
        for i, clause in enumerate(clauses):
            subject_text = ""
            if clause.get("subject"):
                if isinstance(clause["subject"], dict):
                    subject_text = clause["subject"].get("text", "")
                else:
                    subject_text = str(clause["subject"])
            
            verb_text = ""
            if clause.get("predicate"):
                if isinstance(clause["predicate"], dict):
                    verb_text = clause["predicate"].get("verb", "")
            
            object_text = ""
            if clause.get("object"):
                if isinstance(clause["object"], dict):
                    object_text = clause["object"].get("text", "") or str(clause["object"].get("type", ""))
                elif isinstance(clause["object"], str):
                    object_text = clause["object"]
            
            writer.writerow([
                "pedagogical",
                "clause",
                clause.get("clause_type", ""),
                subject_text,
                verb_text,
                object_text,
                json.dumps(clause, ensure_ascii=False)[:100],
            ])
    
    warnings = analysis_result.get("warnings", {}).get("warnings", [])
    if warnings:
        writer.writerow([])
        writer.writerow(["Layer", "Type", "Offset", "Message", "Suggestions"])
        
        for warning in warnings:
            suggestions = ", ".join(warning.get("suggestions", [])[:3])
            writer.writerow([
                "warnings",
                "grammar_issue",
                warning.get("offset", ""),
                warning.get("message", ""),
                suggestions,
            ])
    
    return output.getvalue()
