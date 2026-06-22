# Agent 接入配置（极简版）

把一个 `agents/{id}/` 小项目接到 Views，只需 **3 步**。

## 1. 创建 Agent 目录

复制模板：

```bash
cp -r agents/_template agents/user-profile
```

编辑 `agents/user-profile/agent.py`，实现：

```python
def run(user_input: str, **kwargs) -> dict:
    return {"output": "...", "meta": {}}
```

编辑 `agents/user-profile/config.json`：

```json
{
  "id": "user-profile",
  "name": "用户画像 Agent",
  "description": "回答：这个用户是谁？他想去哪？",
  "view": { "type": "default" }
}
```

本地自测：

```bash
python agents/user-profile/agent.py "职业：前端，目标：海外面试"
```

## 2. 注册到 manifest

在 `views/shared/agents.manifest.json` 增加一条：

```json
{
  "id": "user-profile",
  "dir": "user-profile",
  "enabled": true
}
```

重启 `python views/run.py` 后，`GET /api/agents` 会出现该 agent。

## 3. 加入流水线（可选）

在 `views/shared/workflows/mvp-pipeline.json` 的 `execution_order` 里已有占位节点时，只需实现 agent 并确保 `agent_id` 与 `config.json` 的 `id` 一致。

切换工作流：

```
GET /api/workflow?name=mvp-pipeline
```

---

## config.json 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `id` | 是 | 全局唯一，与 workflow 节点 `agent_id` 一致 |
| `name` | 是 | 界面显示名 |
| `description` | 是 | 一句话职责 |
| `view.type` | 否 | `default` 通用面板；`custom` 使用独立 UI（见 DESIGN.md） |
| `schema_ref` | 否 | 指向 `schema.json`，供表单与文档生成 |

## schema.json

描述输入输出字段，方便：

- 前端自动生成表单（后续）
- 独立开发时对齐契约

## 不要做的事

- 不要在 `agent.py` 里写 Flask 路由
- 不要让 agent A import agent B
- 不要把 prompt 硬编码在 views 前端

调度与历史记录由 Views 后端 `runs` API 负责。
