# speech-to-text（双模型 ASR）

## 模式

| mode | 模型 | 说明 |
|------|------|------|
| `compare` | **qwen3-asr-flash** | 参考文本 + 音频 → 识别 + 字/词级 diff 标红；小文件可直接 base64 上传 |
| `subtitle` | **paraformer-v2** | 用户提供公网音频 URL → 句级字幕时间轴 |

## 环境变量

| 变量 | 说明 |
|------|------|
| `DASHSCOPE_API_KEY` | 必填 |
| `ASR_COMPARE_MODEL` | 默认 `qwen3-asr-flash` |
| `ASR_SUBTITLE_MODEL` / `ASR_MODEL` | 默认 `paraformer-v2` |
| `ASR_COMPATIBLE_BASE_URL` | qwen OpenAI 兼容端点，默认 `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `ASR_MEDIA_DIR` | 默认 `views/backend/media/asr`（字幕 JSON 落盘） |
| `ASR_DISABLED` | `1` 禁用 |
| `DASHSCOPE_BASE_HTTP_API_URL` / `DASHSCOPE_WORKSPACE_ID` | 可选专属域名 |

字幕模式不在 agent 侧配置公网前缀；由调用方传入可被百炼拉取的 `audio_url`。

## 调用

```python
# 校对：直接传 base64（推荐）
run("", mode="compare", reference="你好世界", audio_base64="...", audio_mime="audio/webm")

# 字幕：用户输入公网音频地址
run("", mode="subtitle", audio_url="https://example.com/a.wav")
```
