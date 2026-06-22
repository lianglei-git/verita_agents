# Views 设计说明

## 这个产品是什么

**Views = Agent 流水线调试台 + 每个 Agent 的独立工作台。**

对应 [prd-pending.md](../../prd-pending.md) 里的长期目标：最终要在一条页面上跑通「用户画像 → 路线规划 → … → 练习」全链路；同时在开发任一单个 Agent 时，又能单独打开、单独调试，不依赖整条链已就绪。

---

## 分层架构

```
┌─────────────────────────────────────────────────────────────┐
│  frontend (Vite + React)                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Console 全链路 │  │ Agent 独立页  │  │ Agent 自定义视图  │  │
│  │ /              │  │ /agent/:id   │  │ 嵌套在面板内      │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘  │
└─────────┼─────────────────┼───────────────────┼────────────┘
          │                 │                   │
          └─────────────────┴───────────────────┘
                            │ /api/*
┌───────────────────────────┴─────────────────────────────────┐
│  views/backend (Flask)                                        │
│  routes · runs 历史 · workflow 加载 · agent 注册表              │
└───────────────────────────┬───────────────────────────────────┘
                            │ run()
┌───────────────────────────┴───────────────────────────────────┐
│  agents/  （仓库根目录，每个子目录 = 一个 SDK）                  │
│  user-profile/ · route-planner/ · story-scenario/ · ...       │
└───────────────────────────────────────────────────────────────┘
```

**职责边界**

| 层 | 做什么 | 不做什么 |
|----|--------|----------|
| `agents/{id}/` | 业务逻辑、`run()`、schema、单测 | HTTP、React、流程编排 |
| `views/backend` | API、执行历史、上下游上下文 | 业务 prompt 细节 |
| `views/frontend` | 展示、输入、回顾、路由 | 直接 import agent 代码 |

---

## 两种使用模式（核心设计）

### 模式 A：全链路 Console（已有）

- 路由：`/`（当前单页）
- 读取 `workflow` 的 `execution_order`
- 顶部：执行顺序条
- 左侧：运行记录
- 中间：当前节点的上游 / 当前 / 下游 I/O
- 用途：联调整条 MVP 流水线，验证上下游传参

### 模式 B：单 Agent 工作台（待加路由）

- 路由：`/agent/:id`（建议下一步用 react-router 实现）
- 只加载一个 agent 的 schema + 自定义 view
- 仍可调用同一套 `POST /api/runs/{id}/execute/{agent_id}`
- 用途：**独立开发**某个 agent，无需等上游实现

两种模式 **共用同一套后端与同一套 AgentView 组件**，避免写两套 UI。

---

## 每个 Agent 的展示：默认 vs 自定义

`agents/{id}/config.json`：

```json
"view": { "type": "default" }
```

| type | 行为 |
|------|------|
| `default` | 使用 `GenericAgentView`：文本输入 + JSON 结果 + schema 字段提示 |
| `custom` | 加载 `frontend/src/agents/{id}/index.jsx` 专属 UI |

### 嵌套关系（推荐）

```
Console 页面
└── AgentPanel（外壳：上下游 I/O、运行按钮、历史）
    └── <AgentViewResolver agentId={id} mode="embedded" />
            ├── default → GenericAgentView
            └── custom  → UserProfileView（例如：表单分栏、画像卡片预览）
```

独立页 `/agent/user-profile`：

```
AgentWorkbench
└── <AgentViewResolver agentId="user-profile" mode="standalone" />
```

**同一个 `UserProfileView` 组件，两种 layout：**

- `embedded`：嵌在流水线面板里，宽度受限，强调与上下游对照
- `standalone`：全宽，可放更复杂的交互（向导、多步表单、可视化）

这样 prd 里 7～11 个 agent 各自可以有截然不同的展示，但不破坏统一调试台。

### 示例：不同 Agent 可能需要不同 UI

| Agent | 展示侧重 |
|-------|----------|
| 用户画像 | 多字段表单 → 结构化画像卡片 |
| 路线规划 | 路线卡片列表、时间线 |
| 故事场景 | 章节大纲、剧情段落 |
| 知识点映射 | 表格：场景 ↔ EGP 语法点 |
| 课程编译 | 四段式骨架编辑器 |
| 内容练习 | 题目预览、题型切换 |

这些都不适合用一个 textarea 搞定，所以 **custom view 是刚需**，但应 optional——没写好 custom 前先用 default 跑通。

---

## 工作流配置：从 demo 到 MVP 全链路

工作流文件放在 `views/shared/workflows/`：

| 文件 | 用途 |
|------|------|
| `demo-pipeline.json` | 本地 echo / summarize 测试 |
| `mvp-pipeline.json` | prd MVP 7 agent 占位（节点 `status: planned`） |

manifest 指定默认工作流：

```json
"default_workflow": "demo-pipeline"
```

前端后续可增加 **工作流切换器**（demo / mvp / 完整闭环），一条页面承载不同 agent 集合。

### 与 prd-pending 的 agent 列表映射

| prd 阶段 | agent id 建议 | 目录 |
|----------|---------------|------|
| Orchestrator | `orchestrator` | 后端服务，不一定进 agents/ |
| 用户画像 | `user-profile` | `agents/user-profile/` |
| 路线规划 | `route-planner` | `agents/route-planner/` |
| 故事场景 | `story-scenario` | `agents/story-scenario/` |
| 知识点映射 | `knowledge-mapping` | `agents/knowledge-mapping/` |
| 课程编译 | `course-compiler` | `agents/course-compiler/` |
| 内容练习 | `content-exercise` | `agents/content-exercise/` |
| 第二阶段 | `assessment`, `competency`, `review` | 同上模式扩展 |

原则：**workflow 只描述顺序与节点名；实现永远在 `agents/`。**

---

## 执行历史与上下游（已有能力）

每次 run 记录各节点 `params` / `result`，用于：

- 全链路回顾
- 单 agent 页查看「上次独立测试结果」
- 将来 Orchestrator 持久化的一步一对齐

独立开发时：在 `/agent/:id` 仍可创建 run，只是 execution_order 可退化为 `[input, {agent}]` 的 **单节点工作流**（可选 `workflows/single-{id}.json` 代码生成）。

---

## 路由（已实现）

| 路径 | 页面 |
|------|------|
| `/` | 全链路 Console |
| `/agents` | Agent 列表 |
| `/agent/:id` | 单 Agent 独立工作台 |

`AgentViewResolver` 根据 `view.type` 加载 `GenericAgentView` 或 `frontend/src/agents/{id}/` 自定义组件。

首个 custom 示例：`user-profile`（表单 + 画像卡片）。

## 相关文档

```
verita_agents/
├── agents/                          # 所有 agent SDK
│   ├── user-profile/
│   │   ├── agent.py
│   │   ├── config.json
│   │   └── schema.json
│   └── ...
├── views/
│   ├── docs/
│   │   ├── DESIGN.md                # 本文件
│   │   └── AGENT-CONFIG.md          # 接入步骤
│   ├── shared/
│   │   ├── agents.manifest.json
│   │   └── workflows/
│   ├── backend/
│   │   └── agents/
│   │       ├── loader.py            # 扫描 agents/
│   │       └── registry.py          # 合并内置 + 外部
│   └── frontend/
│       └── src/
│           ├── pages/
│           │   ├── Console.jsx
│           │   └── AgentWorkbench.jsx
│           └── agents/              # 仅 custom view
│               ├── registry.js
│               └── user-profile/
│                   └── index.jsx
```

---

## 相关文档

- 接入步骤：[AGENT-CONFIG.md](./AGENT-CONFIG.md)
- 启动方式：[../readme.md](../readme.md)
- 产品 agent 规划：[../../prd-pending.md](../../prd-pending.md)
