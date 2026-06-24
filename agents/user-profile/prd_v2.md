# User-Profile 采集 Agent · PRD v2

> **版本**：v2.0（讨论定稿）  
> **归属**：`agents/user-profile`  
> **代号**：Digital Twin Engine · Journey-First Collection  
> **关联**：[知识库/用户需求.md](../../知识库/用户需求.md)

---

## 1. 背景与问题

v1 采用固定 baseline 字段 + 25 题预算 + 预设 path 缺口，导致：

- 问句像固定问卷（CEFR、婚姻、学历等与 journey 无关时仍追问）
- 用户广义回答未被充分吸收，同一语义反复问
- 「要采什么」在实现层写死，与「用户不是想学英语，是想用英语达成人生目标」的产品观不一致

v2 改为：**目标 + 现在 → 动态元信息 → 问题流 → AI 判断何时够**。

---

## 2. 产品目标

| 目标 | 说明 |
|------|------|
| 人生目标优先 | 先解析用户要通过英语**达成什么**，而非先问「英语水平」 |
| 动态必要信息 | 由 **目标 − 现在** 推出本次 journey 还需了解什么 |
| 推断优先 | 能从输入推出的字段不追问；整句回答尽量闭合多项元信息 |
| 无硬题数 | 不设 25 题上限；由 AI 判断信息是否**足够做规划** |
| 混合 schema | **Universal 固定**（字段名即语义）+ **Journey Meta 动态** |

**本期范围**：仅采集与放行逻辑；**不考虑下游** agent 如何消费 handoff。

---

## 3. 设计原则

1. **双锚点**：`goal`（目标）与 `current`（现在）是一等公民。
2. **元信息即需求**：每条 `journey_meta` 描述「为规划还需知道的一件事」，名称即义。
3. **逐步拼接**：`current` 允许多轮补充，直至 `current_clarity` 达标，不强制首轮一段话写全。
4. **路线草图非门禁**：推断足够后**直接进入 meta 采集**；`route_sketch` 可展示但不强制用户点「符合」才继续。
5. **少问、问准**：同 meta 最多追问 2 次，仍不清则 `waived` + 假设补全。
6. **自由回答**：用户始终用自然语言作答；后台结构化，前台无多栏表单。

---

## 4. 用户旅程（四阶段）

```
任意输入（故事 / 一句话 / 跳过）
        ↓
[A] 双锚点 — goal + current（可逐步拼接）
        ↓
[B] 元信息规划 — 由「目标 − 现在」生成 journey_meta + route_sketch
        ↓
[C] 问题流 — 按 priority 闭合 open 的 meta / 必要 universal
        ↓
[D] 放行 — AI 判定 sufficient / conditional
```

### 4.1 阶段 A：双锚点

**目的**：建立规划最小输入：`goal`、`current`，并补齐必要 universal。

**流程**：

1. 对用户输入做**全量推断**（故事、单题回答均适用）。
2. 评估 `goal_clarity`、`current_clarity`（`high | medium | low`）。
3. 决策：
   - `goal` 不清 → **只问目标**（单题开放）
   - `goal` 已够、`current` 不清 → **只问现在**（可指向缺失维度，仍为一题）
   - 二者均 ≥ `medium` → 进入阶段 B
4. `current` **逐步拼接**：每轮将新回答 merge 进 `current`（文本拼接或结构化片段合并），直到清晰度达标；不要求用户一次写全。

**不做**：一次性批量问年龄、婚姻、CEFR、学历等 universal 大全套。

### 4.2 阶段 B：元信息规划

**触发**：`goal_clarity` 与 `current_clarity` 均 ≥ `medium`。

**输入**：`goal`、`current`、已填 universal、`distance_summary`（系统内部对「目标 − 现在」距离的解读）。

**输出**：

- `journey_meta[]`：本次 journey 需闭合的信息项（见 §5.2）
- `route_sketch`：路线标题、摘要、阶段里程碑（供展示与内部规划，**非确认门禁**）

**规则**：

- 单 journey 元信息建议 **3～8 条**，带 `priority`：`blocking | important | optional`
- 已从 `goal` / `current` / 历史回答可推断的项 → `status: inferred`，填入 `value`，**不进入问题流**
- `goal` 或 `current` 发生重大变化 → `meta_plan_version++`，重算 `journey_meta`（保留仍有效的 inferred）

**产品决策（已定）**：

> **推断足够后直接进入 meta 采集**；不强制「路线符合预期吗？」确认步。`route_sketch` 可在 UI 展示为「当前推断方向」，用户可忽略或后续用自然语言纠正。

### 4.3 阶段 C：问题流

**选题顺序**：

```
blocking 且 status=open
  → important 且 open
    → optional 且 open（仅当 AI 认为仍有价值）
```

**交互**：

- 每次 **1 题**，对应一条 `journey_meta` 或必要 universal 缺口
- 问句由 LLM 生成（结合 `goal`、`current`、meta.`label` / `why`）；无 LLM 时模板兜底
- 用户 **自由文本** 回答；系统整句推断，可一次闭合多条 meta

**闭合与防重复**：

| 机制 | 说明 |
|------|------|
| `status != open` | 不再问该 meta |
| `asked_count >= 2` | 不再问；标记 `waived`，写入 `assumptions` |
| 语义等价 | 同簇 meta（如时间压力类）答一闭多 |
| `answered_log` | 记录问过什么，避免换皮重问 |

### 4.4 阶段 D：放行

**无题数硬上限**；用 `turn_count` 仅作统计与软护栏。

**AI 判定 `sufficient` 的充分条件**：

- `goal_clarity`、`current_clarity` ≥ `medium`
- 所有 `priority=blocking` 的 meta：`status ∈ { inferred, confirmed, waived }`
- `release.confidence` ≥ 阈值（建议 0.7）
- 无 goal 与 current 之间的明显矛盾

**放行类型**：

| status | 含义 |
|--------|------|
| `sufficient` | blocking 全闭合，important 大部分有值 |
| `conditional` | blocking 闭合，important 依赖 assumptions |

**软护栏**（非强制 25 题）：

- `turn_count > 15` 且 blocking 已闭 → 倾向 `conditional`
- `turn_count > 20` → 建议 `conditional`，记录 `unresolved_meta`

---

## 5. 数据架构（混合 Schema）

### 5.1 Universal（固定）

字段名自带含义；**默认不全部追问**，推断不到且对 journey 有影响时再问。

```yaml
universal:
  anchors:
    goal: string              # 想通过英语达成什么（人生/职业目标）
    current: string           # 现在：处境、能力、限制、资源（可逐步拼接）
    goal_clarity: enum        # high | medium | low
    current_clarity: enum     # high | medium | low

  identity:
    age_range: string         # 年龄档
    occupation: string        # 职业 / 专业
    region_anchor: string     # 主要地区（国家/城市）
    native_language: string   # 母语
    role_anchor: string       # 身份类型（可由 occupation 推断）

  capability_snapshot:        # 可选，非默认必采
    self_assessed_level: string   # 自评一句话或 A1–C2
    strongest: string
    weakest: string
```

**默认策略**：

| 字段 | 策略 |
|------|------|
| `goal` | **必达**（清晰度 medium+） |
| `current` | **必达**（可多轮拼接） |
| `occupation` | 推断不到再问 |
| `region_anchor` | 推断不到再问 |
| `age_range` | 对 journey 有影响时再问 |
| `native_language` | 同上 |

**明确移出 universal 默认集**（改为 journey_meta 按需生成）：

婚姻状况、学历、CEFR 分项、听说读写分数、考试类型、截止日期等——仅在 meta 规划认为 blocking 时作为 **动态 meta** 出现。

### 5.2 Journey Meta（动态）

由阶段 B 生成；持久化于 `collection.journey_meta[]`。

```yaml
journey_meta_item:
  id: string                  # 如 meta_001
  key: string                 # 蛇形命名，名称即义，如 income_path
  label: string               # 短标签，如「收入路径」
  why: string                 # 为何需要此项
  priority: enum              # blocking | important | optional
  status: enum                # open | inferred | confirmed | waived
  value: string | null        # 闭合后的值（自由文本为主）
  confidence: float         # 0–1
  source: enum                # planner | user | inferred
  asked_count: int            # 已问次数，上限 2
```

**示例 — goal：赚美元 + 前端工程师**

| key | label | priority |
|-----|-------|----------|
| `income_path` | 收入路径（远程/跳槽/接单） | blocking |
| `target_market` | 目标市场 | blocking |
| `timeline_pressure` | 时间压力 | blocking |
| `interview_exposure` | 面试/英语暴露经验 | important |
| `biggest_blocker` | 最大障碍 | important |

**示例 — goal：雅思 7 分留学**

| key | label | priority |
|-----|-------|----------|
| `target_exam` | 考试类型 | blocking |
| `deadline` | 截止日期 | blocking |
| `current_prep` | 当前备考状态 | important |
| `weak_modules` | 薄弱模块 | important |

### 5.3 Collection（会话状态）

```yaml
collection:
  phase: enum                 # anchoring | meta_planning | collecting | sufficient
  journey_meta: array
  meta_plan_version: int
  route_sketch:               # 展示用，非门禁
    title: string
    summary: string
    milestones: string[]
  asked_log: array            # { target, question, turn }
  assumptions: array
  answered_effective: object  # 有效回答账本
  confident_fields: object    # 高置信推断
  cluster_ask_counts: object  # 语义簇追问计数
  release:
    status: enum              # collecting | sufficient | conditional
    reason: string
    confidence: float
  turn_count: int             # 对话轮次统计，无硬顶
  # v2 移除：budget_max, question_count 硬预算
```

### 5.4 与 v1 twin 的关系

实现期可保留 `twin` 外壳作兼容映射；**逻辑真源**为 `universal` + `journey_meta`。v1 的 `identity / capability / growth / scenario` 不再作为「问什么」的驱动源。

---

## 6. 交互要求

### 6.1 对用户

- **单输入框**为主：故事、锚点、meta 采集均用自然语言
- **可选**：跳过故事，直接从目标/现在开始
- **展示**：
  - 双锚点摘要（目标 / 现在）
  - 路线草图 `route_sketch`（信息性，非必确认）
  - 关键信息进度（如 blocking meta 闭合数，非 x/25 题）
  - 推断提示：「已从你的回答识别 N 项，跳过重复追问」

### 6.2 不对用户展示

- 多栏固定表单
- 固定 25 题进度条
- 字段清单式「请填写年龄、婚姻、学历…」

---

## 7. API 响应（概念）

每轮 `run` 返回核心结构：

```json
{
  "universal": {
    "anchors": { "goal", "current", "goal_clarity", "current_clarity" },
    "identity": { ... }
  },
  "collection": {
    "phase", "journey_meta", "route_sketch", "release", "turn_count"
  },
  "next_questions": [{
    "target": "meta:income_path | universal:goal | anchor:current",
    "question": "...",
    "why": "...",
    "hint": "..."
  }],
  "meta": {
    "inferred_fields": [],
    "confident_fields": {},
    "planner_source": "meta_planner | heuristic"
  }
}
```

---

## 8. 核心模块（实现指引）

| 模块 | 职责 |
|------|------|
| `anchor_extractor` | 从任意输入推断 goal / current / universal；更新 clarity |
| `meta_planner` | goal + current → journey_meta + route_sketch |
| `question_composer` | 自然语言问句生成 |
| `answer_enrich` | 整句全量推断，闭合多条 meta |
| `planner_guard` | open 过滤、追问上限、语义去重 |
| `release_evaluator` | sufficient / conditional，无题数硬顶 |
| `agent.run` | 阶段机编排 |

---

## 9. 与 v1 差异摘要

| 维度 | v1 | v2 |
|------|----|----|
| 起点 | batch_baseline 固定项 | goal + current 双锚点 |
| 问什么 | baseline + path.required_fields | journey_meta 动态列表 |
| 字段 | 固定 twin schema | universal 固定 + meta 动态 |
| 题数 | 25 硬上限 | 无上限，AI sufficient |
| 路线确认 | 常作 path_confirm 门禁 | **推断足够即进 meta 采集** |
| current | 倾向一次采集 | **逐步拼接** |
| 英语水平 | 常单独 CEFR 追问 | 融入 current 或 journey meta |

---

## 10. 实施里程碑

| 阶段 | 交付 | 说明 |
|------|------|------|
| **M1** | 双锚点 + 去掉 25 题 | `anchor_extractor`；`current` 逐步 merge |
| **M2** | `meta_planner` | 替代 v1 `llm_planner` 的固定 required_fields |
| **M3** | meta 问题流 + enrich | `target: meta:*`；闭合与防重复 |
| **M4** | sufficient 判定 | 新 `release_evaluator`；route_sketch 仅展示 |
| **M5** | universal 精简 + 映射层 | 旧 twin 只读兼容（可选） |

---

## 11. 验收标准

1. 用户只说「国内前端想赚美元」→ 先闭合 goal/current，**不**先问 CEFR/婚姻/学历。
2. `current` 可分多轮补充，清晰度达标后自动进入 meta 规划。
3. meta 规划后 **无需** 点「路线符合」即可进入 meta 采集题。
4. 同一 meta（或语义等价）**不会**换措辞问超过 2 次。
5. 用户一句回答可闭合多条 meta（如时间 + 市场 + 短板）。
6. blocking meta 全闭合后 AI 可 sufficient 放行，**无** 25 题拦截。
7. UI 无固定表单、无 x/25 题进度。

---

## 12. 已定产品决策记录

| # | 问题 | 决策 |
|---|------|------|
| 1 | 路线草图是否必须用户确认？ | **否**。推断足够后直接进入 meta 采集；`route_sketch` 仅展示。 |
| 2 | `current` 是否必须一段话？ | **否**。允许多轮逐步拼接，直至 `current_clarity` 达标。 |
| 3 | 元信息 schema？ | **混合**：universal 固定 + journey_meta 动态。 |
| 4 | 题数上限？ | **不设 25**；AI 判断 sufficient，软护栏见 §4.4。 |
| 5 | 下游 handoff？ | **本期不考虑**。 |

---

## 13. 参考

- [知识库/用户需求.md](../../知识库/用户需求.md) — 赚美元 / 人生故事 / 能力缺口叙事
- [prd.md](./prd.md) — v1 Digital Twin 全量建模愿景（长期）
- 现实现：`agent.py`、`planner.py`、`batch_baseline.py`（v1，待 M1 起逐步替换）
