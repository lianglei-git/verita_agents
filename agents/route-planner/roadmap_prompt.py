"""自适应路线图提示词。"""

from __future__ import annotations

import json
from typing import Any


def build_user_prompt(
    profile: dict[str, Any],
    gap_diagnosis: dict[str, Any] | None,
    scenario: dict[str, Any],
    scenario_set: dict[str, Any] | None,
) -> str:
    gaps_block = ""
    if gap_diagnosis:
        gaps_block = f"""
## 差距诊断
```json
{json.dumps(gap_diagnosis, ensure_ascii=False, indent=2)}
```
"""
    selection = ""
    if scenario_set and scenario_set.get("selection_rationale"):
        selection = f"\n用户选线理由：{scenario_set['selection_rationale']}"

    return f"""请基于用户确认的情景主线，生成可执行的 AdaptiveRoadmap JSON。

## 画像
```json
{json.dumps(profile, ensure_ascii=False, indent=2)}
```
{gaps_block}
## 用户确认的情景主线
```json
{json.dumps(scenario, ensure_ascii=False, indent=2)}
```
{selection}

## 输出要求
1. phases[] 每阶段含：title、goal、time_window、actions、deliverables、success_thresholds、
   resource_costs、milestones（至少 1 个可验证）、risk_signals、if_not_met（含 adjustments）、
   review_checkpoint。
2. 路线图须直接回应差距项与情景中的 key_decisions / staged_outcomes，禁止关键词模板套话。
3. assumptions[] 列出关键假设（attributed_claim），高影响低置信度标 requires_confirmation。
4. 填写 roadmap_id、profile_id、scenario_id、title、summary、version=1。

只返回 JSON 对象，符合 adaptive_roadmap schema。"""
