"""vocabulary.generate — 词条 + 文本例句，不回 object_id。"""

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

from _lib.llm import get_client, is_llm_available  # noqa: E402

AGENT_ID = "vocabulary-generate"
PACKAGE_VERSION = "1.0.0"
SKILL = "vocabulary.generate"
_FORBIDDEN = ("object_id", "asset_id", "activity_id")

_SYSTEM = (
    "You generate a learner vocabulary card. Reply with JSON only, no markdown. "
    "Shape: {lemma, phonetic:{notation,value}, pos:[], level, "
    "forms:{comparative,superlative,derived:[]}, "
    "senses:[{sense_id,gloss:{<lang>:...},example_texts:[{lang,text}]}]}. "
    "phonetic.notation is IPA or pinyin or kana or romaji. "
    "Examples are plain text only. Never include object_id, asset_id, or audio urls."
)


def phonetic_notation(lang: str) -> str:
    code = (lang or "").strip()
    if code.startswith("zh"):
        return "pinyin"
    if code.startswith("ja"):
        return "kana"
    return "IPA"


def strip_forbidden(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            k: strip_forbidden(v)
            for k, v in value.items()
            if k not in _FORBIDDEN
        }
    if isinstance(value, list):
        return [strip_forbidden(v) for v in value]
    return value


def fallback_card(
    lemma: str,
    *,
    learning: str,
    support: str,
    user_level: str,
    context: str,
) -> dict[str, Any]:
    return {
        "lemma": lemma,
        "phonetic": {"notation": phonetic_notation(learning), "value": ""},
        "pos": [],
        "level": user_level,
        "forms": {"comparative": None, "superlative": None, "derived": []},
        "senses": [
            {
                "sense_id": "s1",
                "gloss": {support: lemma, learning: lemma},
                "example_texts": [
                    {"lang": learning, "text": context or lemma},
                ],
            }
        ],
    }


def normalize_card(
    raw: dict[str, Any] | None,
    *,
    lemma: str,
    learning: str,
    support: str,
    user_level: str,
    context: str,
) -> dict[str, Any]:
    base = fallback_card(
        lemma, learning=learning, support=support, user_level=user_level, context=context
    )
    if not isinstance(raw, dict):
        return base
    clean = strip_forbidden(raw)
    if clean.get("lemma"):
        base["lemma"] = str(clean["lemma"])
    phonetic = clean.get("phonetic")
    if isinstance(phonetic, dict):
        notation = str(phonetic.get("notation") or phonetic_notation(learning))
        if notation not in {"IPA", "pinyin", "kana", "romaji"}:
            notation = phonetic_notation(learning)
        base["phonetic"] = {"notation": notation, "value": str(phonetic.get("value") or "")}
    if isinstance(clean.get("pos"), list):
        base["pos"] = [str(x) for x in clean["pos"] if x]
    if clean.get("level"):
        base["level"] = str(clean["level"])
    forms = clean.get("forms")
    if isinstance(forms, dict):
        base["forms"] = {
            "comparative": forms.get("comparative"),
            "superlative": forms.get("superlative"),
            "derived": list(forms.get("derived") or []) if isinstance(forms.get("derived"), list) else [],
        }
    senses = clean.get("senses")
    if isinstance(senses, list) and senses:
        normalized = []
        for i, sense in enumerate(senses):
            if not isinstance(sense, dict):
                continue
            gloss = sense.get("gloss") if isinstance(sense.get("gloss"), dict) else {}
            gloss = {str(k): str(v) for k, v in gloss.items() if k not in _FORBIDDEN}
            if learning not in gloss:
                gloss[learning] = lemma
            if support not in gloss:
                gloss[support] = gloss.get(learning) or lemma
            examples = []
            for ex in sense.get("example_texts") or []:
                if not isinstance(ex, dict):
                    continue
                examples.append(
                    {"lang": str(ex.get("lang") or learning), "text": str(ex.get("text") or "")}
                )
            if not examples:
                examples = [{"lang": learning, "text": context or lemma}]
            normalized.append(
                {
                    "sense_id": str(sense.get("sense_id") or f"s{i + 1}"),
                    "gloss": gloss,
                    "example_texts": examples,
                }
            )
        if normalized:
            base["senses"] = normalized
    return strip_forbidden(base)


def run(user_input: str, **kwargs: Any) -> dict[str, Any]:
    lemma = str(kwargs.get("lemma") or user_input or "").strip()
    context = str(kwargs.get("context") or "").strip()
    learning = str(kwargs.get("learning_language") or "en").strip() or "en"
    support = str(kwargs.get("support_language") or "zh-CN").strip() or "zh-CN"
    user_level = str(kwargs.get("user_level") or "").strip()
    goal = str(kwargs.get("goal") or "").strip()
    meta = {
        "agent": AGENT_ID,
        "package_version": PACKAGE_VERSION,
        "skill": SKILL,
    }
    if not lemma:
        return {
            "error": "empty_input",
            "message": "provide lemma",
            "output": fallback_card("", learning=learning, support=support, user_level=user_level, context=""),
            "usage": {"provider": "", "model": "", "tokens": 0, "usage_sec": 0, "cost_micros": None},
            "meta": meta,
        }

    raw = None
    tokens = 0
    model = ""
    if is_llm_available():
        client = get_client()
        if client is not None:
            payload = {
                "lemma": lemma,
                "context": context,
                "learning_language": learning,
                "support_language": support,
                "user_level": user_level,
                "goal": goal,
            }
            try:
                data = client.chat_json(json.dumps(payload, ensure_ascii=False), system=_SYSTEM)
                raw = data if isinstance(data, dict) else None
                stats = client.stats()
                tokens = int(stats.get("total_input_tokens") or 0) + int(
                    stats.get("total_output_tokens") or 0
                )
                model = getattr(client.cfg, "model", "") or ""
                meta["llm_status"] = "success"
            except Exception as exc:  # noqa: BLE001
                meta["llm_status"] = "error"
                meta["llm_error"] = str(exc)
        else:
            meta["llm_status"] = "unavailable"
    else:
        meta["llm_status"] = "unavailable"

    card = normalize_card(
        raw,
        lemma=lemma,
        learning=learning,
        support=support,
        user_level=user_level,
        context=context,
    )
    result: dict[str, Any] = {
        "output": card,
        "usage": {
            "provider": "llm" if tokens else "",
            "model": model,
            "tokens": tokens,
            "usage_sec": 0,
            "cost_micros": None,
        },
        "meta": meta,
    }
    if meta.get("llm_status") == "unavailable":
        result["error"] = "llm_unavailable"
        result["message"] = "LLM unavailable; returned structural fallback without object_id."
    return result


if __name__ == "__main__":
    print(
        json.dumps(
            run("emotive", learning_language="en", support_language="zh-CN", user_level="C1"),
            ensure_ascii=False,
            indent=2,
        )
    )
