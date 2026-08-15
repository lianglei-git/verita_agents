"""P6：内部 token 中间件。"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from backend.app import create_app
from backend.auth import is_protected_agent_call


class ProtectedPathTest(unittest.TestCase):
    def test_only_run_and_stream(self):
        self.assertTrue(is_protected_agent_call("/api/agents/translate/run", "POST"))
        self.assertTrue(is_protected_agent_call("/api/agents/asr.transcribe/stream", "POST"))
        self.assertFalse(is_protected_agent_call("/api/agents/translate/run", "GET"))
        self.assertFalse(is_protected_agent_call("/api/agents/translate", "GET"))
        self.assertFalse(is_protected_agent_call("/api/runs/x/execute/translate", "POST"))


class InternalTokenHttpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()

    def test_no_token_configured_allows_run(self):
        env = {
            "AGENT_AUTH_DISABLED": "",
            "INTERNAL_TOKEN": "",
            "AGENT_TOKEN": "",
        }
        with patch.dict(os.environ, env):
            res = self.client.post(
                "/api/agents/summarize/run",
                json={"input": "hello", "options": {}},
            )
        self.assertEqual(res.status_code, 200)

    def test_token_required(self):
        with patch.dict(os.environ, {"INTERNAL_TOKEN": "secret-ls", "AGENT_AUTH_DISABLED": ""}):
            missing = self.client.post(
                "/api/agents/summarize/run",
                json={"input": "hello", "options": {}},
            )
            self.assertEqual(missing.status_code, 401)
            self.assertEqual(missing.get_json()["error"]["code"], "unauthorized")

            wrong = self.client.post(
                "/api/agents/summarize/run",
                json={"input": "hello", "options": {}},
                headers={"X-Internal-Token": "nope"},
            )
            self.assertEqual(wrong.status_code, 401)

            ok = self.client.post(
                "/api/agents/summarize/run",
                json={"input": "hello", "options": {}},
                headers={"X-Internal-Token": "secret-ls"},
            )
            self.assertEqual(ok.status_code, 200)
            self.assertEqual(ok.get_json()["skill"], "summarize")

    def test_auth_disabled_skips(self):
        with patch.dict(os.environ, {"INTERNAL_TOKEN": "secret-ls", "AGENT_AUTH_DISABLED": "1"}):
            res = self.client.post(
                "/api/agents/summarize/run",
                json={"input": "hello", "options": {}},
            )
        self.assertEqual(res.status_code, 200)

    def test_get_agent_not_protected(self):
        with patch.dict(os.environ, {"INTERNAL_TOKEN": "secret-ls", "AGENT_AUTH_DISABLED": ""}):
            res = self.client.get("/api/agents/translate")
        self.assertEqual(res.status_code, 200)
