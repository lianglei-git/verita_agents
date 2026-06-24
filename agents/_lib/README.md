# agents/_lib

Agent 公共基础设施，供各 `agents/{id}/` 引用。

## LLM

提炼自 `Lab-ConstructingSpiralSyntax/llm_client.py`，修复了重试逻辑，并支持无 key 时优雅降级。

```python
from _lib.llm import get_client, is_llm_available, LLMConfig

if is_llm_available():
    client = get_client()
    text = client.chat("...")
    data = client.chat_json("...")
```

## 导入前提

- Views 加载 agent 时会自动把 `agents/` 加入 `sys.path`
- 独立运行某 agent 时，需在 `agent.py` 顶部 bootstrap `agents/` 路径（见 `user-profile/agent.py`）
