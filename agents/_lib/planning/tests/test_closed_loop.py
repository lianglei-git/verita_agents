"""Phase 4 闭环验证 — 五类代表性输入 + 安全边界。"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_AGENTS_ROOT = _TESTS_DIR.parents[2]

for path in (_AGENTS_ROOT,):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from _lib.planning import (  # noqa: E402
    audit_attributed_claim,
    scan_text_violations,
    validate_contract,
)
from _lib.planning.tests.helpers import (  # noqa: E402
    assert_claims_labeled,
    assert_no_safety_violations,
    list_fixtures,
    load_fixture,
    run_full_chain,
    run_gap,
)


class TestSafetyBoundaries(unittest.TestCase):
    def test_scan_catches_deterministic_prophecy(self) -> None:
        violations = scan_text_violations("你一定会成功，这是命中注定的事情")
        codes = {v["code"] for v in violations}
        self.assertIn("deterministic_prediction", codes)

    def test_scan_catches_diagnosis(self) -> None:
        violations = scan_text_violations("你患有抑郁症，应该去看心理医生")
        codes = {v["code"] for v in violations}
        self.assertIn("psychological_diagnosis", codes)

    def test_fact_cannot_use_model_source(self) -> None:
        issues = audit_attributed_claim({
            "text": "用户是 INTJ",
            "kind": "fact",
            "source": "model_assumed",
            "confidence": 0.9,
        })
        self.assertTrue(any("fact must not" in i for i in issues))

    def test_validate_contract_gap_requires_gaps(self) -> None:
        issues = validate_contract({"gaps": []}, "gap_diagnosis")
        self.assertTrue(any("gaps must not be empty" in i for i in issues))

    def test_validate_contract_roadmap_requires_milestones(self) -> None:
        issues = validate_contract({
            "phases": [{
                "id": "p1",
                "title": "阶段一",
                "goal": "目标",
                "milestones": [],
                "if_not_met": {"adjustments": []},
            }],
        }, "adaptive_roadmap")
        self.assertTrue(len(issues) >= 2)


class TestGapBlocking(unittest.TestCase):
    def test_insufficient_info_blocks_gap(self) -> None:
        fixture = load_fixture("insufficient_info.json")
        result = run_gap({
            "heuristic_only": True,
            "profile": fixture["profile"],
        })
        self.assertTrue(result.get("blocked"))
        self.assertIsNone(result.get("gap_diagnosis"))

    def test_insufficient_info_force_proceeds(self) -> None:
        fixture = load_fixture("insufficient_info.json")
        result = run_gap({
            "heuristic_only": True,
            "force": True,
            "profile": fixture["profile"],
        })
        self.assertFalse(result.get("blocked"))
        self.assertIsNotNone(result.get("gap_diagnosis"))


class TestClosedLoopFixtures(unittest.TestCase):
    FIXTURE_NAMES = [
        "clear_career_goal.json",
        "fuzzy_life_exploration.json",
        "contradictory_constraints.json",
        "refuse_to_supplement.json",
    ]

    def test_all_fixtures_present(self) -> None:
        names = {p.name for p in list_fixtures()}
        for name in self.FIXTURE_NAMES + ["insufficient_info.json"]:
            self.assertIn(name, names, f"missing fixture {name}")

    def test_full_chain_fixtures(self) -> None:
        for name in self.FIXTURE_NAMES:
            with self.subTest(fixture=name):
                fixture = load_fixture(name)
                report = run_full_chain(fixture)
                if not report["passed"]:
                    self.fail(
                        f"{name} failed:\n"
                        + "\n".join(report["issues"])
                    )

    def test_insufficient_info_chain_stops_at_gap(self) -> None:
        fixture = load_fixture("insufficient_info.json")
        report = run_full_chain(fixture)
        self.assertTrue(report["passed"], msg="\n".join(report["issues"]))
        self.assertIn("gap", report["steps"])
        self.assertTrue(report["steps"]["gap"].get("blocked"))
        self.assertNotIn("scenario", report["steps"])


class TestCLIFilePath(unittest.TestCase):
    def test_gap_cli_reads_fixture_path(self) -> None:
        from _lib.cli import resolve_cli_input

        fixture = _TESTS_DIR / "fixtures" / "clear_career_goal.json"
        raw = resolve_cli_input([str(fixture), str(fixture)])
        data = json.loads(raw)
        self.assertEqual(data["case_id"], "clear_career_goal")


if __name__ == "__main__":
    unittest.main(verbosity=2)
