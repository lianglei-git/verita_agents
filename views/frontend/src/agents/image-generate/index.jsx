import { useMemo, useState } from 'react'
import './ImageGenerateView.less'

const MODES = [
  { id: 'cover', label: 'cover · 封面 16:9' },
  { id: 'goal', label: 'goal · 目标插画' },
  { id: 'spot', label: 'spot · 功能插画' },
  { id: 'vocabulary', label: 'vocabulary · 单词图' },
  { id: 'sentence', label: 'sentence · 句子配图' },
]

const COMPOSITIONS = ['centered', 'thirds', 'panorama']
const MOTIFS = ['mountain_path', 'skyline', 'book_steps', 'bridge', 'harbor', 'doorway', 'runway', 'compass']
const KINDS = ['empty', 'onboarding', 'badge', 'error']

export default function ImageGenerateView({
  userInput,
  onInputChange,
  onRun,
  loading,
  result,
  reviewMode,
}) {
  const [mode, setMode] = useState('cover')
  const [subject, setSubject] = useState(
    'A hotel reception bell and a key card on a counter, a suitcase standing nearby',
  )
  const [composition, setComposition] = useState('centered')
  const [motif, setMotif] = useState('mountain_path')
  const [kind, setKind] = useState('empty')
  const [lemma, setLemma] = useState('ambulance')
  const [pos, setPos] = useState('noun')
  const [sense, setSense] = useState('a single ambulance with a cross symbol, side view')
  const [sentence, setSentence] = useState(userInput || "We're in a competitive industry.")
  const [identity, setIdentity] = useState('frontend engineer')
  const [current, setCurrent] = useState('desk job, B1 English')
  const [goal, setGoal] = useState('work overseas as a global engineer')
  const [language, setLanguage] = useState('en')
  const [useProfile, setUseProfile] = useState(false)

  const payload = result?.result || result || null
  const output = result?.output && typeof result.output === 'object' ? result.output : payload?.output
  const previewUrl = payload?.preview?.url
  const prompt = payload?.meta?.prompt || ''
  const err = payload?.error || result?.error?.code

  const canRun = useMemo(() => {
    if (mode === 'cover') return Boolean(subject.trim())
    if (mode === 'vocabulary') return Boolean(lemma.trim() || sense.trim())
    if (mode === 'sentence') return Boolean(sentence.trim())
    return true
  }, [mode, subject, lemma, sense, sentence])

  const handleRun = () => {
    const options = { mode }
    if (mode === 'cover') {
      options.subject = subject.trim()
      options.composition = composition
      onInputChange(options.subject)
    } else if (mode === 'goal') {
      options.motif = motif
      if (useProfile) {
        options.profile = { identity, current, goal, language }
      }
      onInputChange(useProfile ? goal : motif)
    } else if (mode === 'spot') {
      options.kind = kind
      if (subject.trim()) options.subject = subject.trim()
      onInputChange(options.subject || kind)
    } else if (mode === 'vocabulary') {
      options.lemma = lemma.trim()
      options.pos = pos.trim() || 'noun'
      if (sense.trim()) options.sense = sense.trim()
      onInputChange(options.lemma)
    } else {
      options.text = sentence.trim()
      onInputChange(options.text)
    }
    onRun(options)
  }

  return (
    <div className="ls-skill-view image-generate-view">
      {!reviewMode && (
        <div className="input-panel">
          <label>
            <span>mode</span>
            <select value={mode} onChange={(e) => setMode(e.target.value)} disabled={loading}>
              {MODES.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.label}
                </option>
              ))}
            </select>
          </label>

          {mode === 'cover' && (
            <>
              <label>
                <span>subject</span>
                <textarea
                  rows={3}
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  disabled={loading}
                />
              </label>
              <label>
                <span>composition</span>
                <select
                  value={composition}
                  onChange={(e) => setComposition(e.target.value)}
                  disabled={loading}
                >
                  {COMPOSITIONS.map((id) => (
                    <option key={id} value={id}>
                      {id}
                    </option>
                  ))}
                </select>
              </label>
            </>
          )}

          {mode === 'goal' && (
            <>
              <label>
                <span>motif（轨道 A 兜底）</span>
                <select value={motif} onChange={(e) => setMotif(e.target.value)} disabled={loading}>
                  {MOTIFS.map((id) => (
                    <option key={id} value={id}>
                      {id}
                    </option>
                  ))}
                </select>
              </label>
              <label className="check-row">
                <input
                  type="checkbox"
                  checked={useProfile}
                  onChange={(e) => setUseProfile(e.target.checked)}
                  disabled={loading}
                />
                用 profile 走轨道 B（目标 ≥10 字且身份/现状已填；失败回退 motif）
              </label>
              {useProfile && (
                <div className="lang-row">
                  <label>
                    <span>identity</span>
                    <input value={identity} onChange={(e) => setIdentity(e.target.value)} disabled={loading} />
                  </label>
                  <label>
                    <span>current</span>
                    <input value={current} onChange={(e) => setCurrent(e.target.value)} disabled={loading} />
                  </label>
                  <label>
                    <span>goal</span>
                    <input value={goal} onChange={(e) => setGoal(e.target.value)} disabled={loading} />
                  </label>
                  <label>
                    <span>language</span>
                    <input value={language} onChange={(e) => setLanguage(e.target.value)} disabled={loading} />
                  </label>
                </div>
              )}
            </>
          )}

          {mode === 'spot' && (
            <>
              <label>
                <span>kind</span>
                <select value={kind} onChange={(e) => setKind(e.target.value)} disabled={loading}>
                  {KINDS.map((id) => (
                    <option key={id} value={id}>
                      {id}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>subject（可空，空则用 kind 默认主体）</span>
                <textarea
                  rows={2}
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  disabled={loading}
                />
              </label>
            </>
          )}

          {mode === 'vocabulary' && (
            <div className="lang-row">
              <label>
                <span>lemma</span>
                <input value={lemma} onChange={(e) => setLemma(e.target.value)} disabled={loading} />
              </label>
              <label>
                <span>pos</span>
                <input value={pos} onChange={(e) => setPos(e.target.value)} disabled={loading} />
              </label>
              <label>
                <span>sense / visual</span>
                <input value={sense} onChange={(e) => setSense(e.target.value)} disabled={loading} />
              </label>
            </div>
          )}

          {mode === 'sentence' && (
            <label>
              <span>text</span>
              <textarea
                rows={3}
                value={sentence}
                onChange={(e) => setSentence(e.target.value)}
                disabled={loading}
              />
            </label>
          )}

          <button type="button" className="run-btn" onClick={handleRun} disabled={loading || !canRun}>
            {loading ? '生成中…' : '生成 PNG'}
          </button>
          <p className="hint">
            工作台无 upload，落本地 /media/images/。LS 信封 output 只有 uploaded / bytes / mime / filename /
            width / height。
          </p>
        </div>
      )}

      {err && (
        <div className="error-banner">
          {typeof err === 'string' ? err : err}
          {payload?.message ? ` — ${payload.message}` : ''}
          {result?.error?.message ? ` — ${result.error.message}` : ''}
        </div>
      )}

      {previewUrl && (
        <div className="preview-frame">
          <img className="preview-img" src={previewUrl} alt={output?.filename || 'generated'} />
        </div>
      )}

      {output?.mime === 'image/png' && (
        <p className="meta-line">
          {output.filename} · {output.width}×{output.height} · {output.bytes} bytes · uploaded=
          {String(output.uploaded)}
          {payload?.meta?.mode ? ` · mode=${payload.meta.mode}` : ''}
          {payload?.meta?.style_version ? ` · ${payload.meta.style_version}` : ''}
        </p>
      )}

      {prompt && <pre className="prompt-box">{prompt}</pre>}
    </div>
  )
}
