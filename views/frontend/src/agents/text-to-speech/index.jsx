import { useEffect, useRef, useState } from 'react'
import { createPcmPlayer, formatDuration } from './pcmPlayer'
import './TextToSpeechView.less'

async function consumeSse(response, onEvent) {
  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop() || ''
    for (const part of parts) {
      const lines = part.split('\n')
      for (const line of lines) {
        if (!line.startsWith('data:')) continue
        const raw = line.slice(5).trim()
        if (!raw) continue
        try {
          onEvent(JSON.parse(raw))
        } catch {
          /* ignore malformed */
        }
      }
    }
  }
}

export default function TextToSpeechView({
  userInput,
  onInputChange,
  onRun,
  loading,
  result,
  reviewMode,
}) {
  const [mode, setMode] = useState('stream')
  const [streaming, setStreaming] = useState(false)
  const [error, setError] = useState('')
  const [sentences, setSentences] = useState([])
  const [activeIndex, setActiveIndex] = useState(null)
  const [voice, setVoice] = useState('Cherry')
  const [language, setLanguage] = useState('en')
  const [uploadUrl, setUploadUrl] = useState('')
  const [fullResult, setFullResult] = useState(null)
  const [speakResult, setSpeakResult] = useState(null)
  const playerRef = useRef(null)
  const abortRef = useRef(null)
  const audioRef = useRef(null)

  const payload = result?.result || result || null

  useEffect(() => {
    if (payload?.mode === 'full' && payload.audio) {
      setFullResult(payload)
      setSpeakResult(null)
      setError(payload.error || '')
    }
    const out = result?.output || payload?.output
    if (out && out.mime === 'audio/wav') {
      setSpeakResult({
        output: out,
        preview: payload?.preview,
        error: payload?.error,
        message: payload?.message,
      })
      setFullResult(null)
      setError(payload?.error || result?.error?.code || '')
    }
  }, [payload, result])

  const busy = streaming || loading

  const handleStream = async () => {
    const text = String(userInput || '').trim()
    if (!text || busy) return

    setError('')
    setSentences([])
    setFullResult(null)
    setSpeakResult(null)
    setActiveIndex(null)
    setStreaming(true)

    if (playerRef.current) {
      await playerRef.current.stop()
      playerRef.current = null
    }

    const controller = new AbortController()
    abortRef.current = controller
    const player = createPcmPlayer(24000)
    playerRef.current = player

    try {
      const res = await fetch('/api/agents/text-to-speech/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          input: text,
          options: { voice: voice.trim() || 'Cherry' },
        }),
        signal: controller.signal,
      })

      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.error || `Stream failed: ${res.status}`)
      }

      await consumeSse(res, (event) => {
        const ev = event.event
        if (ev === 'sentence_start') {
          const idx = event.sentence_index
          setSentences((prev) => {
            const next = [...prev]
            next[idx] = {
              index: idx,
              text: event.text || '',
              duration_ms: null,
              audio_url: null,
              status: 'queued',
            }
            return next
          })
          player.beginSentence(idx, (playIndex) => {
            setActiveIndex(playIndex)
            setSentences((prev) => {
              const next = [...prev]
              if (next[playIndex]) {
                next[playIndex] = { ...next[playIndex], status: 'playing' }
              }
              return next
            })
          })
        } else if (ev === 'audio_delta') {
          player.enqueueBase64Pcm(event.audio_b64)
        } else if (ev === 'sentence_end') {
          const idx = event.sentence_index
          const applyDuration = (measured) => {
            setSentences((prev) => {
              const next = [...prev]
              if (next[idx]) {
                next[idx] = {
                  ...next[idx],
                  duration_ms: measured || next[idx].duration_ms,
                  audio_url: event.audio_url || null,
                  status: next[idx].status === 'playing' ? 'playing' : 'done',
                }
              }
              return next
            })
          }
          if (event.duration_ms != null) {
            applyDuration(event.duration_ms)
          } else {
            player.captureSentenceDurationMs().then(applyDuration)
          }
        } else if (ev === 'error') {
          setError(event.error || 'tts_error')
        }
      })
    } catch (err) {
      if (err?.name !== 'AbortError') {
        setError(err.message || String(err))
      }
    } finally {
      setStreaming(false)
      abortRef.current = null
    }
  }

  const handleFull = () => {
    const text = String(userInput || '').trim()
    if (!text || busy || typeof onRun !== 'function') return
    setError('')
    setSentences([])
    setFullResult(null)
    setSpeakResult(null)
    setActiveIndex(null)
    onRun({ mode: 'full', voice: voice.trim() || 'Cherry' })
  }

  const handleSpeak = () => {
    const text = String(userInput || '').trim()
    if (!text || busy || typeof onRun !== 'function') return
    setError('')
    setSentences([])
    setFullResult(null)
    setSpeakResult(null)
    setActiveIndex(null)
    const options = {
      mode: 'speak',
      text,
      language,
      voice: voice.trim() || 'Cherry',
    }
    const putUrl = uploadUrl.trim()
    if (putUrl) {
      options.upload = {
        url: putUrl,
        method: 'PUT',
        headers: { 'Content-Type': 'audio/wav' },
        max_bytes: 104857600,
      }
    }
    onRun(options)
  }

  const handleStop = () => {
    abortRef.current?.abort()
    playerRef.current?.stop()
    setStreaming(false)
    setActiveIndex(null)
  }

  const replaySentence = (s) => {
    if (!s?.audio_url) return
    setActiveIndex(s.index)
    const audio = new Audio(s.audio_url)
    audio.play().catch(() => {})
  }

  const onFullAudioTimeUpdate = () => {
    const audio = audioRef.current
    const subs = fullResult?.subtitles
    if (!audio || !subs?.length) return
    const ms = audio.currentTime * 1000
    const hit = subs.find((s) => ms >= s.start_ms && ms < s.end_ms)
    if (hit && hit.index !== activeIndex) setActiveIndex(hit.index)
  }

  const displaySubs = fullResult?.subtitles || []

  return (
    <div className="text-to-speech-view">
      {!reviewMode && (
        <div className="input-panel">
          <label>
            <span>模式</span>
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value)}
              disabled={busy}
              className="mode-select"
            >
              <option value="stream">试听（流式边播）</option>
              <option value="full">生成资料（单音频 + 字幕）</option>
              <option value="speak">LS tts.speak（WAV 元数据）</option>
            </select>
          </label>
          <label>
            <span>language</span>
            <select value={language} onChange={(e) => setLanguage(e.target.value)} disabled={busy}>
              <option value="en">en</option>
              <option value="ja">ja</option>
              <option value="zh-CN">zh-CN</option>
            </select>
          </label>
          <label>
            <span>音色 voice</span>
            <input
              type="text"
              value={voice}
              onChange={(e) => setVoice(e.target.value)}
              disabled={busy}
              placeholder="Cherry"
            />
          </label>
          <label>
            <span>待合成文本</span>
            <textarea
              rows={5}
              value={userInput}
              onChange={(e) => onInputChange(e.target.value)}
              disabled={busy}
              placeholder="输入文章，按句号/问号/叹号/省略号分句…"
            />
          </label>
          {mode === 'speak' && (
            <label>
              <span>COS 预签 PUT URL（可选）</span>
              <textarea
                rows={3}
                value={uploadUrl}
                onChange={(e) => setUploadUrl(e.target.value)}
                disabled={busy}
                placeholder="https://bucket.cos.ap-xxx.myqcloud.com/key?q-sign-algorithm=sha1&…"
              />
            </label>
          )}
          <div className="btn-row">
            {mode === 'stream' ? (
              <>
                <button
                  type="button"
                  className="run-btn"
                  onClick={handleStream}
                  disabled={busy || !String(userInput || '').trim()}
                >
                  {streaming ? '合成中…' : '流式合成并播放'}
                </button>
                {streaming && (
                  <button type="button" className="stop-btn" onClick={handleStop}>
                    停止
                  </button>
                )}
              </>
            ) : mode === 'speak' ? (
              <button
                type="button"
                className="run-btn"
                onClick={handleSpeak}
                disabled={busy || !String(userInput || '').trim()}
              >
                {loading ? '合成中…' : '合成 WAV（tts.speak）'}
              </button>
            ) : (
              <button
                type="button"
                className="run-btn"
                onClick={handleFull}
                disabled={busy || !String(userInput || '').trim()}
              >
                {loading ? '生成中…' : '生成整段音频 + 字幕'}
              </button>
            )}
          </div>
        </div>
      )}

      {error && (
        <div className="error-banner">
          <strong>{error}</strong>
        </div>
      )}

      {speakResult?.output && (
        <div className="full-panel">
          <h4>tts.speak</h4>
          {speakResult.preview?.url && (
            <audio controls src={speakResult.preview.url} className="full-audio" />
          )}
          <p className="meta-line">
            {speakResult.output.filename} · {speakResult.output.mime} · {speakResult.output.bytes}{' '}
            bytes · {speakResult.output.duration_sec}s · uploaded=
            {String(speakResult.output.uploaded)}
          </p>
        </div>
      )}

      {fullResult?.audio?.url && (
        <div className="full-panel">
          <h4>整段音频</h4>
          <audio
            ref={audioRef}
            controls
            src={fullResult.audio.url}
            onTimeUpdate={onFullAudioTimeUpdate}
            className="full-audio"
          />
          <p className="meta-line">
            时长 {formatDuration(fullResult.audio.duration_ms)}
            {fullResult.meta?.job_id ? ` · job ${fullResult.meta.job_id}` : ''}
            {fullResult.audio.path ? ` · ${fullResult.audio.path}` : ''}
          </p>
          <h4>句级字幕</h4>
          <div className="sentence-list">
            {displaySubs.map((s) => (
              <div
                key={s.index}
                className={activeIndex === s.index ? 'sentence-card active' : 'sentence-card'}
              >
                <div className="sentence-meta">
                  <span className="idx">#{s.index + 1}</span>
                  <span className="dur">
                    {formatDuration(s.start_ms)} – {formatDuration(s.end_ms)}
                  </span>
                </div>
                <p className="sentence-text">{s.text}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {!fullResult && sentences.length > 0 && (
        <div className="sentence-list">
          {sentences.map((s) =>
            s ? (
              <div
                key={s.index}
                className={
                  activeIndex === s.index ? 'sentence-card active' : 'sentence-card'
                }
              >
                <div className="sentence-meta">
                  <span className="idx">#{s.index + 1}</span>
                  <span className="dur">{formatDuration(s.duration_ms)}</span>
                  {s.audio_url && (
                    <button
                      type="button"
                      className="replay-btn"
                      onClick={() => replaySentence(s)}
                    >
                      重播
                    </button>
                  )}
                </div>
                <p className="sentence-text">{s.text}</p>
              </div>
            ) : null,
          )}
        </div>
      )}

      {!sentences.length && !fullResult && !speakResult && !busy && !error && !reviewMode && (
        <div className="empty-state">
          {mode === 'stream'
            ? '选择试听模式后点击「流式合成并播放」'
            : mode === 'speak'
              ? '选择 tts.speak 后合成 WAV。可贴 COS 预签 PUT URL；不填只落本地'
              : '选择生成资料后点击「生成整段音频 + 字幕」'}
        </div>
      )}
    </div>
  )
}
