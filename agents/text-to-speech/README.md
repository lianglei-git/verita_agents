# text-to-speech

按句语音合成。厂商在 `_lib/tts/providers/`（首发 `aliyun_dashscope`）。

## 模式

| mode / 入口 | 用途 |
|---|---|
| `stream`（默认） | SSE 试听：`POST /api/agents/text-to-speech/stream` |
| `full` | 教学资料：切片合成 → 单音频落盘 + 句级字幕 JSON |
| `speak` / LS `tts.speak` | 合成 WAV；有 `upload` 则预签 PUT，`output` 只回元数据 |

LS：`POST /api/agents/tts.speak/run`（body 含 `text` / `language` / `upload`）。

工作台无 `upload` 时 `mode=speak` 把 WAV 写到 `/media/tts/`，预览在 `result.preview`，不进 LS `output`。

## 环境变量

| 变量 | 说明 |
|---|---|
| `DASHSCOPE_API_KEY` | 阿里云百炼 API Key |
| `DASHSCOPE_BASE_HTTP_API_URL` | 默认北京 `https://dashscope.aliyuncs.com/api/v1` |
| `TTS_PROVIDER` | 默认 `aliyun` |
| `TTS_MODEL` | 默认 `qwen3-tts-flash` |
| `TTS_VOICE` | 默认 `Cherry` |
| `TTS_SAMPLE_RATE` | 默认 `24000` |
| `TTS_MIME` | 默认 `audio/pcm` |
| `TTS_DISABLED` | `1` 禁用 |
| `TTS_MEDIA_DIR` | full / speak 工作台落盘根目录（默认 `views/backend/media/tts`） |

依赖：`dashscope>=1.24.5`。
