#!/usr/bin/env python3
"""运行规划闭环验证并输出报告。

用法:
  python agents/_lib/planning/tests/run_closed_loop.py
  python agents/_lib/planning/tests/run_closed_loop.py --narrative
  python agents/_lib/planning/tests/run_closed_loop.py --case clear_career_goal
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_AGENTS_ROOT = _TESTS_DIR.parents[2]

sys.path.insert(0, str(_AGENTS_ROOT))

from _lib.planning.tests.helpers import (  # noqa: E402
    list_fixtures,
    load_fixture,
    run_all_fixtures,
    run_full_chain,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="规划闭环验证")
    parser.add_argument("--case", help="仅运行指定 fixture（不含 .json 后缀）")
    parser.add_argument("--narrative", action="store_true", help="包含 life-script-author 启动步骤")
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    args = parser.parse_args()

    if args.case:
        fixture = load_fixture(args.case)
        results = [run_full_chain(fixture, include_narrative=args.narrative)]
    else:
        results = run_all_fixtures(include_narrative=args.narrative)

    passed = sum(1 for r in results if r["passed"])
    total = len(results)

    if args.json:
        print(json.dumps({"passed": passed, "total": total, "results": results}, ensure_ascii=False, indent=2))
    else:
        print(f"规划闭环验证: {passed}/{total} 通过\n")
        for r in results:
            status = "PASS" if r["passed"] else "FAIL"
            print(f"  [{status}] {r['case_id']}: {r.get('description', '')}")
            if r["issues"]:
                for issue in r["issues"]:
                    print(f"         - {issue}")
        print()
        for r in results:
            if r.get("steps"):
                print(f"--- {r['case_id']} steps ---")
                for step, meta in r["steps"].items():
                    blocked = meta.get("blocked")
                    extra = f" blocked={blocked}" if blocked is not None else ""
                    print(f"  {step}:{extra} {meta.get('output_preview', '')[:80]}")
                print()

    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
