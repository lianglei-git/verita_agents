"""情景推演提示词。"""

from __future__ import annotations

import json
from typing import Any

from _lib.planning.types import SCENARIO_ARCHETYPES


def build_user_prompt(profile: dict[str, Any], gap_diagnosis: dict[str, Any] | None) -> str:
    gaps_block = ""
    if gap_diagnosis and gap_diagnosis.get("gaps"):
        gaps_block = f"""
## 差距诊断
```json
{json.dumps(gap_diagnosis, ensure_ascii=False, indent=2)}
```
"""

    archetypes = "、".join(SCENARIO_ARCHETYPES)
    return f"""请基于 PlanningProfile 与差距诊断，生成 3 个互斥、可比较的人生/职业情景（ScenarioSet JSON）。

## 画像
```json
{json.dumps(profile, ensure_ascii=False, indent=2)}
```
{gaps_block}
## 输出要求
1. 必须恰好 3 个情景，archetype 分别为：{archetypes}（各一个，互斥路径）。
2. 每个情景含：title、tagline、premises（attributed_claim）、key_decisions、staged_outcomes、
   opportunity_costs、failure_modes、early_warning_signals、reversible_actions、confidence_notes。
3. premises 须区分用户事实与显式假设，禁止确定性命运预言。
4. 填写 set_id、profile_id、gap_diagnosis_id（若有）、comparison_axes、disclaimer。
5. 不要填写 selected_scenario_id（由用户后续选择）。

只返回 JSON 对象，符合 scenario_set schema。"""
