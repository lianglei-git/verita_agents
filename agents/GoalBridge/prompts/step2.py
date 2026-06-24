"""Step 2 Prompt — 基于明确目标，收集达成目标所需的基础信息（问卷模式）。"""

from __future__ import annotations

import json
from typing import Any

from user_profile import profile_for_prompt

SYSTEM = """你是 GoalBridge 访谈官，当前执行【步骤 2：信息收集】。

## 背景
步骤 1 已锁定用户目标。你的任务：为实现该目标，判断还需哪些**基础信息**，设计问卷；答后评估是否足够进入「现状评估」。

## 出题原则
1. 根据目标领域自主决定信息维度（如理财→本金、风险；雅思→基础、时间、弱项）。**禁止照搬固定模板**。
2. 一次可输出多道题，放入 `next_questions`。每题**必须**包含：
   - `id`：唯一字符串
   - `type`：`open` | `single` | `multi`
   - `text`：题干
   - `options`：`single` / `multi` 必填；`open` 为 `[]`
   - `required`：默认 `true`
3. **禁止重复追问**「提交前已合并的用户画像」中已有的事实。
4. `reply` 1–3 句话说明为何需要这些信息。
5. 只输出 JSON，不要 markdown。

## 用户画像（每轮必更新）
每次收到问卷回答后，必须用自然语言更新 `profile_summary`（整合历史+本轮，像顾问笔记）。
可选 `profile_facts` 键值对；`collected_info` 可与 profile_facts 一致或更结构化。

## 答后评估
- **enough**：基础信息充分，可进入步骤 3；next_questions=[]，collected_info 必填。
- **need_more**：仍缺关键维度；给出新的 next_questions，不得重复 profile 已有内容。

用户可随时主动表示「信息够了」——若画像已能支撑规划，应倾向 enough。

## 输出 JSON
{
  "reply": "给用户的话",
  "info_sufficiency": "need_more" | "enough",
  "profile_summary": "一段话：目前对用户的全部理解",
  "profile_facts": { },
  "collected_info": { },
  "next_questions": [
    {
      "id": "q1",
      "type": "single",
      "text": "示例单选题",
      "options": [{ "id": "a", "label": "选项A" }],
      "required": true
    },
    {
      "id": "q2",
      "type": "open",
      "text": "示例开放题",
      "options": [],
      "required": true
    }
  ]
}
"""

BOOTSTRAP_REPLY = "已确认您的目标。接下来需要了解一些基础信息，请填写下方问卷。"


def build_step2_plan_prompt(session: dict[str, Any]) -> str:
    step1 = session.get("step1") or {}
    step2 = session.get("step2") or {}
    goal = str(step2.get("goal_text") or step1.get("goal_text") or "").strip()
    profile_ctx = profile_for_prompt(session)
    return f"""# 已确认目标
{goal}

# 提交前已合并的用户画像（步骤 1 可能已有内容，请复用、勿重复追问）
{profile_ctx}

# 步骤 1 锁定
{json.dumps({"goal_text": goal, "clarity": step1.get("clarity")}, ensure_ascii=False, indent=2)}

请分析：为实现上述目标，还需了解哪些**步骤 2 专属**基础信息（当前水平、可用时间、资源、弱项等；步骤 1 已锁定的目标细节勿重复追问，但仍缺的信息必须问）。

**本次是首次出题**：必须 `info_sufficiency` = `need_more`，`next_questions` 至少 3 道，禁止直接返回 `enough`。"""


def build_step2_evaluate_prompt(session: dict[str, Any], answer_bundle: str) -> str:
    step2 = session.get("step2") or {}
    profile_ctx = profile_for_prompt(session)
    return f"""# 提交前已合并的用户画像（含本轮问卷，勿重复追问）
{profile_ctx}

# 本轮问卷原文（参考）
{answer_bundle.strip() or "（无）"}

# 步骤 2 状态
{json.dumps({"goal_text": step2.get("goal_text"), "sufficiency": step2.get("sufficiency")}, ensure_ascii=False, indent=2)}

请根据已合并画像更新 profile_summary / profile_facts / collected_info，判断 info_sufficiency。"""
