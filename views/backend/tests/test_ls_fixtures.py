"""LS E4 fixtures：清单齐全、信封完整、关键边界在。"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from backend.config import SHARED_DIR

ROOT = Path(SHARED_DIR) / "ls-fixtures"
FORBIDDEN = ("object_id", "asset_id", "activity_id")


def _load(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def _walk_keys(obj, found: set[str]) -> None:
    if isinstance(obj, dict):
        found.update(obj)
        for v in obj.values():
            _walk_keys(v, found)
    elif isinstance(obj, list):
        for item in obj:
            _walk_keys(item, found)


class LsFixturesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = _load("index.json")
        cls.rows = cls.index["fixtures"]

    def test_index_lists_existing_files(self):
        self.assertGreaterEqual(len(self.rows), 15)
        for row in self.rows:
            path = ROOT / row["file"]
            self.assertTrue(path.is_file(), row["file"])

    def test_five_skills_have_200(self):
        by_skill = {}
        for row in self.rows:
            if row.get("status") == 200:
                by_skill.setdefault(row["skill"], []).append(row["file"])
        for skill in (
            "asr.transcribe",
            "translate",
            "sentence.extract",
            "sentence.analyze",
            "vocabulary.generate",
        ):
            self.assertTrue(by_skill.get(skill), skill)

    def test_analyze_has_three_versions(self):
        versions = set()
        for name in ("200-v1.json", "200-v2.json", "200-v3.json"):
            data = _load(f"sentence.analyze/{name}")
            out = data["response"]["output"]
            versions.add(out["api_version"])
            self.assertIn("analysis", out)
            self.assertNotIn("activity_id", out.get("meta") or {})
        self.assertEqual(versions, {"v1", "v2", "v3"})

    def test_asr_cues_have_no_id(self):
        data = _load("asr.transcribe/200-en-cues-no-id.json")
        cues = data["response"]["output"]["cues"]
        self.assertTrue(cues)
        for cue in cues:
            self.assertNotIn("id", cue)
            self.assertIn("text", cue)
        self.assertIsNone(data["response"]["usage"]["cost_micros"])

    def test_extract_text_has_empty_cue_ids(self):
        data = _load("sentence.extract/200-text-empty-cue-ids.json")
        sentences = data["response"]["output"]["sentences"]
        self.assertTrue(sentences)
        for row in sentences:
            self.assertEqual(row["cue_ids"], [])
            self.assertIsNone(row["start_ms"])

    def test_success_envelopes(self):
        for row in self.rows:
            if row.get("status") != 200:
                continue
            data = _load(row["file"])
            body = data["response"]
            for key in ("request_id", "skill", "output", "usage", "versions"):
                self.assertIn(key, body, row["file"])
            self.assertIsNone(body["usage"].get("cost_micros"), row["file"])
            keys: set[str] = set()
            _walk_keys(body["output"], keys)
            for banned in FORBIDDEN:
                self.assertNotIn(banned, keys, row["file"])

    def test_error_fixtures(self):
        unauth = _load("_errors/401-unauthorized.json")
        self.assertEqual(unauth["http"]["status"], 401)
        self.assertEqual(unauth["response"]["error"]["code"], "unauthorized")
        missing = _load("_errors/404-unknown-skill.json")
        self.assertEqual(missing["http"]["status"], 404)


if __name__ == "__main__":
    unittest.main()
