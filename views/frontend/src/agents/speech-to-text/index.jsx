import { useEffect, useRef, useState } from 'react'
import './SpeechToTextView.less'

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = String(reader.result || '')
      const b64 = result.includes(',') ? result.split(',')[1] : result
      resolve({ base64: b64, mime: file.type || 'audio/webm', dataUrl: result })
    }
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

function DiffView({ diff }) {
  if (!diff?.length) return null
  return (
    <p className="diff-line">
      {diff.map((op, i) => {
        if (op.op === 'equal') {
          return (
            <span key={i} className="diff-equal">
              {op.text}
            </span>
          )
        }
        if (op.op === 'replace') {
          return (
            <span key={i} className="diff-group">
              <span className="diff-ref">{op.ref}</span>
              <span className="diff-hyp">{op.hyp}</span>
            </span>
          )
        }
        if (op.op === 'delete') {
          return (
            <span key={i} className="diff-ref">
              {op.ref}
            </span>
          )
        }
        if (op.op === 'insert') {
          return (
            <span key={i} className="diff-hyp">
              {op.hyp}
            </span>
          )
        }
        return null
      })}
    </p>
  )
}

function isHttpUrl(value) {
  const s = String(value || '').trim()
  return s.startsWith('http://') || s.startsWith('https://')
}

export default function SpeechToTextView({
  userInput,
  onInputChange,
  onRun,
  loading,
  result,
  reviewMode,
}) {
  const [mode, setMode] = useState('compare')
  const [reference, setReference] = useState('')
  const [audioUrl, setAudioUrl] = useState('')
  const [error, setError] = useState('')
  const [recording, setRecording] = useState(false)
  const [audioPreview, setAudioPreview] = useState(null)
  const [pendingAudio, setPendingAudio] = useState(null) // { base64, mime, dataUrl }
  const [activeIndex, setActiveIndex] = useState(null)

  const mediaRecorderRef = useRef(null)
  const chunksRef = useRef([])
  const audioRef = useRef(null)

  const payload = result?.result || result || null

  useEffect(() => {
    if (!payload) return
    if (payload.error) setError(payload.error)
    else setError('')
  }, [payload])

  const busy = loading || recording

  const startRecording = async () => {
    setError('')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      chunksRef.current = []
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }
      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop())
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' })
        const file = new File([blob], 'recording.webm', { type: blob.type })
        const packed = await fileToBase64(file)
        setPendingAudio(packed)
        setAudioPreview(packed.dataUrl)
      }
      mediaRecorderRef.current = recorder
      recorder.start()
      setRecording(true)
    } catch (err) {
      setError(err.message || '无法打开麦克风')
    }
  }

  const stopRecording = () => {
    mediaRecorderRef.current?.stop()
    setRecording(false)
  }

  const onPickFile = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setError('')
    try {
      const packed = await fileToBase64(file)
      setPendingAudio(packed)
      setAudioPreview(packed.dataUrl)
    } catch (err) {
      setError(err.message || '读取文件失败')
    }
  }

  const handleRun = () => {
    if (typeof onRun !== 'function' || busy) return
    setError('')
    setActiveIndex(null)
    if (mode === 'compare') {
      if (!pendingAudio) {
        setError('请先录音或选择音频文件')
        return
      }
      const ref = (reference || userInput || '').trim()
      if (!ref) {
        setError('请填写参考文本')
        return
      }
      onInputChange(ref)
      onRun({
        mode: 'compare',
        reference: ref,
        audio_base64: pendingAudio.base64,
        audio_mime: pendingAudio.mime,
      })
      return
    }

    const url = (audioUrl || userInput || '').trim()
    if (!isHttpUrl(url)) {
      setError('请填写公网可访问的音频地址（http/https）')
      return
    }
    onInputChange(url)
    onRun({
      mode: 'subtitle',
      audio_url: url,
    })
  }

  const onAudioTimeUpdate = () => {
    const audio = audioRef.current
    const subs = payload?.subtitles
    if (!audio || !subs?.length) return
    const ms = audio.currentTime * 1000
    const hit = subs.find(
      (s) =>
        s.start_ms != null &&
        s.end_ms != null &&
        ms >= s.start_ms &&
        ms < s.end_ms,
    )
    if (hit && hit.index !== activeIndex) setActiveIndex(hit.index)
  }

  const playUrl = payload?.audio?.url || audioPreview
  const canRun =
    mode === 'compare' ? Boolean(pendingAudio) : isHttpUrl(audioUrl || userInput)

  return (
    <div className="speech-to-text-view">
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
              <option value="compare">跟读校对（字/词标红）</option>
              <option value="subtitle">音频转字幕</option>
            </select>
          </label>

          {mode === 'compare' && (
            <>
              <label>
                <span>参考文本</span>
                <textarea
                  rows={3}
                  value={reference}
                  onChange={(e) => {
                    setReference(e.target.value)
                    onInputChange(e.target.value)
                  }}
                  disabled={busy}
                  placeholder="输入正确参考句…"
                />
              </label>

              <div className="audio-actions">
                {!recording ? (
                  <button type="button" className="secondary-btn" onClick={startRecording} disabled={busy}>
                    开始录音
                  </button>
                ) : (
                  <button type="button" className="stop-btn" onClick={stopRecording}>
                    停止录音
                  </button>
                )}
                <label className="file-btn">
                  选择音频文件
                  <input type="file" accept="audio/*" hidden onChange={onPickFile} disabled={busy} />
                </label>
              </div>

              {audioPreview && (
                <audio controls src={audioPreview} className="preview-audio" />
              )}
            </>
          )}

          {mode === 'subtitle' && (
            <label>
              <span>音频公网地址</span>
              <input
                type="url"
                className="url-input"
                value={audioUrl}
                onChange={(e) => {
                  setAudioUrl(e.target.value)
                  onInputChange(e.target.value)
                }}
                disabled={busy}
                placeholder="https://example.com/audio.wav"
              />
            </label>
          )}

          <button
            type="button"
            className="run-btn"
            onClick={handleRun}
            disabled={busy || !canRun}
          >
            {loading ? '识别中…' : mode === 'compare' ? '识别并对比' : '生成字幕'}
          </button>
          <p className="hint">
            {mode === 'compare'
              ? '跟读校对使用 qwen3-asr-flash，录音/小文件可直接上传，无需公网 URL。'
              : '字幕模式使用 Paraformer：请填写百炼可拉取的公网音频 URL。'}
          </p>
        </div>
      )}

      {error && (
        <div className="error-banner">
          <strong>{error}</strong>
        </div>
      )}

      {payload?.mode === 'compare' && !payload.error && (
        <div className="result-panel">
          <h4>识别结果</h4>
          <p className="transcript">{payload.transcript}</p>
          <h4>
            差异（准确率{' '}
            {payload.stats?.accuracy != null
              ? `${Math.round(payload.stats.accuracy * 100)}%`
              : '—'}
            ）
          </h4>
          <DiffView diff={payload.diff} />
          <p className="legend">
            <span className="diff-equal">正确</span>
            <span className="diff-ref">参考/漏读</span>
            <span className="diff-hyp">识别/多读</span>
          </p>
        </div>
      )}

      {payload?.mode === 'subtitle' && !payload.error && (
        <div className="result-panel">
          <h4>字幕同步</h4>
          {playUrl && (
            <audio
              ref={audioRef}
              controls
              src={payload.audio?.url || playUrl}
              onTimeUpdate={onAudioTimeUpdate}
              className="preview-audio"
            />
          )}
          <div className="sentence-list">
            {(payload.subtitles || []).map((s) => (
              <div
                key={s.index}
                className={activeIndex === s.index ? 'sentence-card active' : 'sentence-card'}
              >
                <div className="sentence-meta">
                  <span>#{s.index + 1}</span>
                  <span>
                    {s.start_ms ?? '—'}ms – {s.end_ms ?? '—'}ms
                  </span>
                </div>
                <p className="sentence-text">{s.text}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
