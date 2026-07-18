import { useState } from 'react'
import './EnSyntaxTaggerView.less'

const TABS = [
  { id: 'overview', label: '概览' },
  { id: 'chunks', label: '短语块' },
  { id: 'llm_tokens', label: 'LLM 词元' },
  { id: 'spacy', label: 'spaCy 词元' },
  { id: 'grammars', label: '语法点' },
  { id: 'json', label: '原始 JSON' },
]

function Empty({ text }) {
  return <div className="empty-state">{text}</div>
}

function SummaryGrid({ summary }) {
  if (!summary || typeof summary !== 'object') return null
  const rows = [
    ['主语', summary.subject],
    ['谓语', summary.predicate],
    ['宾语', summary.object],
    ['补语', summary.complement],
    ['状语', summary.adverbial],
    ['定语', summary.attributive],
  ].filter(([, v]) => v != null && v !== '')
  if (!rows.length) return null
  return (
    <dl className="summary-grid">
      {rows.map(([k, v]) => (
        <div key={k} className="summary-row">
          <dt>{k}</dt>
          <dd>{v}</dd>
        </div>
      ))}
    </dl>
  )
}

export default function EnSyntaxTaggerView({
  userInput,
  onInputChange,
  onRun,
  loading,
  result,
  reviewMode,
}) {
  const [tab, setTab] = useState('overview')

  const payload = result?.result || result || {}
  const analysis = payload.analysis || {}
  const spacyTokens = payload.spacy_tokens || []
  const meta = payload.meta || {}
  const hasError = Boolean(payload.error)

  const handleRun = () => {
    if (typeof onRun === 'function') onRun()
  }

  return (
    <div className="en-syntax-tagger-view">
      {!reviewMode && (
        <div className="input-panel">
          <label>
            <span>英文句子</span>
            <textarea
              rows={3}
              value={userInput}
              placeholder="例如：Although she was tired, she kept working because she had a deadline."
              onChange={(e) => onInputChange(e.target.value)}
              disabled={loading}
            />
          </label>
          <button
            type="button"
            className="run-btn"
            onClick={handleRun}
            disabled={loading || !String(userInput || '').trim()}
          >
            {loading ? '分析中…' : '开始分析'}
          </button>
        </div>
      )}

      {hasError && (
        <div className="error-banner">
          <strong>{payload.error}</strong>
          {payload.message ? ` — ${payload.message}` : ''}
        </div>
      )}

      {(analysis.sentence || spacyTokens.length > 0 || hasError) && (
        <>
          <div className="status-bar">
            <span>LLM: {meta.llm_status || 'n/a'}</span>
            <span>spaCy: {meta.spacy_status || 'n/a'}</span>
            {meta.spacy_model && <span>模型: {meta.spacy_model}</span>}
            <span>spaCy tokens: {spacyTokens.length}</span>
          </div>

          <div className="tabs">
            {TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                className={tab === t.id ? 'tab active' : 'tab'}
                onClick={() => setTab(t.id)}
              >
                {t.label}
              </button>
            ))}
          </div>

          <div className="tab-body">
            {tab === 'overview' && (
              <div className="panel">
                {!analysis.sentence && !analysis.translation ? (
                  <Empty text="暂无 LLM 分析结果（可查看 spaCy 词元页）" />
                ) : (
                  <>
                    <div className="hero-line">
                      <p className="sentence">{analysis.sentence || payload.input}</p>
                      {analysis.translation && (
                        <p className="translation">{analysis.translation}</p>
                      )}
                    </div>
                    <div className="meta-chips">
                      {analysis.sentence_type && (
                        <span className="chip">{analysis.sentence_type}</span>
                      )}
                      {analysis.tense_voice && (
                        <span className="chip">{analysis.tense_voice}</span>
                      )}
                    </div>
                    <h4>主干摘要</h4>
                    <SummaryGrid summary={analysis.structure_summary} />
                  </>
                )}
              </div>
            )}

            {tab === 'chunks' && (
              <div className="panel">
                {(analysis.chunks || []).length === 0 ? (
                  <Empty text="暂无短语块" />
                ) : (
                  <div className="chunk-list">
                    {analysis.chunks.map((c) => (
                      <div key={c.id ?? c.text} className="chunk-card">
                        <div className="chunk-head">
                          <span className="chunk-id">#{c.id}</span>
                          <span className="chunk-type">{c.type}</span>
                          <span className="chunk-role">{c.syntax_role}</span>
                        </div>
                        <code className="chunk-text">{c.text}</code>
                        {c.modify_target && (
                          <p className="chunk-mod">修饰：{c.modify_target}</p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {tab === 'llm_tokens' && (
              <div className="panel table-wrap">
                {(analysis.tokens || []).length === 0 ? (
                  <Empty text="暂无 LLM 词元" />
                ) : (
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>#</th>
                        <th>词</th>
                        <th>原形</th>
                        <th>词性</th>
                        <th>代码</th>
                        <th>功能</th>
                        <th>依存</th>
                        <th>中心词</th>
                      </tr>
                    </thead>
                    <tbody>
                      {analysis.tokens.map((t) => (
                        <tr key={t.id ?? `${t.word}-${t.pos_code}`}>
                          <td>{t.id}</td>
                          <td className="word">{t.word}</td>
                          <td>{t.lemma}</td>
                          <td>{t.pos}</td>
                          <td>
                            <code>{t.pos_code}</code>
                          </td>
                          <td>{t.syntax_function}</td>
                          <td>{t.dependency}</td>
                          <td>{t.head_word ?? '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}

            {tab === 'spacy' && (
              <div className="panel table-wrap">
                {spacyTokens.length === 0 ? (
                  <Empty
                    text={
                      meta.spacy_message
                        ? `暂无 spaCy 词元 — ${meta.spacy_message}`
                        : '暂无 spaCy 词元'
                    }
                  />
                ) : (
                  <>
                    <p className="hint">
                      spaCy 确定性标注：<code>pos</code> 粗粒度类型、
                      <code>tag</code> Penn 细标签、<code>dep</code> 依存关系
                    </p>
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>#</th>
                          <th>词</th>
                          <th>lemma</th>
                          <th>pos</th>
                          <th>tag</th>
                          <th>dep</th>
                          <th>head</th>
                          <th>chars</th>
                          <th>morph</th>
                        </tr>
                      </thead>
                      <tbody>
                        {spacyTokens.map((t) => (
                          <tr key={t.index}>
                            <td>{t.index}</td>
                            <td className="word">{t.text}</td>
                            <td>{t.lemma}</td>
                            <td>
                              <code className="pos-pill">{t.pos}</code>
                            </td>
                            <td>
                              <code>{t.tag}</code>
                            </td>
                            <td>
                              <code>{t.dep}</code>
                            </td>
                            <td>
                              {t.head_text}
                              <span className="muted"> ({t.head_idx})</span>
                            </td>
                            <td className="muted">
                              {t.char_start}:{t.char_end}
                            </td>
                            <td className="muted morph">{t.morph || '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </>
                )}
              </div>
            )}

            {tab === 'grammars' && (
              <div className="panel">
                {(analysis.grammars || []).length === 0 ? (
                  <Empty text="暂无语法点" />
                ) : (
                  <div className="grammar-list">
                    {analysis.grammars.map((g, i) => (
                      <div key={`${g.grammar_type}-${i}`} className="grammar-card">
                        <div className="grammar-head">
                          <span className="g-type">{g.grammar_type}</span>
                          <code className="g-content">{g.grammar_content}</code>
                        </div>
                        {g.grammar_function && (
                          <p className="g-func">功能：{g.grammar_function}</p>
                        )}
                        {g.grammar_notes && (
                          <p className="g-notes">{g.grammar_notes}</p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {tab === 'json' && (
              <div className="panel">
                <pre className="json-pre">{JSON.stringify(payload, null, 2)}</pre>
              </div>
            )}
          </div>
        </>
      )}

      {!result && !loading && !reviewMode && (
        <Empty text="输入英文句子后点击「开始分析」" />
      )}
    </div>
  )
}
