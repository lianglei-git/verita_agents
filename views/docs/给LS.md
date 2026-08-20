# 给 LS 的对接包

冲突时：冻结决策 **D-LS-10** = [`agentsapi对接ls.md`](./agentsapi对接ls.md) > 其他文档。  
Agent **不**返回 `object_id` / `asset_id` / `activity_id`。不要指望一条接口跑完整课流水线。

---

## 必读（按这个顺序交给 LS 工程师）

### 1. HTTP 字段 — [`agentsapi对接ls.md`](./agentsapi对接ls.md)

抄进 LS `dev/agentsapi对接ls.md`。入口：

```
POST {AGENT_BASE_URL}/api/agents/{skill}/run
Header: Content-Type: application/json · X-Internal-Token: <AGENT_TOKEN>
```

| skill | 产物 | 配额 |
|---|---|---|
| `asr.transcribe` | JSON 转写 | `usage_sec` |
| `translate` | JSON 对齐翻译 | `tokens` |
| `sentence.extract` | JSON 学习句 | `tokens` |
| `sentence.analyze` | JSON 句析（v1/v2/v3） | `tokens` |
| `vocabulary.generate` | JSON 词条 | `tokens` |
| `tts.speak` | WAV（预签 PUT） | `usage_sec` |
| `image.generate` | PNG（预签 PUT，一个 skill + `mode`） | `tokens = 1` |

二进制字段（`upload` / `output`）在该文件 **§6**。TTS 现网交付 **`audio/wav` / `tts.wav`**（不是 mp3）。

### 2. 端到端流程 — [`TTS+png需求文档.md`](./TTS+png需求文档.md)

给 LS 做 **TTSIMG** 用：预签 PUT、`Exists`、写 `ls_media_asset` / activity、接入清单第 1–10 步。  
HTTP 字段仍以 `agentsapi对接ls.md` §6 为准；本文写「怎么接、写哪些表」。

### 3. 夹具 — [`../shared/ls-fixtures/`](../shared/ls-fixtures/)

对着样本写 Gateway / 薄客户端单测，不必真打 Agent。  
`tts.speak/`、`image.generate/` 各有 200 + 400。

---

## 已有、不必再发明

[`Agent 原子 API 需求（LS 对接）.md`](./Agent%20原子%20API%20需求（LS%20对接）.md) 是 LS 消费侧必须守的差（D-LS-9）。LS 仓应已有对应冻结。字段细节以 `agentsapi对接ls.md` 为准。

---

## 可选（产品/设计，不是 HTTP）

出图风格锚原文已归档：[archive/LS AI 图片生成 Prompt 手册 v1.0.md](./archive/LS%20AI%20图片生成%20Prompt%20手册%20v1.0.md)。  
Agent 已锁进 `agents/image-generate/handbook.py`（`STYLE_VERSION = v1.0`）。LS 调 `image.generate` **不用**按手册拼 Prompt，只传 `mode` 与附属字段。

---

## 不要交给 LS 当契约

| 文件 | 原因 |
|---|---|
| `DESIGN.md` / `AGENT-CONFIG.md` | 本仓工作台 |
| `archive/LS API.md` | 过期副本（只有五个 JSON skill，且未含 TTS/出图） |
| `archive/Agent 原子 API roadmap.md` | 本仓实现计划，已完成 |

---

## LS 侧还没做完的（对照）

- `IsAISkill` 尚未加入 `tts.speak` / `image.generate`
- filestore **Presign PUT** 未实现 → 方案 A 落不了地
- 注册表保持 `planned` / `gray`，直到 TTSIMG 清单 1–7 完成
