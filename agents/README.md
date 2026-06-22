# Agents 目录

仓库根目录下，每个子文件夹 = 一个可独立开发的 Agent SDK。

```
agents/
├── README.md                 # 本文件
├── _template/                # 复制此目录开始新 agent
├── echo/                     # 示例
├── user-profile/             # （待建）用户画像 Agent
├── route-planner/            # （待建）路线规划 Agent
└── ...
```

## 每个 Agent 最少包含

| 文件 | 作用 |
|------|------|
| `config.json` | 元信息 + Views 展示配置 |
| `agent.py` | 实现 `run()` 入口 |
| `schema.json` | 输入/输出字段说明（可选但推荐） |

## 原则

- Agent **不互相直接调用**，由 Orchestrator / Views 流水线调度
- `agent.py` 只做业务，不关心 HTTP 或 React
- 独立测试：`python -m agents.echo.agent` 或各目录自有 tests

## 接入 Views

见 [views/docs/AGENT-CONFIG.md](../views/docs/AGENT-CONFIG.md)
