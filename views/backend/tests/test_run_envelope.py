"""P0：POST /api/agents/{id|skill}/run 信封与幂等。"""

from __future__ import annotations

import unittest

from backend.app import create_app


class RunEnvelopeHttpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()

    def test_summarize_envelope(self):
        res = self.client.post(
            "/api/agents/summarize/run",
            json={"input": "hello world", "options": {}, "request_id": "01JTESTSUM"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["request_id"], "01JTESTSUM")
        self.assertEqual(data["skill"], "summarize")
        self.assertEqual(data["agent_id"], "summarize")
        self.assertIn("result", data)
        self.assertIn("output", data)
        self.assertIn("usage", data)
        self.assertIn("versions", data)

    def test_unknown_skill_404(self):
        res = self.client.post("/api/agents/not.a.skill/run", json={"request_id": "01J404"})
        self.assertEqual(res.status_code, 404)
        data = res.get_json()
        self.assertEqual(data["error"]["code"], "agent_not_found")

    def test_asr_skill_alias_run(self):
        res = self.client.post(
            "/api/agents/asr.transcribe/run",
            json={"input": "", "options": {"mode": "compare"}},
        )
        self.assertIn(res.status_code, (200, 400))
        data = res.get_json()
        self.assertEqual(data["skill"], "asr.transcribe")
        self.assertEqual(data["agent_id"], "speech-to-text")
        self.assertIn("result", data)

    def test_asr_skill_alias_get(self):
        by_id = self.client.get("/api/agents/speech-to-text")
        by_skill = self.client.get("/api/agents/asr.transcribe")
        self.assertEqual(by_id.status_code, 200)
        self.assertEqual(by_skill.status_code, 200)
        self.assertEqual(by_id.get_json()["id"], "speech-to-text")
        self.assertEqual(by_skill.get_json()["id"], "speech-to-text")
        self.assertEqual(by_skill.get_json()["skill"], "asr.transcribe")
        self.assertTrue(by_skill.get_json()["examples"])

    def test_idempotent_same_request_id(self):
        body = {"input": "hello", "options": {}, "request_id": "01JIDEMPOTENT1"}
        first = self.client.post("/api/agents/summarize/run", json=body)
        second = self.client.post("/api/agents/summarize/run", json=body)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.get_json()["usage"]["latency_ms"], second.get_json()["usage"]["latency_ms"])
        self.assertEqual(first.get_json()["result"], second.get_json()["result"])


if __name__ == "__main__":
    unittest.main()
