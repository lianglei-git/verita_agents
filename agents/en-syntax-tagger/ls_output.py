"""把 v1 analysis 收成 LS sentence.analyze / sentence/1.0。"""

from __future__ import annotations

from typing import Any

BCP47_TO_LABEL = {
    "en": "英语",
    "ja": "日语",
    "zh": "中文",
    "zh-CN": "中文",
    "zh-Hans": "中文",
}

LABEL_TO_BCP47 = {
    "英语": "en",
    "英文": "en",
    "日语": "ja",
    "日文": "ja",
    "中文": "zh-CN",
    "汉语": "zh-CN",
}

PROFILE_TO_VERSION = {
    "academic": "v1",
    "teaching": "v2",
    "json": "v3",
    "json_data": "v3",
}


def to_label(value: str | None, default: str = "英语") -> str:
    raw = (value or "").strip()
    if not raw:
        return default
    if raw in BCP47_TO_LABEL:
        return BCP47_TO_LABEL[raw]
    if raw in LABEL_TO_BCP47:
        return raw
    return raw


def to_bcp47(value: str | None, default: str = "en") -> str:
    raw = (value or "").strip()
    if not raw:
        return default
    if raw == "zh":
        return "zh-CN"
    if raw in BCP47_TO_LABEL:
        return raw if raw != "zh" else "zh-CN"
    return LABEL_TO_BCP47.get(raw, raw)


def phonetic_notation(lang: str) -> str:
    code = to_bcp47(lang, "")
    if code.startswith("zh"):
        return "pinyin"
    if code.startswith("ja"):
        return "kana"
    return "IPA"


def normalize_ls_kwargs(user_input: str, kwargs: dict[str, Any]) -> dict[str, Any]:
    """LS 扁平字段 → 现有 handler 的 sentence / native_lang / learn_lang。"""
    text = kwargs.get("text") or user_input or kwargs.get("sentence") or ""
    learning = kwargs.get("learning_language") or kwargs.get("learn_lang")
    support = kwargs.get("support_language") or kwargs.get("native_lang")
    profile = str(kwargs.get("profile") or "academic").strip() or "academic"
    out = dict(kwargs)
    out["sentence"] = str(text).strip()
    out["learn_lang"] = to_label(learning, "英语")
    out["native_lang"] = to_label(support, "中文")
    if not kwargs.get("version") and not kwargs.get("api_version"):
        out["version"] = PROFILE_TO_VERSION.get(profile, "v1")
    return out


def to_sentence_analyze_output(
    result: dict[str, Any],
    *,
    learning_language: str,
    support_language: str,
    profile: str = "academic",
    user_level: str | None = None,
    goal: str | None = None,
) -> dict[str, Any]:
    analysis = result.get("analysis") if isinstance(result.get("analysis"), dict) else {}
    sentence = str(analysis.get("sentence") or result.get("input") or "")
    translation = str(analysis.get("translation") or "")
    target = to_bcp47(learning_language, "en")
    explain = to_bcp47(support_language, "zh-CN")
    src_meta = result.get("meta") if isinstance(result.get("meta"), dict) else {}
    status = "error" if result.get("error") else "success"
    meta: dict[str, Any] = {
        "agent": src_meta.get("agent") or "en-syntax-tagger",
        "profile": profile or src_meta.get("profile") or "academic",
        "status": status,
        "package_version": str(src_meta.get("package_version") or "3.0.0"),
        "api_version": str(result.get("api_version") or src_meta.get("api_version") or "1.0"),
    }
    if user_level:
        meta["user_level"] = user_level
    if goal:
        meta["goal"] = goal

    i18n = {
        target: {
            "content": sentence,
            "phonetic": {
                "notation": phonetic_notation(target),
                "value": str(analysis.get("phonetic") or ""),
            },
        },
        explain: {
            "content": translation,
            "phonetic": {
                "notation": phonetic_notation(explain),
                "value": "",
            },
        },
    }

    return {
        "target_lang": target,
        "explain_lang": explain,
        "profile": profile or "academic",
        "sentence_type": analysis.get("sentence_type") or "",
        "tree": analysis.get("tree") or "",
        "trunk": analysis.get("trunk") if isinstance(analysis.get("trunk"), dict) else {},
        "modifiers": analysis.get("modifiers") if isinstance(analysis.get("modifiers"), list) else [],
        "constituent_table": (
            analysis.get("constituent_table")
            if isinstance(analysis.get("constituent_table"), list)
            else []
        ),
        "special_structures": (
            analysis.get("special_structures")
            if isinstance(analysis.get("special_structures"), dict)
            else {"clauses": [], "non_finites": []}
        ),
        "semantic_roles": (
            analysis.get("semantic_roles") if isinstance(analysis.get("semantic_roles"), list) else []
        ),
        "translation": translation,
        "i18n": i18n,
        "meta": meta,
    }
