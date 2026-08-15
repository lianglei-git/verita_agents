"""sentence.analyze：按 api_version 原样交出 analysis，禁止 activity_id。"""

from __future__ import annotations

import sys
import unittest

from backend.agents import get_agent, run_agent
from backend.agents.loader import AGENTS_ROOT

if str(AGENTS_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENTS_ROOT))


class SentenceAnalyzeMapTest(unittest.TestCase):
    def test_versioned_output_drops_activity_id(self):
        spec = get_agent("sentence.analyze")
        self.assertIsNotNone(spec)
        to_out = spec["module"].to_versioned_ls_output
        raw = {
            "input": "I am.",
            "api_version": "v1",
            "analysis": {
                "sentence": "I am.",
                "translation": "我是。",
                "sentence_type": "简单句",
                "tree": "[S]",
                "trunk": {"subject": {"text": "I"}, "predicate": {"text": "am"}},
                "meta": {"activity_id": "01JLEAK"},
            },
            "meta": {
                "agent": "en-syntax-tagger",
                "package_version": "3.0.0",
                "activity_id": "01JLEAK",
            },
        }
        out = to_out(
            raw,
            api_version="v1",
            learning_language="en",
            support_language="zh-CN",
            profile="academic",
            user_level="B1",
            goal="商务口语",
        )
        self.assertEqual(out["api_version"], "v1")
        self.assertEqual(out["target_lang"], "en")
        self.assertEqual(out["explain_lang"], "zh-CN")
        self.assertEqual(out["analysis"]["tree"], "[S]")
        self.assertNotIn("activity_id", out["analysis"].get("meta") or {})
        self.assertNotIn("activity_id", out["meta"])
        self.assertEqual(out["meta"]["user_level"], "B1")

    def test_empty_run_has_ls_output(self):
        result = run_agent(
            "sentence.analyze",
            "",
            learning_language="en",
            support_language="zh-CN",
            profile="academic",
        )
        self.assertEqual(result.get("error"), "empty_input")
        self.assertIsInstance(result.get("output"), dict)
        self.assertEqual(result["output"]["api_version"], "v1")
        self.assertEqual(result["output"]["target_lang"], "en")
        self.assertNotIn("activity_id", result["output"]["meta"])

    def test_v2_output_keeps_teaching_shape(self):
        result = run_agent(
            "sentence.analyze",
            "",
            api_version="v2",
            learning_language="en",
            support_language="zh-CN",
            profile="teaching",
        )
        self.assertEqual(result["output"]["api_version"], "v2")
        self.assertIsInstance(result["output"]["analysis"], dict)

    def test_bcp47_labels(self):
        spec = get_agent("en-syntax-tagger")
        to_bcp47 = spec["module"].to_bcp47
        self.assertEqual(to_bcp47("英语"), "en")
        self.assertEqual(to_bcp47("中文"), "zh-CN")
        self.assertEqual(to_bcp47("zh-CN"), "zh-CN")


if __name__ == "__main__":
    unittest.main()
