import { useMemo, useState } from 'react'
import './TranslateView.less'

function asItems(payload) {
  const out = payload?.output
  if (out && typeof out === 'object' && Array.isArray(out.items)) return out.items
  return []
}

export default function TranslateView({
  userInput,
  onInputChange,
  onRun,
  loading,
  result,
  reviewMode,
}) {
  const [sourceLang, setSourceLang] = useState('en')
  const [targetLang, setTargetLang] = useState('zh-CN')
  const [rows, setRows] = useState([
    { id: 'c1', text: 'I am.', start_ms: 21805, end_ms: 23000 },
    { id: 'c2', text: "We're in a competitive industry.", start_ms: 23010, end_ms: 25900 },
  ])

  const payload = result?.result || result || null
  const translated = asItems(payload)
  const byId = useMemo(() => {
    const map = {}
    translated.forEach((row) => {
      map[row.id] = row
    })
    return map
  }, [translated])

  const handleRun = () => {
    const items = rows
      .map((r) => ({
        id: r.id.trim(),
        text: r.text.trim(),
        start_ms: r.start_ms === '' || r.start_ms == null ? null : Number(r.start_ms),
        end_ms: r.end_ms === '' || r.end_ms == null ? null : Number(r.end_ms),
      }))
      .filter((r) => r.id && r.text)
    onInputChange(items.map((r) => r.text).join('\n'))
    onRun({ source_lang: sourceLang, target_lang: targetLang, items })
  }

  const updateRow = (i, key, value) => {
    setRows((prev) => prev.map((row, idx) => (idx === i ? { ...row, [key]: value } : row)))
  }

  return (
    <div className="ls-skill-view translate-view">
      {!reviewMode && (
        <div className="input-panel">
          <div className="lang-row">
            <label>
              <span>source_lang</span>
              <input value={sourceLang} onChange={(e) => setSourceLang(e.target.value)} disabled={loading} />
            </label>
            <label>
              <span>target_lang</span>
              <input value={targetLang} onChange={(e) => setTargetLang(e.target.value)} disabled={loading} />
            </label>
          </div>
          <table className="align-table">
            <thead>
              <tr>
                <th>id</th>
                <th>原文</th>
                <th>start_ms</th>
                <th>end_ms</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={i}>
                  <td>
                    <input value={row.id} onChange={(e) => updateRow(i, 'id', e.target.value)} disabled={loading} />
                  </td>
                  <td>
                    <input value={row.text} onChange={(e) => updateRow(i, 'text', e.target.value)} disabled={loading} />
                  </td>
                  <td>
                    <input
                      value={row.start_ms ?? ''}
                      onChange={(e) => updateRow(i, 'start_ms', e.target.value)}
                      disabled={loading}
                    />
                  </td>
                  <td>
                    <input
                      value={row.end_ms ?? ''}
                      onChange={(e) => updateRow(i, 'end_ms', e.target.value)}
                      disabled={loading}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <button type="button" className="run-btn" onClick={handleRun} disabled={loading}>
            {loading ? '翻译中…' : '翻译'}
          </button>
          <p className="hint">视觉回归重点：译文行的 id / 时间戳必须与原文一致。</p>
        </div>
      )}

      {payload?.error && (
        <div className="error-banner">
          {payload.error}
          {payload.message ? ` — ${payload.message}` : ''}
        </div>
      )}

      {translated.length > 0 && (
        <table className="align-table result-table">
          <thead>
            <tr>
              <th>id</th>
              <th>原文</th>
              <th>译文</th>
              <th>ms</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((src) => {
              const dst = byId[src.id]
              const idOk = Boolean(dst)
              const msOk =
                !dst ||
                (dst.start_ms === src.start_ms && dst.end_ms === src.end_ms)
              return (
                <tr key={src.id} className={idOk && msOk ? '' : 'mismatch'}>
                  <td>
                    <code>{src.id}</code>
                    {!idOk && <span className="bad"> 缺失</span>}
                  </td>
                  <td>{src.text}</td>
                  <td>{dst?.text || '—'}</td>
                  <td>
                    {dst?.start_ms ?? '—'}–{dst?.end_ms ?? '—'}
                    {!msOk && <span className="bad"> 时间戳变了</span>}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </div>
  )
}
