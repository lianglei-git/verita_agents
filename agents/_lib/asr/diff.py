"""Reference vs hypothesis diff — CJK by char, Latin runs by word."""

from __future__ import annotations

import difflib
import re
from typing import Any

_TOKEN_RE = re.compile(
    r"[A-Za-z0-9]+(?:'[A-Za-z]+)?|[^\sA-Za-z0-9]",
    re.UNICODE,
)


def tokenize(text: str) -> list[str]:
    """汉字/标点按字；连续 ASCII 字母数字按词。"""
    raw = (text or "").strip()
    if not raw:
        return []
    # collapse whitespace but keep content for matching
    compact = re.sub(r"\s+", " ", raw)
    return _TOKEN_RE.findall(compact)


def diff_tokens(reference: str, hypothesis: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Return (diff_ops, stats).
    ops: equal | replace | delete | insert
    """
    ref_toks = tokenize(reference)
    hyp_toks = tokenize(hypothesis)
    sm = difflib.SequenceMatcher(a=ref_toks, b=hyp_toks, autojunk=False)
    ops: list[dict[str, Any]] = []
    correct = 0

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            text = "".join(ref_toks[i1:i2])
            ops.append({"op": "equal", "text": text})
            correct += i2 - i1
        elif tag == "replace":
            ops.append(
                {
                    "op": "replace",
                    "ref": "".join(ref_toks[i1:i2]),
                    "hyp": "".join(hyp_toks[j1:j2]),
                }
            )
        elif tag == "delete":
            ops.append({"op": "delete", "ref": "".join(ref_toks[i1:i2])})
        elif tag == "insert":
            ops.append({"op": "insert", "hyp": "".join(hyp_toks[j1:j2])})

    ref_n = len(ref_toks)
    hyp_n = len(hyp_toks)
    accuracy = (correct / ref_n) if ref_n else (1.0 if hyp_n == 0 else 0.0)
    stats = {
        "ref_chars": ref_n,
        "hyp_chars": hyp_n,
        "correct": correct,
        "accuracy": round(accuracy, 4),
    }
    return ops, stats
