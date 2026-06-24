# Agents 目录

仓库根目录下，每个子文件夹 = 一个可独立开发的 Agent SDK。

```
agents/
├── README.md
├── requirements.txt          # 公共依赖（openai 等）
├── _lib/                     # 公共基础设施（LLM、JSON 工具）
│   └── llm/
│       ├── client.py
│       └── config.py
├── _template/
├── user-profile/
├── route-planner/
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
- **LLM / 重试 / JSON 解析** 使用 `agents/_lib/`，不要复制到各 agent
- 独立测试：`python agents/user-profile/agent.py`

## 公共 LLM 库

```python
from _lib.llm import get_client, is_llm_available

client = get_client()  # 无 API key 时返回 None
if client:
    data = client.chat_json(prompt, system="...")
```

环境变量：

| 变量 | 说明 |
|------|------|
| `OPENAI_API_KEY` | API 密钥（必填才启用 LLM） |
| `OPENAI_BASE_URL` | 默认 `https://api.deepseek.com` |
| `LLM_MODEL` | 默认 `deepseek-chat` |
| `LLM_DISABLED` | `1` 时强制走启发式 / 规则逻辑 |

安装依赖：

```bash
pip install -r agents/requirements.txt
# 或通过 views：pip install -r views/requirements.txt
```

## 接入 Views

见 [views/docs/AGENT-CONFIG.md](../views/docs/AGENT-CONFIG.md)
