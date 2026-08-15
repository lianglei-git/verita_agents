"""P2：sentence.analyze remap，禁止 activity_id。"""

from __future__ import annotations

import sys
import unittest

from backend.agents import get_agent, run_agent
from backend.agents.loader import AGENTS_ROOT

if str(AGENTS_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENTS_ROOT))


class SentenceAnalyzeMapTest(unittest.TestCase):
    def test_remap_drops_activity_id(self):
        spec = get_agent("sentence.analyze")
        self.assertIsNotNone(spec)
        to_out = spec["module"].to_sentence_analyze_output
        raw = {
            "input": "I am.",
            "api_version": "v1",
            "analysis": {
                "sentence": "I am.",
                "translation": "我是。",
                "sentence_type": "简单句",
                "tree": "[S]",
                "trunk": {"subject": {"text": "I"}, "predicate": {"text": "am"}},
                "constituent_table": [{"role": "S", "text": "I"}],
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
            learning_language="en",
            support_language="zh-CN",
            profile="academic",
            user_level="B1",
            goal="商务口语",
        )
        self.assertEqual(out["target_lang"], "en")
        self.assertEqual(out["explain_lang"], "zh-CN")
        self.assertEqual(out["tree"], "[S]")
        self.assertEqual(out["trunk"]["subject"]["text"], "I")
        self.assertIn("en", out["i18n"])
        self.assertIn("zh-CN", out["i18n"])
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
        self.assertEqual(result["output"]["target_lang"], "en")
        self.assertNotIn("activity_id", result["output"]["meta"])

    def test_bcp47_labels(self):
        spec = get_agent("en-syntax-tagger")
        to_bcp47 = spec["module"].to_bcp47
        self.assertEqual(to_bcp47("英语"), "en")
        self.assertEqual(to_bcp47("中文"), "zh-CN")
        self.assertEqual(to_bcp47("zh-CN"), "zh-CN")


if __name__ == "__main__":
    unittest.main()
