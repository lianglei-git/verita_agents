import { useState } from 'react'
import './VocabularyView.less'

export default function VocabularyView({
  userInput,
  onInputChange,
  onRun,
  loading,
  result,
  reviewMode,
}) {
  const [lemma, setLemma] = useState(userInput || 'emotive')
  const [context, setContext] = useState('an emotive issue')
  const [learning, setLearning] = useState('en')
  const [support, setSupport] = useState('zh-CN')
  const [level, setLevel] = useState('C1')
  const [goal, setGoal] = useState('商务口语')

  const payload = result?.result || result || null
  const card = payload?.output && typeof payload.output === 'object' ? payload.output : null

  const handleRun = () => {
    onInputChange(lemma)
    onRun({
      lemma: lemma.trim(),
      context: context.trim(),
      learning_language: learning,
      support_language: support,
      user_level: level,
      goal,
    })
  }

  return (
    <div className="ls-skill-view vocabulary-view">
      {!reviewMode && (
        <div className="input-panel">
          <label>
            <span>lemma</span>
            <input
              value={lemma}
              onChange={(e) => {
                setLemma(e.target.value)
                onInputChange(e.target.value)
              }}
              disabled={loading}
            />
          </label>
          <label>
            <span>context</span>
            <input value={context} onChange={(e) => setContext(e.target.value)} disabled={loading} />
          </label>
          <div className="lang-row">
            <label>
              <span>learning</span>
              <input value={learning} onChange={(e) => setLearning(e.target.value)} disabled={loading} />
            </label>
            <label>
              <span>support</span>
              <input value={support} onChange={(e) => setSupport(e.target.value)} disabled={loading} />
            </label>
            <label>
              <span>level</span>
              <input value={level} onChange={(e) => setLevel(e.target.value)} disabled={loading} />
            </label>
          </div>
          <label>
            <span>goal</span>
            <input value={goal} onChange={(e) => setGoal(e.target.value)} disabled={loading} />
          </label>
          <button type="button" className="run-btn" onClick={handleRun} disabled={loading || !lemma.trim()}>
            {loading ? '生成中…' : '生成词条'}
          </button>
        </div>
      )}

      {payload?.error && (
        <div className="error-banner">
          {payload.error}
          {payload.message ? ` — ${payload.message}` : ''}
        </div>
      )}

      {card?.lemma && (
        <article className="vocab-card">
          <header>
            <h3>{card.lemma}</h3>
            <span>
              {card.phonetic?.notation} {card.phonetic?.value || '—'}
              {card.pos?.length ? ` · ${card.pos.join(', ')}` : ''}
              {card.level ? ` · ${card.level}` : ''}
            </span>
          </header>
          {(card.senses || []).map((sense) => (
            <section key={sense.sense_id}>
              <p className="gloss">
                {Object.entries(sense.gloss || {}).map(([lang, text]) => (
                  <span key={lang}>
                    <code>{lang}</code> {text}
                  </span>
                ))}
              </p>
              <ul>
                {(sense.example_texts || []).map((ex, i) => (
                  <li key={i}>
                    <code>{ex.lang}</code> {ex.text}
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </article>
      )}
    </div>
  )
}
