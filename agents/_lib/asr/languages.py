"""BCP-47 → Paraformer language_hints。"""

from __future__ import annotations

BCP47_TO_HINT = {
    "en": "en",
    "ja": "ja",
    "zh": "zh",
    "zh-CN": "zh",
    "zh-Hans": "zh",
}

SUPPORTED_LEARNING_LANGS = ("en", "ja", "zh-CN")


def language_hints_for(language: str | None, fallback: tuple[str, ...] | None = None) -> list[str]:
    raw = (language or "").strip()
    if not raw:
        return list(fallback or ("zh", "en"))
    hint = BCP47_TO_HINT.get(raw) or BCP47_TO_HINT.get(raw.split("-")[0])
    if hint:
        return [hint]
    return [raw]
