"""把 AsrResult 收成 LS asr.transcribe 的 output。"""

from __future__ import annotations

from typing import Any

from _lib.asr.types import AsrResult


def duration_sec_from_result(result: AsrResult) -> float:
    ends: list[int] = []
    for sentence in result.sentences:
        if sentence.end_ms is not None:
            ends.append(int(sentence.end_ms))
        for word in sentence.words:
            if word.end_ms is not None:
                ends.append(int(word.end_ms))
    if not ends:
        return 0.0
    return round(max(ends) / 1000.0, 3)


def to_transcribe_output(
    result: AsrResult,
    *,
    enable_word_timestamps: bool = True,
) -> dict[str, Any]:
    words: list[dict[str, Any]] = []
    for sentence in result.sentences:
        for word in sentence.words:
            if not word.text:
                continue
            item: dict[str, Any] = {
                "text": word.text,
                "start_ms": word.start_ms,
                "end_ms": word.end_ms,
            }
            if word.confidence is not None:
                item["confidence"] = word.confidence
            words.append(item)

    cues = [
        {
            "text": sentence.text,
            "start_ms": sentence.start_ms,
            "end_ms": sentence.end_ms,
        }
        for sentence in result.sentences
        if sentence.text
    ]

    use_words = bool(enable_word_timestamps and words)
    return {
        "text": result.transcript,
        "duration_sec": duration_sec_from_result(result),
        "timestamp_granularity": "word" if use_words else "sentence",
        "words": words if use_words else [],
        "cues": cues,
    }
