# Agent 原子 API Roadmap（LS 对接）

> 需求原文：[Agent 原子 API 需求（LS 对接）.md](./Agent%20原子%20API%20需求（LS%20对接）.md)  
> 原则：沿用现有 Views 架构，不另起网关；能力在 `agents/`，HTTP 在 `views/backend`，前端做视觉回归 + API 文档。

---

## 0. 已确认的设计

| 决策 | 做法 |
|---|---|
| 入口 | 现有 `POST /api/agents/{id}/run`，不新开进程 / 端口 |
| 鉴权 | **后置**。统一中间件验 `X-Internal-Token`，开发期可关 |
| 工作流 | Agent 不互调、不拼流水线。LS 多次分别调用 |
| 复用 | ASR、句析基于现有实现重构，不重写供应商层 |
| 前端 | 工作台继续做视觉回归；每个 Agent 页补 API 文档 |
| 落库 | 不写 LS 库，不回传 `object_id` / `asset_id` / `activity_id` |
| 媒体入口 | 只收 LS 限时 **GET** URL（`audio_url`）。不收 multipart；base64 仅工作台跟读 |
| 媒体出口 | ASR 只出 JSON。TTS：LS 预签 **PUT** `upload_url`，Agent 写入后回元数据，不回路径 / id |

**skill 与现有 id**

Views 工作台继续用目录 id（`speech-to-text`）。LS 用 skill 原值（`asr.transcribe`）。  
`config.json` 增加 `skill`，registry **双注册**：同一条 Flask 路由同时认两种名字。

| skill（LS） | 现有 / 新建 | 策略 |
|---|---|---|
| `asr.transcribe` | `speech-to-text` | 重构 subtitle / Paraformer；跟读 compare 保留给前端 |
| `sentence.analyze` | `en-syntax-tagger` | 以 v1 academic 为底座，remap 到 `sentence/1.0` |
| `translate` | 新建 | 标准 `agents/` 模板 |
| `sentence.extract` | 新建 | 标准 `agents/` 模板 |
| `vocabulary.generate` | 新建 | 标准 `agents/` 模板 |

E10（`learning_path.generate` / `curriculum.analyze`）不进本 roadmap 主线。

---

**进度**：P0–P6 已落地。P7 联调收口可对照清单用真数据走一遍。

## 1. 阶段总览

```
P0 契约层          信封 / skill 别名 / 错误码 / 文档面板骨架
 │
 ├─ P1 asr.transcribe      重构 speech-to-text
 ├─ P2 sentence.analyze    重构 en-syntax-tagger v1
 │
 ├─ P3 translate           新建
 ├─ P4 sentence.extract    新建
 ├─ P5 vocabulary.generate 新建
 │
 ├─ P6 鉴权中间件          后置
 └─ P7 联调收口            五个 skill 示例 + 其余 Agent 补文档
```

P1 / P2 可并行（底座已在）。P3–P5 依赖 P0 信封稳定。P6 不挡联调。  
每阶段验收：**接口契约 + 工作台能跑 + 该 Agent 的 API 文档可见**。

---

## 2. P0 — 契约层（不改业务算法）

**目标**：LS 和 Views 走同一条路由，返回形状可对齐，前端不被立刻打断。

### 后端

- `config.json` 增加可选 `skill`（如 `"skill": "asr.transcribe"`）。
- `loader` / `registry`：`id` 与 `skill` 都指向同一 `run()`。
- HTTP 包装（只动 `views/backend/routes/api.py` 附近）：
  - 成功：`request_id` / `skill` / `output` / `usage` / `versions`
  - 失败：`error.code` + `error.message`；4xx 业务不可重试，5xx 原样
  - **过渡期**保留现有 `result`（= 今天的 agent 返回），Views 前端先不改读取路径
- 请求兼容两种 body：
  - Views：`{ "input", "options", "run_id" }`
  - LS：扁平字段 + `request_id`（ULID）
- `request_id` 透传；幂等先做进程内缓存（同 id 回同一结果），不落盘。

### 前端

- 工作台增加通用 **API 文档面板**（请求 / 响应 / 示例 / 错误码）。
- 数据来自该 Agent 的 `schema.json` + `examples/`，不在前端手写第二份契约。
- 先挂在 standalone 工作台；Console 嵌入态可折叠或不显示。

### 验收

- `POST /api/agents/speech-to-text/run` 与 `POST /api/agents/asr.transcribe/run` 打到同一个 run（P1 完成 skill 字段后）。
- 旧工作台（`input` + `options`）仍能跑现有 Agent。
- 任意已有 Agent 页能看到文档面板骨架（内容可先空）。

### 不做

- 不改 Paraformer / 句法 prompt。
- 不加 token 校验。

---

## 3. P1 — `asr.transcribe`（重构 speech-to-text）

**复用**：`agents/_lib/asr`（Paraformer、`AsrResult` / words / sentences）、`run_subtitle()`。

**改什么**

- 增加 LS 主路径：`audio_url` + `language`（BCP-47：`en` / `ja` / `zh-CN`）+ `enable_word_timestamps`。
- `output` 对齐需求 §4.1：`text` / `duration_sec` / `timestamp_granularity` / `words` / `cues`。
- `usage.usage_sec` = 识别音频时长；`usage.provider` / `model` 填阿里云实际值。
- 词级优先；做不到则 `timestamp_granularity=sentence`，只填 `cues`。
- 视频 URL：抽音轨留在 Agent 内（`_lib/asr` 增补），不对 LS 暴露「上传阿里云」接口。
- **保留** `mode=compare`（跟读校对），仅供工作台视觉回归，不注册为 LS skill。

**前端**

- subtitle 模式按新 `output` 展示全文 + cue / word 时间轴。
- 补 API 文档：三种语言各一条示例。

**验收**

- `en` / `ja` / `zh-CN` 各一条公网 URL；有时间戳；`usage_sec` 有值。
- 工作台跟读模式不回归。

---

## 4. P2 — `sentence.analyze`（重构 en-syntax-tagger）

**复用**：v1 academic 的 prompt、handler、`trunk` / `modifiers` / `tree` / `constituent_table`。

**改什么**

- LS 入参：`text` / `learning_language` / `support_language` / `user_level` / `goal` / `profile`。
- 内部仍走 v1；语言码从「中文/英语」收到 BCP-47（`zh-CN` / `en`）。
- `output` 对齐需求 §4.4（`sentence/1.0` 单条 analysis）：
  - `target_lang` = `learning_language`
  - `tree` / `trunk` / `constituent_table` 都要
  - `i18n`：学习语言正文 + 讲解语言译文；`phonetic.notation` = `IPA` | `pinyin` | `kana` | `romaji`
- **禁止**返回 `activity_id`。需求稿示例里的该字段以总则为准。
- `meta.api_version` 继续区分结构版本；本期 LS 默认 academic / v1。
- 输出用 JSON Schema 校验（可基于现有 `versions/v1/output.schema.json` 扩一版 LS schema）。

**前端**

- 现有成分表 / 树 / 主干可视化继续吃 remap 后的字段（加一层适配，避免重做 UI）。
- v2 / v3 仍可在工作台切换，**不**暴露给 LS。
- 补 API 文档。

**验收**

- 一次只分析一句；输出过 schema；无 `activity_id`。
- 工作台学术版视图不空。

---

## 5. P3 — `translate`（新建）

标准接入：`agents/translate/` + manifest + Generic 或轻量 custom view。

- 入参：`source_lang` / `target_lang` / `items[]`（`id` + `text` + 可选 `start_ms`/`end_ms`），或整段 `text`。
- 出参：`items[]` 的 `id` / 时间戳 **原样回传**，只换 `text`。
- `usage.tokens` 必填。
- 工作台：左原文、右译文、id 对照表（视觉回归重点：id 不错位）。
- API 文档 + 示例。

**验收**：片段 `id` 往返一致。

---

## 6. P4 — `sentence.extract`（新建）

- 入参：`learning_language` + `text` 和/或 `cues[]`。
- 出参：`sentences[]`（`text` / `start_ms` / `end_ms` / `cue_ids`）。
- 合并过碎 cue、切开过长句；无媒体时起止为 `null`。
- 工作台：cue 列表 → 句子列表，标出合并/切开。
- API 文档 + 示例。

**验收**：有 cue、纯文本两条路径都能出句。

---

## 7. P5 — `vocabulary.generate`（新建）

- 入参：`lemma` / `context` / `learning_language` / `support_language` / `user_level` / `goal`。
- 出参对齐 vocabulary/1.0：**例句给文本**（`example_texts`），不要 `object_id`。
- 发音音频本期不做。
- 工作台：词条卡片（音标、词性、义项、例句）。
- API 文档 + 示例。

**验收**：无 `object_id` / `asset_id`；至少学习语 + 讲解语 gloss。

---

## 8. P6 — 鉴权中间件（后置）

- Flask `before_request`：`/api/agents/*/run`（及 stream）校验 `X-Internal-Token`。
- Token 来自环境变量（Agent 侧 `INTERNAL_TOKEN`；LS 用 `AGENT_TOKEN` 或回退同名）。
- 本地：未设 token 则跳过，或 `AGENT_AUTH_DISABLED=1`。
- 工作台 / Console 开发请求不强制带头，避免打断视觉回归。

**验收**：设了 token 时无头 → 401；带头 → 与 P1–P5 行为一致。

---

## 9. P7 — 联调收口

对照需求 §7：

1. 五个 E9 接口内部 token（P6 后）打通，错误码稳定。
2. ASR 三语种 + 时间戳 + `usage_sec`。
3. `translate` id 往返一致。
4. `sentence.analyze` 过 schema，无 `activity_id`。
5. **没有**「一键处理整段媒体」的接口。
6. 每 skill 一份可复制示例（工作台 API 面板 = LS 抄进 `dev/api.llms.txt` 的来源）。

其余非 E9 Agent（画像、TTS、GoalBridge…）按同一文档面板补齐契约说明，不改 LS 范围。

---

## 10. 每阶段交付物（共同）

| 层 | 交付 |
|---|---|
| `agents/{id}/` | `run()`、schema、examples、必要时 prompt |
| `views/backend` | 只加路由包装 / 中间件，不把 prompt 写进 Flask |
| `views/frontend` | 工作台能跑通 + 该 Agent API 文档 |
| 文档 | 本文件勾进度；字段冻结后抄需求进 schema，不维护第三份 |

Agent **禁止**：互相 import、写 Flask 路由、返回 LS 落库 id。

---

## 11. 媒体文件（已冻结）

**ASR 入口**：`audio_url`（LS 限时 GET）。**出口**：JSON（`text` / `words` / `cues`），无文件。

**TTS 出口（V1.1 实现，契约先冻）**：LS 先建好 Object / 预签 PUT，Agent 只写入。

`POST /api/agents/tts.synthesize/run`（skill 名实现时再挂到 `text-to-speech`）

Request：

```json
{
  "request_id": "01J…",
  "text": "I am.",
  "voice": "Cherry",
  "language": "en",
  "upload_url": "https://ls-oss/…?sign=PUT"
}
```

成功 `output`（无 `object_id` / 无产品路径）：

```json
{
  "uploaded": true,
  "mime": "audio/wav",
  "duration_sec": 1.8,
  "bytes": 86400
}
```

- `upload_url` 缺失或 PUT 失败：4xx（签名过期 / 403 不可当 5xx 盲重试）。
- 工作台无 `upload_url` 时仍可落本地 `/media/tts/` 做试听，那条路径不进 LS 信封。
- Agent 不对 LS 暴露「上传阿里云」；厂商临时盘只在内部。

## 12. 明确不做（本路线全程）

- 独立 Agent 网关进程 / 9100 端口
- 媒体加工 pipeline API
- 转码 / VTT 文件（字幕 JSON 即可）
- Agent 直写 LS 桶再回路径 / `object_id`
- Language Focus、出题、配图、Tutor（需求 §6）；TTS **实现**后置，**契约**见 §11
- E10 Collection Studio skill（E9 未稳之前不做）

---

## 13. 建议开工顺序

1. **P0** — 信封 + skill 别名 + 文档面板骨架（后面每个 skill 都踩在这上面）
2. **P1** — ASR 重构（LS 链路第一步，底座最熟）
3. **P2** — 句析重构（底座最熟，和 P1 可并行）
4. **P3 → P4 → P5** — 三个新 Agent
5. **P6** — 鉴权
6. **P7** — 对照联调清单收口
