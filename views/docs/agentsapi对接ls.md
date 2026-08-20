# Agent API（给 LS）

> LS 已按本文冻成 **D-LS-10**（2026-08-15）。本仓消费说明：`docs/Agent 原子 API 需求（LS 对接）.md`。

五个 JSON skill，另加两个二进制 skill（`tts.speak` / `image.generate`）。LS 按任务图**分别调用**，不要指望一条接口跑完整条媒体流水线。  
Agent **不**返回 `object_id` / `asset_id` / `activity_id`。

二进制产物（TTS / 出图）的端到端流程见 [`TTS+png需求文档.md`](./TTS+png需求文档.md)。本节 §6 是字段定稿。

---

## 约定

| 项 | 值 |
|---|---|
| 入口 | `POST {AGENT_BASE_URL}/api/agents/{skill}/run` |
| Header | `Content-Type: application/json` · `X-Internal-Token: <AGENT_TOKEN>` |
| 语言码 | BCP-47：`en` / `ja` / `zh-CN` |
| 幂等 | 带 `request_id`（ULID）。相同 `request_id` + skill 回同一结果 |
| 发现 | `GET /api/agents/{skill}`（无需 token） |

**成功** HTTP 200：

```json
{
  "request_id": "01J…",
  "skill": "asr.transcribe",
  "output": {},
  "usage": {
    "provider": "aliyun",
    "model": "paraformer-v2",
    "tokens": 0,
    "usage_sec": 83.2,
    "cost_micros": null,
    "latency_ms": 4100
  },
  "versions": { "skill_version": "1.2.0", "package_version": "1.2.0" }
}
```

业务结果只看 `output`。ASR/TTS 看 `usage.usage_sec`，LLM 看 `usage.tokens`。

**失败**

| HTTP | code | LS 是否重试 |
|---|---|---|
| 400 | 业务错误（缺参等） | 否 |
| 401 | `unauthorized` | 否 |
| 404 | `agent_not_found` | 否 |
| 500 | `internal_error` | 是 |

```json
{ "error": { "code": "unauthorized", "message": "missing or invalid X-Internal-Token" } }
```

---

## 1. `asr.transcribe` — 音视频转写

媒体 URL 由 LS 签发（限时 GET）。视频由 Agent 内部抽音轨。

公测路径：https://assets.julebu.co/videos/6fbe4624-3fb4-4a8a-8c33-5f1aa617c35c.mp4

```http
POST /api/agents/asr.transcribe/run
```

```json
{
  "request_id": "01JEXAMPLEASR0000000000001",
  "audio_url": "https://…/signed",
  "language": "en",
  "enable_word_timestamps": true
}
```

`output`：

```json
{
  "text": "I am. We're in a competitive industry.",
  "duration_sec": 83.2,
  "timestamp_granularity": "word",
  "words": [
    { "text": "I", "start_ms": 21805, "end_ms": 21910, "confidence": 0.98 }
  ],
  "cues": [
    { "text": "I am.", "start_ms": 21805, "end_ms": 23000 }
  ]
}
```

- `language`：`en` / `ja` / `zh-CN`
- 无词级时间戳时 `timestamp_granularity` 为 `sentence`，只填 `cues`
- `usage.usage_sec` = 识别音频时长（秒）

---

## 2. `translate` — 片段翻译

`id` / `start_ms` / `end_ms` **原样回传**，只换 `text`。也可只传整段 `text`。

```http
POST /api/agents/translate/run
```

```json
{
  "request_id": "01JEXAMPLETR0000000000001",
  "source_lang": "en",
  "target_lang": "zh-CN",
  "items": [
    { "id": "c1", "text": "I am.", "start_ms": 21805, "end_ms": 23000 },
    { "id": "c2", "text": "We're in a competitive industry.", "start_ms": 23010, "end_ms": 25900 }
  ]
}
```

`output`：

```json
{
  "items": [
    { "id": "c1", "text": "我是。", "start_ms": 21805, "end_ms": 23000 },
    { "id": "c2", "text": "我们处在一个竞争激烈的行业。", "start_ms": 23010, "end_ms": 25900 }
  ]
}
```

---

## 3. `sentence.extract` — 拆学习句

`text` 与 `cues` 二选一或同时给。无媒体时 `start_ms` / `end_ms` 为 `null`。

```http
POST /api/agents/sentence.extract/run
```

```json
{
  "request_id": "01JEXAMPLEEX0000000000001",
  "learning_language": "en",
  "cues": [
    { "id": "c1", "text": "I am.", "start_ms": 21805, "end_ms": 23000 },
    { "id": "c2", "text": "We're in a competitive industry.", "start_ms": 23010, "end_ms": 25900 }
  ]
}
```

`output`：

```json
{
  "sentences": [
    { "text": "I am.", "start_ms": 21805, "end_ms": 23000, "cue_ids": ["c1"] },
    { "text": "We're in a competitive industry.", "start_ms": 23010, "end_ms": 25900, "cue_ids": ["c2"] }
  ]
}
```

---

## 4. `sentence.analyze` — 单句分析

一次只分析**一句**。批量由 LS 循环调用。**无** `activity_id`。

这个 skill **从一开始就按 API 版本出不同结构**。LS 只负责存 JSON 和按版本选前端组件，不必把三版收成同一套字段。

| `api_version` | 别名 / `profile` | `analysis` 长什么样 | 前端 |
|---|---|---|---|
| `v1`（默认） | `academic` | 主干 / 修饰 / 树 / 成分表 | 精读、教研 |
| `v2` | `teaching` | 主干一句话 + 片段对照表 + 结构树 + 难点 | 教学对照 |
| `v3` | `json` | clauses / constituents（含下标）/ chunks / grammars | 高亮对齐 |

请求里带 `api_version`（或 `version` / `profile`）。回包用 `output.api_version` 决定怎么渲染。

```http
POST /api/agents/sentence.analyze/run
```

```json
{
  "request_id": "01JEXAMPLESENT000000000001",
  "text": "We're in a competitive industry.",
  "api_version": "v1",
  "learning_language": "en",
  "support_language": "zh-CN",
  "user_level": "B1",
  "goal": "商务口语"
}
```

三版共用的 `output` 外壳：

```json
{
  "api_version": "v1",
  "target_lang": "en",
  "explain_lang": "zh-CN",
  "analysis": {},
  "spacy_tokens": [],
  "meta": {
    "agent": "en-syntax-tagger",
    "profile": "academic",
    "status": "success",
    "package_version": "3.0.0",
    "api_version": "v1"
  }
}
```

`analysis` 随版本变。下面各举一小段。

**v1**

```json
{
  "sentence": "We're in a competitive industry.",
  "translation": "我们处在一个竞争激烈的行业。",
  "sentence_type": "简单句",
  "tree": "[S [NP We] [VP are [PP in a competitive industry]]]",
  "trunk": { "subject": { "text": "We" }, "predicate": { "text": "are" } },
  "modifiers": [],
  "constituent_table": [{ "role": "S", "text": "We", "function": "主语" }]
}
```

**v2**

```json
{
  "sentence": "We're in a competitive industry.",
  "translation": "我们处在一个竞争激烈的行业。",
  "trunk": "We are in a competitive industry.",
  "segment_table": [
    { "span": "We", "role": "主语", "note": "…" }
  ],
  "structure_tree": "[S …]",
  "difficulty_notes": "competitive 作前置定语。"
}
```

**v3**

```json
{
  "sentence": "We're in a competitive industry.",
  "translation": "我们处在一个竞争激烈的行业。",
  "constituents": [
    { "id": 1, "text": "We", "function": "subject", "start_index": 0, "end_index": 2 }
  ],
  "chunks": [],
  "grammars": []
}
```

---

## 5. `vocabulary.generate` — 词条

例句给**文本**，不要 object。发音音频本期不做。

```http
POST /api/agents/vocabulary.generate/run
```

```json
{
  "request_id": "01JEXAMPLEVC0000000000001",
  "lemma": "emotive",
  "context": "an emotive issue",
  "learning_language": "en",
  "support_language": "zh-CN",
  "user_level": "C1",
  "goal": "商务口语"
}
```

`output`：

```json
{
  "lemma": "emotive",
  "phonetic": { "notation": "IPA", "value": "ɪˈməʊtɪv" },
  "pos": ["adj"],
  "level": "C1",
  "forms": { "comparative": null, "superlative": null, "derived": ["emotively"] },
  "senses": [
    {
      "sense_id": "s1",
      "gloss": {
        "zh-CN": "易引起强烈感情的",
        "en": "arousing intense feeling"
      },
      "example_texts": [{ "lang": "en", "text": "an emotive issue" }]
    }
  ]
}
```

---

## 调用顺序（LS 侧）

典型媒体学习任务：

```
asr.transcribe
  → translate          （字幕/片段）
  → sentence.extract
  → sentence.analyze   （每句一次）
  → vocabulary.generate（每个词一次）
```

本期 JSON skill **没有** pipeline 入口。二进制 skill 见 §6。

---

## 6. 二进制 skill（方案 A，2026-08-19）

TTS / 出图走 **预签 PUT**：LS 在 `run` body 里注入 `upload`，Agent 把文件 PUT 到 `upload.url`，`output` 只回元数据。流程见 [`TTS+png需求文档.md`](./TTS+png需求文档.md)。

工作台无 `upload` 时 Agent 可落本地 `/media/tts/` 或 `/media/images/`，预览放在信封 `result.preview`，**不进** LS `output`。

禁止：`output` 里给文件 URL 或 base64；返回 `asset_id`。

### 6.0 `upload`（LS 注入，两个 skill 共用）

```json
{
  "upload": {
    "url": "https://…presigned-put…",
    "method": "PUT",
    "headers": { "Content-Type": "audio/mpeg" },
    "expires_at": "2026-08-19T04:00:00.000Z",
    "max_bytes": 104857600
  }
}
```

- PUT **必须**带 `headers` 里列出的键，否则签名失败。
- 只 PUT **一次**完整对象；不要分片。
- `max_bytes`：音频 ≤ 104857600（100MB），图片 ≤ 10485760（10MB）。超限 400 `payload_too_large`，不要截断上传。
- `uploaded=false` 或缺省、或 LS `Exists` 为假 → 该 step **失败**。

---

### 6.1 `tts.speak` — 文本转 MP3

Agent id：`text-to-speech`。配额：`usage.usage_sec` = `output.duration_sec`。

```http
POST /api/agents/tts.speak/run
```

```json
{
  "request_id": "01JEXAMPLETTS0000000000001",
  "text": "Hello. This is a test.",
  "language": "en",
  "voice": "Cherry",
  "upload": {
    "url": "https://…presigned-put…",
    "method": "PUT",
    "headers": { "Content-Type": "audio/mpeg" },
    "expires_at": "2026-08-19T04:00:00.000Z",
    "max_bytes": 104857600
  }
}
```

| 字段 | 说明 |
|---|---|
| `text` | 必填。待合成文本 |
| `language` | `en` / `ja` / `zh-CN` |
| `voice` | 可选。缺省走环境 `TTS_VOICE` |
| `upload` | LS 必填。工作台可省略 |

`output`：

```json
{
  "uploaded": true,
  "bytes": 184320,
  "mime": "audio/mpeg",
  "filename": "tts.mp3",
  "duration_sec": 12.4
}
```

业务错误（HTTP 400，不重试）：`empty_input` · `tts_unavailable` · `ffmpeg_missing` · `mp3_encode_failed` · `missing_upload` · `unsupported_upload_method` · `upload_expired` · `payload_too_large` · `upload_failed`。

---

### 6.2 `image.generate` — PNG（一个 skill + `mode`）

Agent id：`image-generate`。风格锚锁死 `STYLE_VERSION = v1.0`（手册一字不改）。配额：`usage.tokens = 1`（每次生成计 1）。

模式之间输入相近、配额相同，**不拆 skill**。LS 原样转发 `mode` 与附属字段。

```http
POST /api/agents/image.generate/run
```

| `mode` | 手册槽位 | 尺寸 | 透明 | 附属字段 |
|---|---|---|---|---|
| `cover` | Collection 封面 | 1920×1080 16:9 | 否 | `subject` 必填；`composition`：`centered` \| `thirds` \| `panorama`（默认 `centered`） |
| `goal` | 目标插画 | 1920×1080 16:9 | 否 | 轨道 A：`motif`（默认 `mountain_path`）。轨道 B：`profile` `{identity,current,goal,language}`（`goal` ≥10 字且 identity/current 已填；LLM 失败或过虚则回退 A） |
| `spot` | 功能插画 | 1024×1024 1:1 | 是 | `kind`：`empty` \| `onboarding` \| `badge` \| `error`；`subject` 可空（空则用 kind 默认主体） |
| `vocabulary` | 单词图 | 1024×1024 1:1 | 是 | `lemma` / `pos` / `sense`；或直接给 `visual`（义项→视觉短语，禁止裸单词直填模型） |
| `sentence` | 句子配图 | 1536×1024 3:2 | 否 | `text` 必填 |

`goal.motif`：`mountain_path` · `skyline` · `book_steps` · `bridge` · `harbor` · `doorway` · `runway` · `compass`。

**cover 示例**

```json
{
  "request_id": "01JEXAMPLEIMG0000000000001",
  "mode": "cover",
  "subject": "A hotel reception bell and a key card on a counter, a suitcase standing nearby",
  "composition": "thirds",
  "upload": {
    "url": "https://…presigned-put…",
    "method": "PUT",
    "headers": { "Content-Type": "image/png" },
    "expires_at": "2026-08-19T04:00:00.000Z",
    "max_bytes": 10485760
  }
}
```

**goal 轨道 A**（`upload` 同 §6.0，`Content-Type: image/png`，`max_bytes: 10485760`）

```json
{ "mode": "goal", "motif": "skyline" }
```

**goal 轨道 B**（LLM 视觉翻译；失败回退 motif）

```json
{
  "mode": "goal",
  "profile": {
    "identity": "frontend engineer",
    "current": "desk job, B1 English",
    "goal": "work overseas as a global engineer",
    "language": "en"
  },
  "motif": "mountain_path"
}
```

**spot / vocabulary / sentence**

```json
{ "mode": "spot", "kind": "empty" }
```

```json
{
  "mode": "vocabulary",
  "lemma": "ambulance",
  "pos": "noun",
  "sense": "a single ambulance with a cross symbol, side view"
}
```

```json
{ "mode": "sentence", "text": "We're in a competitive industry." }
```

`output`（所有 mode 同形；`filename` 以 `.png` 结尾）：

```json
{
  "uploaded": true,
  "bytes": 220184,
  "mime": "image/png",
  "filename": "spot.png",
  "width": 1024,
  "height": 1024
}
```

业务错误：`invalid_mode` · `empty_subject` · `image_unavailable` · `image_failed` · 以及与 TTS 相同的 upload 错误。
