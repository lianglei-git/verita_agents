"""P0：id 与 skill 打到同一个 agent。"""

from __future__ import annotations

import unittest

from backend.agents import get_agent, list_agents


class SkillAliasTest(unittest.TestCase):
    def test_asr_alias(self):
        by_id = get_agent("speech-to-text")
        by_skill = get_agent("asr.transcribe")
        self.assertIsNotNone(by_id)
        self.assertIs(by_id, by_skill)
        self.assertEqual(by_id["skill"], "asr.transcribe")

    def test_sentence_analyze_alias(self):
        by_id = get_agent("en-syntax-tagger")
        by_skill = get_agent("sentence.analyze")
        self.assertIsNotNone(by_id)
        self.assertIs(by_id, by_skill)

    def test_list_does_not_duplicate(self):
        ids = [row["id"] for row in list_agents()]
        self.assertEqual(ids.count("speech-to-text"), 1)
        self.assertNotIn("asr.transcribe", ids)
        asr = next(row for row in list_agents() if row["id"] == "speech-to-text")
        self.assertEqual(asr["skill"], "asr.transcribe")
        self.assertEqual(asr["endpoint"], "/api/agents/asr.transcribe/run")


if __name__ == "__main__":
    unittest.main()
