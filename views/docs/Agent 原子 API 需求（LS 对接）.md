# Agent 原子 API 需求（LS 对接）

> 给 Agent 项目工程师的对接清单。  
> 统一入口：`POST /api/agents/{skill_name}/run`（D-LS-9）。字段契约接入时抄进 `dev/api.llms.txt`。  
> 边界：Agent 不拼工作流、不持有 LS 表。

---

## 1. 分工（先看这个）

| | ls-service（本仓） | Agent 项目 |
|---|---|---|
| 产品数据 | Media / Object / Unit 落库、可见性、配额、activity | 不读写 LS 库 |
| 工作流 | `ai_task` 把多个 API 串成 step 图 | **禁止**「一条 API 跑完整条媒体加工流水线」 |
| 调用 | Gateway 唯一入口；内部 token 打 Agent | 原子 HTTP：一次请求、一种能力、一份结果 |
| 供应商 | 禁止 SDK | 阿里云 ASR/OSS、LLM、TTS 等全部在 Agent 内 |

Studio / 前端不直打 Agent。

---

## 2. 通用约定（所有接口共用）

**协议**

- HTTP JSON，UTF-8。**唯一入口**：`POST /api/agents/{skill_name}/run`。`skill_name` 用下表 skill 原值（含点号，如 `asr.transcribe`），不要为每个 skill 再开一条 path。
- 鉴权：内部 token（`X-Internal-Token`）。**不要**验用户 JWT；身份与配额在 LS。
- LS 侧 Agent 配置只走环境变量（§2.1），不要 YAML。
- 媒体入参：LS 签发的**限时下载 URL**（OSS）。Agent 若需先传到阿里云，**在 Agent 内部完成**，不要对 LS 再暴露「上传阿里云」接口。
- 语言码：BCP-47（`en` / `ja` / `zh-CN`）。
- 同步优先。单次 ASR 过长可做成「提交 + 查询」**一对**接口，仍算同一个 skill；不要做成多 skill 工作流。
- 超时：ASR 建议 ≤ 0.3 × 音频时长；LLM 类 P90 ≤ 15s。超时 / 5xx 原样返回，LS 负责重试。
- 幂等：请求带 `request_id`（ULID）。相同 `request_id` 返回同一结果即可，LS 另有 `dedupe_key`。

**统一响应信封**（便于 LS 写 activity）

成功：HTTP 200。

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
    "cost_micros": 12345,
    "latency_ms": 4100
  },
  "versions": {
    "skill_version": "1.0",
    "package_version": "3.0.0"
  }
}
```

失败：4xx 业务不可重试；5xx / 超时 LS 可重试。body 带 `error.code` + `error.message`。

`usage` 必填：ASR/TTS 用 `usage_sec`，LLM 用 `tokens`。`cost_micros` 有则填。LS **不**接受 Agent 返回的 `object_id` / `asset_id` / `activity_id`——那些是落库后才有的。

**输出约束**

- 顶层必须是合法 JSON，不要 Markdown 围栏。
- 字段级 Markdown 仅允许在讲解类文本里（Language Focus 等，本期不做）。

### 2.1 LS 环境变量

| 变量 | 必填 | 说明 |
|---|---|---|
| `AGENT_BASE_URL` | 是（联调/生产） | 例如 `http://127.0.0.1:9100`，不含 path。空则 Gateway 视为 Agent 不可用 |
| `AGENT_TOKEN` | 建议 | 打 Agent 的内部 token；未设则回退 `INTERNAL_TOKEN` |
| `AGENT_TIMEOUT` | 否 | 默认 LLM 超时，Go duration（如 `15s`） |
| `AGENT_ASR_TIMEOUT` | 否 | ASR 专用超时，可长于默认 |

不要把 skill 列表、模型名、path 模板放进环境变量。path 已冻结为 `/api/agents/{skill_name}/run`。

LS 封装：`internal/infra/agents`（薄 HTTP `Run`），**不要**建根目录 `client/agents`（那是 LC 的布局）。配额 / activity / 落库在 `modules/aicore`。

---

## 3. 本期必做（M1 · E9）

对应 ROADMAP **五个 MVP Skill**。LS 会按产品任务图**多次、分别**调用，例如：

`asr.transcribe` → `translate` → `sentence.extract` → 对每句 `sentence.analyze` → 对关键词 `vocabulary.generate`

| # | skill | 产品用途 | 输入（摘要） | 输出（摘要） | 配额类 |
|---|---|---|---|---|---|
| 1 | `asr.transcribe` | 音视频转写 + 时间戳 | 媒体 URL、识别语言 | 全文 + 词级（无则句级）时间戳 | ASR 秒 |
| 2 | `translate` | 字幕/句子翻译 | 文本或带时间戳片段、源/目标语言 | 对齐后的译文 | LLM 次 |
| 3 | `sentence.extract` | 从转写/正文拆出学习句 | 文本或 timed 片段、学习语言 | 句子列表（可带起止 ms） | LLM 次 |
| 4 | `sentence.analyze` | 句析：成分 / 语法 / 翻译 | 一句 + 学习/讲解语言 + 等级 | 见 §4.4，对齐 `sentence/1.0` 的 `analysis[]` 元素 | LLM 次 |
| 5 | `vocabulary.generate` | 词条生成 | 词/短语 + 语言 + 等级 + goal | 见 §4.5；例句给**文本**，不要 object_id | LLM 次 |

**不要做的（本期）**

- 一条「媒体进、句子+解析+词汇出」的 pipeline API。
- 转码（H.264 / MP3 / VTT 文件生成）。字幕给 JSON 片段即可，VTT 由 LS 拼（若以后要文件再加）。
- 写 OSS 回 LS、或回调 LS 落库。

---

## 4. 输入 / 输出草案

全部 `POST {AGENT_BASE_URL}/api/agents/{skill}/run`。body = 下方 Request；成功时业务结果在信封的 `output` 里。字段名可微调，**语义不要丢**。

### 4.1 `asr.transcribe`

`POST /api/agents/asr.transcribe/run`

**Request**

```json
{
  "request_id": "01J…",
  "audio_url": "https://…/signed",
  "language": "en",
  "enable_word_timestamps": true
}
```

- `language`：`en` / `ja` / `zh-CN`（PRD 13.8）。
- 视频：Agent 内部抽音轨，LS 不先转码。

**Response `output`**

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

- 优先字级时间戳（句子对齐用）。做不到则 `timestamp_granularity=sentence`，只填 `cues`。
- `usage.usage_sec` = 识别音频时长（秒）。

### 4.2 `translate`

`POST /api/agents/translate/run`

**Request**

```json
{
  "request_id": "01J…",
  "source_lang": "en",
  "target_lang": "zh-CN",
  "items": [
    { "id": "c1", "text": "I am.", "start_ms": 21805, "end_ms": 23000 }
  ]
}
```

无时间戳时 `items` 只带 `id` + `text`。也可接受单字段 `text`（整段翻译）。

**Response `output`**

```json
{
  "items": [
    { "id": "c1", "text": "我是。", "start_ms": 21805, "end_ms": 23000 }
  ]
}
```

`id` / `start_ms` / `end_ms` 原样回传，LS 用来对齐字幕和句子。

### 4.3 `sentence.extract`

`POST /api/agents/sentence.extract/run`

用于：ASR 之后拆句；纯文本 / 字幕文件无 ASR 时直接拆句。

**Request**

```json
{
  "request_id": "01J…",
  "learning_language": "en",
  "text": "可选，与 cues 二选一或同时给",
  "cues": [
    { "text": "I am.", "start_ms": 21805, "end_ms": 23000 }
  ]
}
```

**Response `output`**

```json
{
  "sentences": [
    {
      "text": "I am. We're in a competitive industry.",
      "start_ms": 21805,
      "end_ms": 23903,
      "cue_ids": []
    }
  ]
}
```

合并过碎的字幕 cue、切开过长句。无媒体时 `start_ms` / `end_ms` 为 null。

### 4.4 `sentence.analyze`

`POST /api/agents/sentence.analyze/run`

对齐补充设计 **sentence/1.0** 的单条 `analysis`（不要 `activity_id`）。

**Request**

```json
{
  "request_id": "01J…",
  "text": "I am. We're in a competitive industry.",
  "learning_language": "en",
  "support_language": "zh-CN",
  "user_level": "B1",
  "goal": "商务口语",
  "profile": "academic"
}
```

**Response `output`**

```json
{
  "target_lang": "en",
  "explain_lang": "zh-CN",
  "profile": "academic",
  "sentence_type": "复合句",
  "tree": "[S …]",
  "trunk": {
    "subject": {},
    "predicate": {},
    "object": null,
    "complement": null,
    "direct_object": null,
    "indirect_object": null
  },
  "modifiers": [
    {
      "kind": "attributive",
      "text": "…",
      "label": "Attrib",
      "modifies": "We're",
      "semantic": "…",
      "phrase_type": "CP"
    }
  ],
  "constituent_table": [
    {
      "role": "S",
      "text": "[SIMON]",
      "level": "主句",
      "function": "主语",
      "position": "句首",
      "pos_or_type": "NP"
    }
  ],
  "special_structures": { "clauses": [], "non_finites": [] },
  "semantic_roles": [],
  "translation": "我是。我们在竞争激烈的行业中。",
  "i18n": {
    "en": { "content": "I am. We're in a competitive industry.", "phonetic": { "notation": "IPA", "value": "…" } },
    "zh-CN": { "content": "我是。…", "phonetic": { "notation": "pinyin", "value": "…" } }
  },
  "meta": {
        "agent": "en-syntax-tagger",
        "profile": "academic",
        "status": "success",
        "activity_id": "01J…",
        "package_version": "3.0.0",
        "api_version":"1.0" // 每个版本都对应不同俄analysis结构
  }
}
```

- `target_lang` 必须等于 `learning_language`。
- `tree` / `trunk` / `constituent_table` 都要：表给 UI，树给高级视图。
- `i18n` 至少包含学习语言正文 + 讲解语言译文；`phonetic.notation` 为 `IPA` | `pinyin` | `kana` | `romaji`。
- 一次只分析**一句**。批量由 LS 循环调用。

### 4.5 `vocabulary.generate`

`POST /api/agents/vocabulary.generate/run`

对齐 **vocabulary/1.0**，但例句给文本。

**Request**

```json
{
  "request_id": "01J…",
  "lemma": "emotive",
  "context": "可选，来自原句",
  "learning_language": "en",
  "support_language": "zh-CN",
  "user_level": "C1",
  "goal": "商务口语"
}
```

**Response `output`**

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
      "example_texts": [
        { "lang": "en", "text": "an emotive issue" }
      ]
    }
  ]
}
```

不要返回 LS 的 `object_id` / `asset_id`。发音音频本期不做（TTS 后置）。

---

## 5. 同阶段可后做（M1 · E10）

Collection Studio 右栏。仍是**原子 JSON**，LS 拿结果去建 Unit。E9 未稳之前可以后做。

| # | skill | 产品用途 | 输入（摘要） | 输出（摘要） |
|---|---|---|---|---|
| 6 | `learning_path.generate` | Generate Learning Path | 问卷：学习/讲解语言、等级、从哪学到哪（goal） | 有序 Unit 大纲（title / type=lesson\|wordbook / 简述），**不要**直接建库 |
| 7 | `curriculum.analyze` | Analyze Curriculum / Recommend Units / Improve Structure | 现有大纲摘要（标题、类型、顺序） | 诊断 + 建议（增删改顺序的结构化列表） |

`Recommend Units` / `Improve Structure` 可与 `curriculum.analyze` 共用一个接口，用 `mode` 区分；不要做成「生成并创建 24 个 Unit」的工作流 API。

---

## 6. 明确不做 / 以后再开

| skill | 出现位置 | 建议时机 |
|---|---|---|
| TTS | 配额表、句子音频 | Runtime / V1.1。契约已冻：LS 预签 PUT `upload_url`，Agent 写入后回 `uploaded/mime/duration_sec/bytes`，不回 `object_id`（见 roadmap §11） |
| `language_focus.generate` | PRD 19.1 | V1.1 |
| `speaking.generate` / `conversation.generate` | PRD 19.1 | V1.1+ |
| Choice / Fill Blank 出题 | Unit Assistant | V1.1 |
| 句子配图 | PRD 13.8 | 可选，失败不阻塞 |
| `review.planner` | Review Blueprint | M3 |
| `mission.generate` / `insight.analyze` | Home | M3 |
| Tutor 问答 | 11.13 | M3，19.1 尚无 key |
| Exam 评估 | 强模型档 | M3 |
| 转码 / 抽音轨对 LS 暴露 | 原 D3 | 后置；抽音轨留在 Agent 内 |

---

## 7. 联调清单（Agent 侧自测即可）

1. 五个 E9 接口均能用内部 token 打通，错误码稳定。
2. ASR：`en` / `ja` / `zh-CN` 各一条；有时间戳；`usage_sec` 有值。
3. `translate` 片段 `id` 往返一致。
4. `sentence.analyze` 输出可被 JSON Schema 校验（无 `activity_id`）。
5. **没有**「一键处理整段媒体」的接口。
6. 提供 OpenAPI 或等价示例请求；LS 接入时抄进 `dev/api.llms.txt`。
