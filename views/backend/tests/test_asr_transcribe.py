"""P1：asr.transcribe 输出映射、语言码、路由。"""

from __future__ import annotations

import sys
import unittest

from backend.agents import get_agent
from backend.agents.loader import AGENTS_ROOT

if str(AGENTS_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENTS_ROOT))

from _lib.asr.format import to_transcribe_output  # noqa: E402
from _lib.asr.languages import language_hints_for  # noqa: E402
from _lib.asr.media import classify_url  # noqa: E402
from _lib.asr.types import AsrResult, AsrSentence, AsrWord  # noqa: E402


class LanguageHintsTest(unittest.TestCase):
    def test_bcp47(self):
        self.assertEqual(language_hints_for("en"), ["en"])
        self.assertEqual(language_hints_for("ja"), ["ja"])
        self.assertEqual(language_hints_for("zh-CN"), ["zh"])
        self.assertEqual(language_hints_for(None), ["zh", "en"])


class ClassifyUrlTest(unittest.TestCase):
    def test_kinds(self):
        self.assertEqual(classify_url("https://x/a.mp4"), "video")
        self.assertEqual(classify_url("https://x/a.mp3"), "audio")
        self.assertEqual(classify_url("https://x/signed"), "unknown")


class TranscribeOutputTest(unittest.TestCase):
    def test_word_granularity(self):
        result = AsrResult(
            transcript="I am.",
            sentences=[
                AsrSentence(
                    index=0,
                    text="I am.",
                    start_ms=100,
                    end_ms=800,
                    words=[
                        AsrWord(text="I", start_ms=100, end_ms=200, confidence=0.9),
                        AsrWord(text="am", start_ms=220, end_ms=800),
                    ],
                )
            ],
        )
        out = to_transcribe_output(result, enable_word_timestamps=True)
        self.assertEqual(out["text"], "I am.")
        self.assertEqual(out["duration_sec"], 0.8)
        self.assertEqual(out["timestamp_granularity"], "word")
        self.assertEqual(len(out["words"]), 2)
        self.assertEqual(out["cues"][0]["text"], "I am.")
        self.assertEqual(out["words"][0]["confidence"], 0.9)

    def test_sentence_fallback(self):
        result = AsrResult(
            transcript="Hi",
            sentences=[AsrSentence(index=0, text="Hi", start_ms=0, end_ms=500)],
        )
        out = to_transcribe_output(result, enable_word_timestamps=True)
        self.assertEqual(out["timestamp_granularity"], "sentence")
        self.assertEqual(out["words"], [])
        self.assertEqual(out["duration_sec"], 0.5)


class TranscribeRouteTest(unittest.TestCase):
    def test_ls_body_goes_subtitle(self):
        spec = get_agent("asr.transcribe")
        self.assertIsNotNone(spec)
        decide = spec["module"]._is_transcribe_request
        self.assertTrue(decide("", {"language": "en", "audio_url": "https://x/a.mp3"}))
        self.assertTrue(decide("subtitle", {}))
        self.assertFalse(decide("compare", {"audio_url": "https://x/a.mp3"}))
        self.assertFalse(decide("", {"reference": "hi"}))


if __name__ == "__main__":
    unittest.main()
