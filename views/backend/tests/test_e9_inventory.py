"""P7：五个 E9 skill 可发现、有文档、没有 pipeline 入口。"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from backend.app import create_app

E9 = (
    "asr.transcribe",
    "translate",
    "sentence.extract",
    "sentence.analyze",
    "vocabulary.generate",
)


class E9InventoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()

    def setUp(self):
        self._auth = patch.dict(os.environ, {"AGENT_AUTH_DISABLED": "1"})
        self._auth.start()

    def tearDown(self):
        self._auth.stop()

    def test_five_skills_have_docs(self):
        for skill in E9:
            res = self.client.get(f"/api/agents/{skill}")
            self.assertEqual(res.status_code, 200, skill)
            data = res.get_json()
            self.assertEqual(data["skill"], skill)
            self.assertEqual(data["endpoint"], f"/api/agents/{skill}/run")
            self.assertTrue(data.get("examples"), f"{skill} missing examples")
            codes = {row["code"] for row in data.get("errors") or []}
            self.assertIn("unauthorized", codes)

    def test_no_pipeline_route(self):
        for path in (
            "/api/agents/pipeline/run",
            "/api/agents/media.process/run",
            "/api/pipeline/run",
        ):
            res = self.client.post(path, json={})
            self.assertEqual(res.status_code, 404, path)
