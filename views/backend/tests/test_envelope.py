"""P0 契约层：双 body、信封、幂等。"""

from __future__ import annotations

import unittest

from backend.agents.envelope import (
    IdempotencyCache,
    agent_error,
    build_envelope,
    extract_output,
    extract_usage,
    idempotency_key,
    parse_run_payload,
)


class ParseRunPayloadTest(unittest.TestCase):
    def test_views_body(self):
        parsed = parse_run_payload(
            {
                "input": "hello",
                "options": {"mode": "subtitle", "audio_url": "https://x"},
                "run_id": "run-1",
                "request_id": "01JABC",
            }
        )
        self.assertEqual(parsed["user_input"], "hello")
        self.assertEqual(parsed["options"]["mode"], "subtitle")
        self.assertEqual(parsed["run_id"], "run-1")
        self.assertEqual(parsed["request_id"], "01JABC")

    def test_ls_flat_body(self):
        parsed = parse_run_payload(
            {
                "request_id": "01JFLAT",
                "audio_url": "https://x/a.mp3",
                "language": "en",
                "enable_word_timestamps": True,
            }
        )
        self.assertEqual(parsed["user_input"], "")
        self.assertEqual(parsed["options"]["audio_url"], "https://x/a.mp3")
        self.assertEqual(parsed["options"]["language"], "en")
        self.assertTrue(parsed["options"]["enable_word_timestamps"])
        self.assertEqual(parsed["request_id"], "01JFLAT")
        self.assertIsNone(parsed["run_id"])

    def test_ls_text_becomes_input(self):
        parsed = parse_run_payload({"text": "I am.", "learning_language": "en"})
        self.assertEqual(parsed["user_input"], "I am.")
        self.assertEqual(parsed["options"]["learning_language"], "en")


class EnvelopeTest(unittest.TestCase):
    def test_extract_output_prefers_dict(self):
        self.assertEqual(extract_output({"output": {"text": "hi"}}), {"text": "hi"})

    def test_extract_output_drops_error(self):
        out = extract_output({"transcript": "hi", "error": "x", "message": "no"})
        self.assertEqual(out, {"transcript": "hi"})

    def test_usage_from_meta(self):
        usage = extract_usage({"meta": {"provider": "aliyun", "model": "p", "usage_sec": 3}}, 12)
        self.assertEqual(usage["provider"], "aliyun")
        self.assertEqual(usage["usage_sec"], 3)
        self.assertEqual(usage["latency_ms"], 12)

    def test_agent_error(self):
        self.assertEqual(
            agent_error({"error": "missing_audio_url", "message": "need url"}),
            {"code": "missing_audio_url", "message": "need url"},
        )
        self.assertIsNone(agent_error({"transcript": "ok"}))

    def test_build_envelope_keeps_result(self):
        spec = {"id": "speech-to-text", "skill": "asr.transcribe", "version": "1.1.0"}
        result = {"output": "subtitle · 1", "transcript": "hi", "meta": {"package_version": "1.1.0"}}
        body = build_envelope(
            spec=spec,
            request_id="01J",
            user_input="",
            result=result,
            latency_ms=8,
        )
        self.assertEqual(body["skill"], "asr.transcribe")
        self.assertEqual(body["agent_id"], "speech-to-text")
        self.assertEqual(body["result"], result)
        self.assertEqual(body["versions"]["package_version"], "1.1.0")


class IdempotencyTest(unittest.TestCase):
    def test_roundtrip(self):
        cache = IdempotencyCache(maxsize=2)
        key = idempotency_key("asr.transcribe", "01J")
        cache.put(key, 200, {"ok": True})
        self.assertEqual(cache.get(key), (200, {"ok": True}))

    def test_evicts_oldest(self):
        cache = IdempotencyCache(maxsize=1)
        cache.put("a", 200, {"n": 1})
        cache.put("b", 200, {"n": 2})
        self.assertIsNone(cache.get("a"))
        self.assertEqual(cache.get("b")[1]["n"], 2)


if __name__ == "__main__":
    unittest.main()
