# Views 文档

> 2026-08-20 归档：已交付的需求原文与过期副本进 [`archive/`](./archive/)。**给 LS 对接的入口是 [`给LS.md`](./给LS.md)。**

## 给 LS（接线用）

| 文件 | 用途 | 状态 |
|---|---|---|
| **[给LS.md](./给LS.md)** | 交接清单：先读哪几份、冲突时听谁的 | 现行 |
| **[agentsapi对接ls.md](./agentsapi对接ls.md)** | HTTP 字段契约（D-LS-10）。五个 JSON skill + `tts.speak` + `image.generate`。**升字段先改这份** | 现行 |
| **[TTS+png需求文档.md](./TTS+png需求文档.md)** | 二进制方案 A：预签 PUT、Exists、写哪些表、TTSIMG 接入清单 | Agent 已交付；LS 白名单未加 |
| [../shared/ls-fixtures/](../shared/ls-fixtures/) | 请求/响应样本（E4 对字段） | 现行 |
| [Agent 原子 API 需求（LS 对接）.md](./Agent%20原子%20API%20需求（LS%20对接）.md) | LS 消费侧纪律（不拼工作流、不持 LS 表）。LS 仓已冻 D-LS-9 | 现行 |

## 本仓内部（不要当 LS 契约）

| 文件 | 用途 |
|---|---|
| [DESIGN.md](./DESIGN.md) | Views 工作台架构 |
| [AGENT-CONFIG.md](./AGENT-CONFIG.md) | 新 Agent 怎么挂进工作台 |

## 已归档

见 [`archive/README.md`](./archive/README.md)。包括旧 `LS API.md` 副本、本仓 roadmap、已锁进代码的出图 Prompt 手册。
