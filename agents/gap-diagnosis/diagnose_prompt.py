"""差距诊断提示词。"""

from __future__ import annotations

import json
from typing import Any


def build_user_prompt(profile: dict[str, Any]) -> str:
    anchors = profile.get("anchors") or {}
    goals = profile.get("goals") or []
    goal_text = anchors.get("goal") or (goals[0].get("description") if goals else "")
    current = anchors.get("current") or ""

    return f"""请基于以下 PlanningProfile 输出结构化差距诊断（GapDiagnosis JSON）。

## 用户锚点
- 目标：{goal_text or "（未明确）"}
- 现状：{current or "（未明确）"}

## 完整画像
```json
{json.dumps(profile, ensure_ascii=False, indent=2)}
```

## 输出要求
1. 识别 3–6 项从现状到目标的关键差距（gaps[]）。
2. 每项差距须含：title、category、evidence（attributed_claim 数组）、baseline、target_threshold、
   verifiable_metrics、priority、closure_options。
3. evidence 须关联用户事实（kind=fact）或显式假设（kind=assumption），不要伪造用户未述事实。
4. 无法判断的领域标为 uncertainty，高影响低置信度假设标 requires_confirmation。
5. 填写 summary（一段话概括差距格局）与 diagnosis_id（可用简短 slug）。
6. profile_id 与输入画像一致（若无则生成 gap_diag_<slug>）。

只返回 JSON 对象，符合 gap_diagnosis schema。"""
