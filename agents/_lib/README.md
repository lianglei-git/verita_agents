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

## JSON

LLM 输出经 `json-repair` 修复后再解析（容忍尾逗号、截断、markdown 围栏等）：

```python
from _lib.json_utils import extract_json
```

## Planning（规划流水线契约）

统一画像、差距诊断、情景推演、自适应路线图与叙事创作的共享契约与安全约束：

```python
from _lib.planning import (
    empty_planning_profile,
    planning_profile_from_handoff,
    normalize_gap_diagnosis,
    build_safety_system_prompt,
    load_schema,
    validate_contract,
)

profile = planning_profile_from_handoff(handoff)
system = build_safety_system_prompt("scenario")
schema = load_schema("planning_profile")
```

JSON Schema 位于 `agents/_lib/planning/schemas/`。

- Views 加载 agent 时会自动把 `agents/` 加入 `sys.path`
- 独立运行某 agent 时，需在 `agent.py` 顶部 bootstrap `agents/` 路径（见 `user-profile/agent.py`）
