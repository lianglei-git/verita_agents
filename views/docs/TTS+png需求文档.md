二进制 skill（方案 A，LS 提案 2026-08-19）

TTS / 出图走 **预签 PUT**：LS 在 `run` body 里注入 `upload`，Agent 把文件 PUT 到 `upload.url`，`output` 只回元数据。流程见 [`agentsapi对接ls.md`](./agentsapi对接ls.md) §6。

`upload`（LS 注入）：

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

`output` 成功形（TTS）：

```json
{
  "uploaded": true,
  "bytes": 184320,
  "mime": "audio/mpeg",
  "filename": "tts.mp3",
  "duration_sec": 12.4
}
```

出图：`mime=image/png`，`filename` 以 `.png` 结尾，用 `width`/`height` 代替 `duration_sec`。

字段定稿见 [`agentsapi对接ls.md`](./agentsapi对接ls.md) §6。LS 可据此加入 `IsAISkill`。

### `tts.speak`

- 请求：`text`（必填）、`language`（`en` / `ja` / `zh-CN`）、可选 `voice`、LS 注入 `upload`（`Content-Type: audio/mpeg`，`max_bytes` ≤ 100MB）
- `output`：`uploaded` / `bytes` / `mime=audio/mpeg` / `filename=tts.mp3` / `duration_sec`
- 配额：`usage.usage_sec` = `duration_sec`

### `image.generate`（一个 skill + `mode`）

| mode | 手册 | 尺寸 | 透明 |
|---|---|---|---|
| `cover` | Collection 封面 | 1920×1080 | 否 |
| `goal` | 目标插画 | 1920×1080 | 否 |
| `spot` | 功能插画 | 1024×1024 | 是 |
| `vocabulary` | 单词图 | 1024×1024 | 是 |
| `sentence` | 句子配图 | 1536×1024 | 否 |

附属字段、请求/响应示例见对接文档 §6.2。配额：`usage.tokens = 1`。`upload.headers["Content-Type"] = image/png`，`max_bytes` ≤ 10MB。

禁止：`output` 里给文件 URL 或 base64；返回 `asset_id`。


# 下面是 “第三方系统的对接流程” 仅供该项目参考

Agent 对接流程（skill → OSS → Asset）

> **标注：LS ↔ Agent 对接文档。**  
> 线协议字段（请求/响应 JSON）以 [`agentsapi对接ls.md`](./agentsapi对接ls.md) 为准（D-LS-10）。  
> 本文件写**整体怎么接**：Agent 新做完一个能力之后，LS 怎样签发对象存储、怎样回写表、怎样才算 shipped。  
> 边界：D-LS-9（Agent 不拼工作流、不持有 LS 表）。管线：D-LS-11。

冲突时：冻结决策 > 本文 / `agentsapi对接ls.md` > 管线规范 > 本仓旧草案。

---

## 0. 先读哪几份

| 文件 | 用途 |
|---|---|
| 本文 | 端到端流程与接入清单 |
| `dev/agentsapi对接ls.md` | 每个 skill 的 HTTP 字段；**升字段先改它** |
| `dev/ls-fixtures/` | 录制样本，E4 单测对着它写 |
| `docs/Agent 原子 API 需求（LS 对接）.md` | LS 消费侧必须守的差 |
| `docs/LS Media AI 管线规范 v1.0.md` | 注册表、回写、灰显 |
| `internal/registry/media_ai.go` | 代码表；加能力 = 加行 |

Studio / 前端 **禁止**直打 Agent。只打 `POST /api/v4/ls/ai/tasks`。

---

## 1. 分工（不变）

| | LS（本仓） | Agent 项目 |
|---|---|---|
| 入口 | Gateway `agents.Run`；worker 跑 step | `POST /api/agents/{skill}/run` |
| 工作流 | `ls_ai_task` / `ls_ai_task_step` 拼图 | **禁止**一条接口跑完整课流水线 |
| 对象存储 | 本仓 filestore（`file_uri` 形如 `oss:bucket/…` 或 `local:…`） | **不**持有 LS 桶的长期密钥 |
| 产品表 | `ls_media_asset` / Object / activity | **不**写 LS 库，**不**返回 `asset_id` / `object_id` / `activity_id` |
| 供应商 | 禁止 SDK | 跑模型、调阿里云等 |

配置只走 `AGENT_BASE_URL` / `AGENT_TOKEN`（可回退 `INTERNAL_TOKEN`）/ `AGENT_TIMEOUT` / `AGENT_ASR_TIMEOUT`。

---

## 2. 两类产物

看 Agent `output` 里是不是「文件本身」。

### 2.1 JSON 文本（已 shipped）

ASR / translate / extract / analyze / vocab。

```
Studio POST /ai/tasks
  → worker 调 Agent（LS 签发限时 GET，如 audio_url）
  → output JSON 进 ls_ai_task_step.output_json
  → 写 ls_activity
  → 若注册表 writeback = vtt：LS 在进程内拼文件，UploadEx 进 filestore，upsert ls_media_asset
  → extract/analyze/vocab：不写 Asset；E10 / F4 再 mint Object
```

播放地址永远是 LS 对 `file_uri` 再签的 GET，不是 Agent URL。

### 2.2 二进制文件（方案 A，2026-08-19 冻结）

TTS（`*.mp3`）/ 出图（`*.png`）。字节不进 Gateway JSON、不进 `output`。

```
Studio POST /ai/tasks（task_type 将进白名单后才能 shipped）
  → worker 向本仓对象存储预生成 storage_path，签发限时 PUT（upload_url）
  → POST Agent /run，body 带 skill 输入 + upload
  → Agent 把供应商流 PUT 到 upload.url（Content-Type 必须与约定一致）
  → Agent 200，output 只含元数据（bytes / mime / duration_sec / width…），uploaded=true
  → LS Exists(storage_path) 为真才 upsert ls_media_asset
  → 写 ls_activity；step output 存元数据 JSON
  → Studio GET Entry，assets[] 出现 source=ai_generated，url 为本仓签名 GET
```

**禁止**：JSON 塞 base64；把 Agent/供应商 URL 写入 `file_uri`；把本仓长期密钥给 Agent；浏览器直连 Agent 流再自行上传。

封面规则不变：AI 回写 **不**改 `cover_asset_id`。

---

## 3. 方案 A 时序

```
Studio          LS api/worker           对象存储              Agent
  |  POST /ai/tasks                          |                  |
  |----------------->|                       |                  |
  |                  | 建 task+step          |                  |
  |                  | BuildStoragePath      |                  |
  |                  | Presign PUT --------->|                  |
  |                  | Run(skill, input+upload) ---------------->|
  |                  |                       |<----- PUT 文件 --|
  |                  |                       |                  |
  |                  |<------------ 200 output(uploaded, bytes) |
  |                  | Exists(path) -------->|                  |
  |                  | upsert ls_media_asset |                  |
  |                  | insert ls_activity    |                  |
  |  GET /media/entries/{id}                 |                  |
  |<-- assets[].url（本仓签名 GET）----------|                  |
```

`upload` 对象（LS 注入，Agent 原样使用；**不要**自己拼 OSS SDK）：

```json
{
  "request_id": "01J…",
  "upload": {
    "url": "https://…presigned-put…",
    "method": "PUT",
    "headers": { "Content-Type": "audio/mpeg" },
    "expires_at": "2026-08-19T04:00:00.000Z",
    "max_bytes": 104857600
  }
}
```

- `url` 限时（建议 ≤ 15 min，对齐该 skill 超时）。
- PUT **必须**带 `headers` 里列出的键，否则签名失败。
- 只 PUT **一次**完整对象；不要分片协议（本版不分片）。
- `max_bytes` 与 LS `CheckSize` 一致（audio ≤100MB，image ≤10MB）。超限 Agent 应 400，不要截断上传。

Agent `output`（文件已在我们的桶里之后）：

```json
{
  "uploaded": true,
  "bytes": 184320,
  "mime": "audio/mpeg",
  "filename": "tts.mp3",
  "duration_sec": 12.4,
  "sha256": "可选"
}
```

出图把 `duration_sec` 换成 `width` / `height`；`mime` = `image/png`；`filename` 以 `.png` 结尾。

`uploaded=false` 或缺省、或 LS `Exists` 为假 → 该 step **失败**，不写 asset。不要用供应商临时 URL 凑成功。

---

## 4. Agent 新做完一个能力之后：LS 接入清单

按顺序做。跳步会把 gray 按钮点成 400。

### Agent 侧交付

1. `POST /api/agents/{skill}/run` 可调通；`GET /api/agents/{skill}` 可发现（LS 不调用发现接口）。
2. 把 **请求/响应示例** 写入 `dev/agentsapi对接ls.md`（D-LS-10：先改该文件再改 client）。
3. 二进制 skill：实现方案 A（读 `upload.url` 并 PUT），不要回文件 URL。
4. 录一份夹具到 `dev/ls-fixtures/{skill}/`（200 + 至少一条 400）。
5. 约定：`request_id` 幂等；4xx 不重试、5xx 可重试；`usage`（TTS 用 `usage_sec`，出图用 `tokens` 或双方另冻）；`cost_micros` 可为 null。
6. **不**返回 LS 的 id。

出图若有多种模式：优先 **一个 skill + `input.mode`**（LS 原样转发）。只有模式之间输入/配额差到不能共用时才拆成多个 skill。mode 枚举由 Agent 交付后抄进 `agentsapi对接ls.md`，本仓不先发明。

建议 skill 名（未进白名单，未 shipped）：

| 产品按钮 | 建议 skill | 产物 | 配额意向 |
|---|---|---|---|
| TTS / 新闻转音频 / 小说朗读 | `tts.speak` | `audio` `.mp3` | `usage_sec`（类 ASR） |
| AI 配图 / 插画 | `image.generate` | `image` `.png` | 先按 LLM 次计数，点名再拆 |

### LS 侧接线（TTSIMG 开工时做，现在不要提前标 shipped）

1. `registry.IsAISkill` / `IsTaskType` 加入该 skill。
2. `QuotaClass` 加一行。
3. `MediaAIActions`：该按钮 `status=shipped`，`task_type` 非空，`writebacks` 指向 `audio`/`image`。
4. filestore **补 Presign PUT**（现网只有 `GetURL` + `UploadEx`；没有 PUT 预签则方案 A 落不了地）。`Exists` 已有，用来验收上传。
5. worker：调 Agent **之前** `BuildStoragePath` + Presign；把 `upload` 并进 step input。
6. materialize：`format=audio|image` 不再走「拼 VTT + UploadEx」。改为 Exists + upsert `ls_media_asset`（`source=ai_generated`，upsert 键 `(entry_id, asset_type, meta.role, meta.language)`）。
7. 超时：TTS/出图走偏长超时（可复用 `AGENT_ASR_TIMEOUT` 或另加 env，改口先改冻结决策）。
8. `dev/api.llms.txt` 白名单补 `task_type`。
9. 前端投影表与注册表同一行（禁止第二套灰显）。
10. `TEST_CASES.md` 对应该 skill 的 TC 从 draft → stable，并带测试函数名。

未完成 1–7 之前，注册表保持 `planned` / `gray`。

---

## 5. 会写哪些表、不会写哪些

一次成功的二进制 skill（以 TTS 为例）：

| 表 | 谁写 | 写什么 |
|---|---|---|
| `ls_ai_task` / `ls_ai_task_step` | LS worker | 状态、`input_json`（含 upload 元数据，**不要**把预签 URL 存进对外 GET）、`output_json`（uploaded/bytes/mime…） |
| `ls_activity` | Gateway | 每次 `Run` 一行；失败也写 `status=failed`。写 activity 失败 = 整次调用失败 |
| 对象存储 | Agent PUT | 文件本体。`file_uri` 是 LS 预生成的 path |
| `ls_media_asset` | LS materialize | `asset_type=audio`，`source=ai_generated`，`file_uri`，`mime`，`size_bytes`，`duration_ms`，`activity_id`，`meta.role=tts`，`meta.language`，可选 `meta.source_asset_id` |
| `ls_media_entry` | 不改封面 | `cover_asset_id` 保持原规则 |
| `ls_learning_object` | **本步不写** | TTS/出图不是课。要进画布另走 E10 mint（当前 TTS/出图 mint=false） |
| `ls_unit_media_ref` | **本步不写** | 关联已有 Entry 是 UMR；上传联传仍走 complete 带 `unit_id` |

对外 GET Entry **永不**返回 `file_uri`，只返回签名 `url`。

JSON 类 skill 对照：ASR 写 `subtitle` VTT asset；extract 只写 step + activity，Object 等 `from-pipeline`。

---

## 6. 失败、重试、幂等

| 情况 | 行为 |
|---|---|
| Agent 4xx | 不重试；step 失败；不写 asset |
| Agent 5xx / 超时 | 可重试；预签 URL 过期则 LS **重新签发**再调（同一 `request_id` 时 Agent 应认出：若已 PUT 成功则不要再生成，只回同一 output） |
| Agent 200 但 Exists=false | step 失败；当没上传 |
| 同 Entry 再跑同一 role+language | **覆盖**同一 asset 行，不堆历史（D-LS-11 upsert 键） |
| 存储配额用尽 | 不写 asset；与 AI 日配额同形失败 |
| 用户取消任务 | 已 PUT 的对象可留在桶内成孤儿；不在本版做 GC |

`dedupe_key` 仍在 LS 任务层。Agent 层幂等键是 `request_id` + skill。

---

## 7. 现在还没接线（给 Agent 开发对照）

| 项 | 状态 |
|---|---|
| 五个 JSON skill | shipped |
| `tts.speak` / `image.generate` | Agent 已交付字段（见 `agentsapi对接ls.md` §6）；LS 白名单未加；注册表 planned/gray |
| filestore Presign PUT | **未实现**（TTSIMG 的阻塞项） |
| `GET /ai/capabilities` | 不做；灰显读注册表投影 |
| L9 `learning_path.generate` | M3 最后，不走本文二进制通道 |

Agent 已把 TTS / 出图 mode 定稿写入 `agentsapi对接ls.md` §6 与 `ls-fixtures/`。LS 做 TTSIMG 清单第 1–10 步即可接入白名单。
