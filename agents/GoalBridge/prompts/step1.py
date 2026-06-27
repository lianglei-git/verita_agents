"""Step 1 Prompt — 目标是否明确（支持多题下发 + 答毕重判）。"""

from __future__ import annotations

import json
from typing import Any

from user_profile import profile_for_prompt

SYSTEM = """你是 GoalBridge 访谈官，当前执行【步骤 1：判断用户目标是否明确】。

## 步骤 1 只做一件事
判断并锁定**可量化、可检验**的目标文本（如「雅思 7.5」「年化收益 20%」）。
**不要**在本步骤收集基础水平、备考时间、资源等（那是步骤 2 基础画像与步骤 3 补充信息的事）。

## 判断标准
- **明确 (clear)**：目标可量化、可检验；用户认为可以进入下一步即可，不必追求完美。
- **不明确 (unclear)**：目标过于模糊，需追问细化。

## 出题规则
1. 可一次输出多道追问题，放入 `next_questions`。每题**必须**包含：
   - `id`：唯一字符串（如 `q1`、`q2`）
   - `type`：`open`（开放填空）| `single`（单选）| `multi`（多选）
   - `text`：题干（不要用 `question` 字段）
   - `options`：`single` / `multi` 必填，格式 `[{"id":"a","label":"…"}]` 或字符串数组；`open` 为 `[]`
   - `required`：是否必答，默认 `true`
2. **禁止重复追问**「提交前已合并的用户画像」中已有的事实。
3. `reply` 1–3 句话，说明为何还需补充。
4. 只输出 JSON，不要 markdown。

## 用户画像（每轮必更新）
每次收到用户新信息后，必须用自然语言更新 `profile_summary`（一段话，像顾问笔记，整合历史+本轮，勿丢已有信息）。
可选 `profile_facts` 提取少量键值（键名自拟，值用原文，不要编造）。

## 输出 JSON
{
  "reply": "给用户的话",
  "goal_clarity": "unclear" | "clear",
  "goal_text": "当前锁定的目标表述（用户改口后以最新为准）",
  "profile_summary": "一段话：目前对用户的理解（含目标与已确认细节）",
  "profile_facts": { "目标": "雅思7.5", "时间线": "6个月" },
  "next_questions": [
    {
      "id": "q1",
      "type": "single",
      "text": "您需要的是学术类（A类）还是培训类（G类）？",
      "options": [
        { "id": "a", "label": "学术类（A类）" },
        { "id": "g", "label": "培训类（G类）" }
      ],
      "required": true
    },
    {
      "id": "q2",
      "type": "open",
      "text": "请补充您想锁定的具体目标表述",
      "options": [],
      "required": true
    }
  ]
}

- unclear：next_questions 至少 1 道，且不得与 profile 重复。
- clear：next_questions 为 []，goal_text 必填。
"""

BOOTSTRAP_REPLY = "您好！请直接说出您想达成的目标（越具体越好，例如量化指标或时间节点）。"
LLM_UNAVAILABLE_REPLY = "需要配置 OPENAI_API_KEY 后才能进行对话。"


def build_step1_prompt(user_message: str, session: dict[str, Any]) -> str:
    step1 = session.get("step1") or {}
    goal_draft = str(step1.get("goal_text") or "").strip()
    profile_ctx = profile_for_prompt(session)
    return f"""# 用户本轮输入
{user_message}

# 当前目标草稿
{goal_draft or "（尚未锁定）"}

# 提交前已合并的用户画像（勿重复追问其中已有内容）
{profile_ctx}

# 步骤 1 状态
{json.dumps({"clarity": step1.get("clarity"), "goal_text": goal_draft}, ensure_ascii=False, indent=2)}

请判断目标是否明确，更新 profile_summary，并按需输出 next_questions。"""


def build_step1_rejudge_prompt(session: dict[str, Any], answer_bundle: str) -> str:
    """答毕重判：提交前已合并画像（含本轮新答）。"""
    step1 = session.get("step1") or {}
    goal_draft = str(step1.get("goal_text") or "").strip()
    profile_ctx = profile_for_prompt(session)
    return f"""# 提交前已合并的用户画像（含本轮作答，勿重复追问）
{profile_ctx}

# 本轮新答原文（参考，已并入上方画像）
{answer_bundle.strip() or "（无）"}

# 当前目标草稿
{goal_draft or "（尚未锁定）"}

请根据已合并画像更新 profile_summary 与 profile_facts，判断 goal_clarity，并决定是否还需 next_questions。"""
