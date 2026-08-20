# Agent API（给 LS）

> **已归档（2026-08-20）。** 现行契约：[agentsapi对接ls.md](../agentsapi对接ls.md)。本文仅为五个 JSON skill 的旧副本。

五个原子 skill。LS 按任务图**分别调用**，不要指望一条接口跑完整条媒体流水线。  
Agent **不**返回 `object_id` / `asset_id` / `activity_id`。

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

本期 JSON skill **没有** pipeline 入口。二进制 skill（`tts.speak` / `image.generate`）字段见 [`agentsapi对接ls.md`](./agentsapi对接ls.md) §6。

---

## 录制样本（给 LS E4）

`views/shared/ls-fixtures/`：JSON skill 录制样本 + `tts.speak` / `image.generate` 契约样本。  
Gateway / 薄客户端可对着样本开发和单测。二进制字段以 [`agentsapi对接ls.md`](./agentsapi对接ls.md) §6 为准。
