import { useState } from 'react'
import './SentenceExtractView.less'

const SAMPLE_CUES = `[
  { "id": "c1", "text": "I am.", "start_ms": 21805, "end_ms": 23000 },
  { "id": "c2", "text": "We're in a competitive industry.", "start_ms": 23010, "end_ms": 25900 }
]`

export default function SentenceExtractView({
  userInput,
  onInputChange,
  onRun,
  loading,
  result,
  reviewMode,
}) {
  const [language, setLanguage] = useState('en')
  const [text, setText] = useState(userInput || "I am. We're in a competitive industry.")
  const [cuesJson, setCuesJson] = useState(SAMPLE_CUES)
  const [useCues, setUseCues] = useState(true)
  const [parseError, setParseError] = useState('')

  const payload = result?.result || result || null
  const sentences = payload?.output?.sentences || []

  const handleRun = () => {
    setParseError('')
    const options = { learning_language: language }
    if (useCues) {
      try {
        const cues = JSON.parse(cuesJson || '[]')
        if (!Array.isArray(cues)) throw new Error('cues 必须是数组')
        options.cues = cues
      } catch (err) {
        setParseError(err.message || 'cues JSON 无效')
        return
      }
    }
    if (text.trim()) options.text = text.trim()
    onInputChange(text)
    onRun(options)
  }

  return (
    <div className="ls-skill-view sentence-extract-view">
      {!reviewMode && (
        <div className="input-panel">
          <label>
            <span>learning_language</span>
            <input value={language} onChange={(e) => setLanguage(e.target.value)} disabled={loading} />
          </label>
          <label>
            <span>正文 text（可选）</span>
            <textarea
              rows={3}
              value={text}
              onChange={(e) => {
                setText(e.target.value)
                onInputChange(e.target.value)
              }}
              disabled={loading}
            />
          </label>
          <label className="check-row">
            <input
              type="checkbox"
              checked={useCues}
              onChange={(e) => setUseCues(e.target.checked)}
              disabled={loading}
            />
            使用 cues
          </label>
          {useCues && (
            <label>
              <span>cues JSON</span>
              <textarea
                rows={7}
                value={cuesJson}
                onChange={(e) => setCuesJson(e.target.value)}
                disabled={loading}
              />
            </label>
          )}
          <button type="button" className="run-btn" onClick={handleRun} disabled={loading}>
            {loading ? '拆句中…' : '拆出学习句'}
          </button>
        </div>
      )}

      {(parseError || payload?.error) && (
        <div className="error-banner">{parseError || `${payload.error}${payload.message ? ` — ${payload.message}` : ''}`}</div>
      )}

      {sentences.length > 0 && (
        <ol className="sentence-out">
          {sentences.map((s, i) => (
            <li key={`${s.text}-${i}`}>
              <p>{s.text}</p>
              <span>
                {s.start_ms == null && s.end_ms == null ? '无时间戳' : `${s.start_ms ?? '—'}–${s.end_ms ?? '—'}ms`}
                {s.cue_ids?.length ? ` · cue_ids ${s.cue_ids.join(', ')}` : ''}
                {s.cue_ids?.length > 1 ? ' · 已合并' : ''}
              </span>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}
