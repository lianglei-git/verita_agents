# speech-to-text（`asr.transcribe`）

## 模式

| mode | 模型 | 说明 |
|---|---|---|
| **默认 / LS** | **paraformer-v2** | `audio_url` + `language` → 全文 + 词/句级时间戳 |
| `compare` | **qwen3-asr-flash** | 工作台跟读校对；**不**注册为 LS skill |

LS：`POST /api/agents/asr.transcribe/run`

## 环境变量

| 变量 | 说明 |
|---|---|
| `DASHSCOPE_API_KEY` | 必填 |
| `ASR_COMPARE_MODEL` | 默认 `qwen3-asr-flash` |
| `ASR_SUBTITLE_MODEL` / `ASR_MODEL` | 默认 `paraformer-v2` |
| `ASR_COMPATIBLE_BASE_URL` | qwen OpenAI 兼容端点 |
| `ASR_MEDIA_DIR` | 默认 `views/backend/media/asr` |
| `ASR_DISABLED` | `1` 禁用 |

视频 URL 抽音轨在 Agent 内（本机有 ffmpeg 时落一份 wav 备查）。Paraformer 仍拉 LS 签发的公网 URL，不对 LS 暴露「上传阿里云」接口。

## 调用

```python
# LS / 转写
run("", audio_url="https://example.com/a.wav", language="en", enable_word_timestamps=True)

# 工作台跟读
run("", mode="compare", reference="你好世界", audio_base64="...", audio_mime="audio/webm")
```
