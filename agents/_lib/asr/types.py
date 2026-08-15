"""ASR result types."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class AsrWord:
    text: str
    start_ms: int | None = None
    end_ms: int | None = None
    punctuation: str = ""
    confidence: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None and v != ""}


@dataclass
class AsrSentence:
    index: int
    text: str
    start_ms: int | None = None
    end_ms: int | None = None
    words: list[AsrWord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "text": self.text,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "words": [w.to_dict() for w in self.words],
        }


@dataclass
class AsrResult:
    transcript: str
    sentences: list[AsrSentence] = field(default_factory=list)
    raw: Any = None

    def to_subtitles(self) -> list[dict[str, Any]]:
        return [s.to_dict() for s in self.sentences]
