"""P3–P5：translate / sentence.extract / vocabulary.generate。"""

from __future__ import annotations

import unittest

from backend.agents import get_agent, list_agents, run_agent


class SkillRegistryTest(unittest.TestCase):
    def test_aliases(self):
        self.assertIs(get_agent("translate"), get_agent("translate"))
        self.assertEqual(get_agent("sentence-extract")["skill"], "sentence.extract")
        self.assertIs(get_agent("sentence.extract"), get_agent("sentence-extract"))
        self.assertIs(get_agent("vocabulary.generate"), get_agent("vocabulary-generate"))
        ids = [row["id"] for row in list_agents()]
        self.assertEqual(ids.count("translate"), 1)
        self.assertNotIn("sentence.extract", ids)


class TranslateTest(unittest.TestCase):
    def test_align_keeps_id_and_timestamps(self):
        spec = get_agent("translate")
        align = spec["module"].align_translations
        source = [
            {"id": "c1", "text": "I am.", "start_ms": 10, "end_ms": 20},
            {"id": "c2", "text": "Hello.", "start_ms": 21, "end_ms": 40},
        ]
        out = align(source, [{"id": "c2", "text": "你好。"}, {"id": "c1", "text": "我是。"}])
        self.assertEqual([row["id"] for row in out], ["c1", "c2"])
        self.assertEqual(out[0]["text"], "我是。")
        self.assertEqual(out[0]["start_ms"], 10)
        self.assertEqual(out[1]["end_ms"], 40)

    def test_run_preserves_ids_without_llm(self):
        result = run_agent(
            "translate",
            "",
            source_lang="en",
            target_lang="zh-CN",
            items=[
                {"id": "c1", "text": "I am.", "start_ms": 21805, "end_ms": 23000},
                {"id": "c9", "text": "Go.", "start_ms": 1, "end_ms": 2},
            ],
        )
        items = result["output"]["items"]
        self.assertEqual([row["id"] for row in items], ["c1", "c9"])
        self.assertEqual(items[0]["start_ms"], 21805)
        self.assertEqual(items[1]["end_ms"], 2)


class SentenceExtractTest(unittest.TestCase):
    def test_text_path_null_timestamps(self):
        spec = get_agent("sentence.extract")
        sentences = spec["module"].extract_from_text("I am. We're in a competitive industry.")
        self.assertGreaterEqual(len(sentences), 2)
        self.assertTrue(all(s["start_ms"] is None and s["end_ms"] is None for s in sentences))
        self.assertTrue(all(s["cue_ids"] == [] for s in sentences))

    def test_cues_merge_and_ids(self):
        spec = get_agent("sentence.extract")
        sentences = spec["module"].extract_from_cues(
            [
                {"id": "c1", "text": "I am", "start_ms": 100, "end_ms": 200},
                {"id": "c2", "text": "ready.", "start_ms": 210, "end_ms": 400},
            ]
        )
        self.assertEqual(len(sentences), 1)
        self.assertEqual(sentences[0]["cue_ids"], ["c1", "c2"])
        self.assertEqual(sentences[0]["start_ms"], 100)
        self.assertEqual(sentences[0]["end_ms"], 400)
        self.assertIn("ready", sentences[0]["text"])

    def test_run_text_and_cues_paths(self):
        text_out = run_agent("sentence.extract", "Hello. World.", learning_language="en")
        self.assertTrue(text_out["output"]["sentences"])
        cue_out = run_agent(
            "sentence.extract",
            "",
            learning_language="en",
            cues=[{"id": "c1", "text": "Hello.", "start_ms": 0, "end_ms": 10}],
        )
        self.assertTrue(cue_out["output"]["sentences"])


class VocabularyTest(unittest.TestCase):
    def test_no_ls_ids_and_bilingual_gloss(self):
        spec = get_agent("vocabulary.generate")
        card = spec["module"].normalize_card(
            {
                "lemma": "emotive",
                "object_id": "obj_1",
                "asset_id": "ast_1",
                "senses": [
                    {
                        "sense_id": "s1",
                        "object_id": "nope",
                        "gloss": {"en": "arousing feeling"},
                        "example_texts": [{"lang": "en", "text": "an emotive issue", "object_id": "x"}],
                    }
                ],
            },
            lemma="emotive",
            learning="en",
            support="zh-CN",
            user_level="C1",
            context="an emotive issue",
        )
        blob = str(card)
        self.assertNotIn("object_id", blob)
        self.assertNotIn("asset_id", blob)
        self.assertIn("en", card["senses"][0]["gloss"])
        self.assertIn("zh-CN", card["senses"][0]["gloss"])

    def test_run_empty_lemma(self):
        result = run_agent("vocabulary.generate", "")
        self.assertEqual(result["error"], "empty_input")


if __name__ == "__main__":
    unittest.main()
