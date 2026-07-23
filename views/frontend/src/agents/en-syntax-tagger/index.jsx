import { useMemo, useState } from 'react'
import './EnSyntaxTaggerView.less'

function Empty({ text }) {
  return <div className="empty-state">{text}</div>
}

function DataTable({ columns, rows }) {
  if (!rows?.length) return <Empty text="暂无表格数据" />
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key}>{c.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {columns.map((c) => (
                <td key={c.key} className={c.key === 'text' || c.key === 'span' ? 'word' : ''}>
                  {row[c.key] == null || row[c.key] === '' ? '—' : String(row[c.key])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function TrunkBlock({ trunk }) {
  if (!trunk) return null
  if (typeof trunk === 'string') {
    return (
      <p className="trunk-line">
        <strong>主干：</strong>
        {trunk}
      </p>
    )
  }
  const rows = [
    ['S 主语', trunk.subject],
    ['V 谓语', trunk.predicate],
    ['O 宾语', trunk.object],
    ['IO', trunk.indirect_object],
    ['DO', trunk.direct_object],
    ['C 补语', trunk.complement],
  ].filter(([, v]) => v != null)
  return (
    <dl className="summary-grid">
      {rows.map(([k, v]) => (
        <div key={k} className="summary-row">
          <dt>{k}</dt>
          <dd>
            {typeof v === 'object'
              ? `${v.text || ''} ${v.phrase_type ? `[${v.phrase_type}]` : ''} ${v.note || v.tense_voice || ''}`.trim()
              : String(v)}
          </dd>
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
  const [apiVersion, setApiVersion] = useState('v1')

  const handleVersionChange = (next) => {
    setApiVersion(next)
    setTab('overview')
  }

  const payload = result?.result || result || {}
  const analysis = payload.analysis || {}
  const spacyTokens = payload.spacy_tokens || []
  const meta = payload.meta || {}
  const hasError = Boolean(payload.error)
  const effectiveVersion = payload.api_version || meta.api_version || apiVersion

  const tabs = useMemo(() => {
    const base = [{ id: 'overview', label: '概览' }]
    if (effectiveVersion === 'v1') {
      base.push(
        { id: 'table', label: '成分表' },
        { id: 'tree', label: '结构树' },
        { id: 'special', label: '特殊结构' },
      )
    } else if (effectiveVersion === 'v2') {
      base.push(
        { id: 'segments', label: '片段表' },
        { id: 'tree', label: '结构树' },
      )
    } else {
      base.push(
        { id: 'chunks', label: '短语块' },
        { id: 'constituents', label: '成分' },
        { id: 'llm_tokens', label: 'LLM 词元' },
        { id: 'grammars', label: '语法点' },
      )
    }
    base.push({ id: 'spacy', label: 'spaCy 词元' }, { id: 'json', label: '原始 JSON' })
    return base
  }, [effectiveVersion])

  const handleRun = () => {
    if (typeof onRun === 'function') onRun({ version: apiVersion })
  }

  const showResult = analysis.sentence || spacyTokens.length > 0 || hasError

  return (
    <div className="en-syntax-tagger-view">
      {!reviewMode && (
        <div className="input-panel">
          <label>
            <span>分析版本（Prompt 模板）</span>
            <select
              value={apiVersion}
              onChange={(e) => handleVersionChange(e.target.value)}
              disabled={loading}
              className="version-select"
            >
              <option value="v1">v1 · 详细学术版（A）</option>
              <option value="v2">v2 · 对比学习版（B）</option>
              <option value="v3">v3 · JSON 数据版（C）</option>
            </select>
          </label>
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

      {showResult && (
        <>
          <div className="status-bar">
            <span>
              API: {effectiveVersion}
              {meta.profile_label ? ` · ${meta.profile_label}` : ''}
            </span>
            <span>LLM: {meta.llm_status || 'n/a'}</span>
            <span>spaCy: {meta.spacy_status || 'n/a'}</span>
            <span>tokens: {spacyTokens.length}</span>
          </div>

          <div className="tabs">
            {tabs.map((t) => (
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
                  <Empty text="暂无 LLM 分析结果（可查看 spaCy）" />
                ) : (
                  <>
                    <div className="hero-line">
                      <p className="sentence">{analysis.sentence || payload.input}</p>
                      {analysis.translation && (
                        <p className="translation">{analysis.translation}</p>
                      )}
                    </div>
                    <div className="meta-chips">
                      {(analysis.sentence_type || analysis.type) && (
                        <span className="chip">{analysis.sentence_type || analysis.type}</span>
                      )}
                      {analysis.tense_voice && (
                        <span className="chip">{analysis.tense_voice}</span>
                      )}
                    </div>
                    <h4>主干</h4>
                    <TrunkBlock trunk={analysis.trunk || analysis.structure_summary} />
                    {analysis.difficulty_notes && (
                      <>
                        <h4>难点说明</h4>
                        <p className="g-notes">{analysis.difficulty_notes}</p>
                      </>
                    )}
                    {Array.isArray(analysis.modifiers) && analysis.modifiers.length > 0 && (
                      <>
                        <h4>修饰成分</h4>
                        <ul className="mod-list">
                          {analysis.modifiers.map((m, i) => (
                            <li key={i}>
                              <code>{m.label || m.kind}</code> {m.text}
                              {m.modifies ? ` → ${m.modifies}` : ''}
                              {m.semantic ? `（${m.semantic}）` : ''}
                            </li>
                          ))}
                        </ul>
                      </>
                    )}
                  </>
                )}
              </div>
            )}

            {tab === 'table' && (
              <div className="panel">
                <DataTable
                  columns={[
                    { key: 'level', label: '层级' },
                    { key: 'role', label: '成分' },
                    { key: 'text', label: '内容' },
                    { key: 'pos_or_type', label: '类型' },
                    { key: 'function', label: '功能' },
                    { key: 'modifies', label: '修饰' },
                    { key: 'position', label: '位置' },
                  ]}
                  rows={analysis.constituent_table || []}
                />
              </div>
            )}

            {tab === 'segments' && (
              <div className="panel">
                <DataTable
                  columns={[
                    { key: 'span', label: '片段' },
                    { key: 'role', label: '成分' },
                    { key: 'pos', label: '词性' },
                    { key: 'role_in_trunk', label: '主干角色' },
                    { key: 'note', label: '备注' },
                  ]}
                  rows={analysis.segment_table || []}
                />
              </div>
            )}

            {tab === 'tree' && (
              <div className="panel">
                <pre className="tree-pre">
                  {analysis.tree || analysis.structure_tree || '（无树形数据）'}
                </pre>
              </div>
            )}

            {tab === 'special' && (
              <div className="panel">
                <h4>从句</h4>
                {(analysis.special_structures?.clauses || []).length === 0 ? (
                  <Empty text="无从句" />
                ) : (
                  <div className="chunk-list">
                    {analysis.special_structures.clauses.map((c, i) => (
                      <div key={i} className="chunk-card">
                        <div className="chunk-head">
                          <span className="chunk-type">{c.clause_type}</span>
                          {c.connector && <span className="chunk-role">{c.connector}</span>}
                        </div>
                        <code className="chunk-text">{c.text}</code>
                        <p className="chunk-mod">{c.function}</p>
                        {c.internal_brief && <p className="g-notes">{c.internal_brief}</p>}
                      </div>
                    ))}
                  </div>
                )}
                <h4>非谓语</h4>
                {(analysis.special_structures?.non_finites || []).length === 0 ? (
                  <Empty text="无非谓语" />
                ) : (
                  <div className="chunk-list">
                    {analysis.special_structures.non_finites.map((n, i) => (
                      <div key={i} className="chunk-card">
                        <div className="chunk-head">
                          <span className="chunk-type">{n.form}</span>
                        </div>
                        <code className="chunk-text">{n.text}</code>
                        <p className="chunk-mod">
                          {n.function}
                          {n.logical_subject ? ` · 逻辑主语：${n.logical_subject}` : ''}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
                {(analysis.semantic_roles || []).length > 0 && (
                  <>
                    <h4>语义角色</h4>
                    <DataTable
                      columns={[
                        { key: 'text', label: '片段' },
                        { key: 'grammatical', label: '语法' },
                        { key: 'semantic_role', label: '语义角色' },
                        { key: 'argument_type', label: '论元' },
                      ]}
                      rows={analysis.semantic_roles}
                    />
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

            {tab === 'constituents' && (
              <div className="panel">
                <DataTable
                  columns={[
                    { key: 'id', label: '#' },
                    { key: 'text', label: '内容' },
                    { key: 'type', label: '类型' },
                    { key: 'pos', label: '词性' },
                    { key: 'function', label: '功能' },
                    { key: 'start_index', label: 'start' },
                    { key: 'end_index', label: 'end' },
                  ]}
                  rows={analysis.constituents || []}
                />
              </div>
            )}

            {tab === 'llm_tokens' && (
              <div className="panel">
                <DataTable
                  columns={[
                    { key: 'id', label: '#' },
                    { key: 'word', label: '词' },
                    { key: 'lemma', label: '原形' },
                    { key: 'pos', label: '词性' },
                    { key: 'pos_code', label: '代码' },
                    { key: 'syntax_function', label: '功能' },
                    { key: 'dependency', label: '依存' },
                    { key: 'head_word', label: '中心词' },
                  ]}
                  rows={analysis.tokens || []}
                />
              </div>
            )}

            {tab === 'grammars' && (
              <div className="panel">
                {(analysis.grammars || []).length === 0 ? (
                  <Empty text="暂无语法点" />
                ) : (
                  <div className="grammar-list">
                    {analysis.grammars.map((g, i) => (
                      <div key={i} className="grammar-card">
                        <div className="grammar-head">
                          <span className="g-type">{g.grammar_type}</span>
                          <code className="g-content">{g.grammar_content}</code>
                        </div>
                        {g.grammar_function && (
                          <p className="g-func">功能：{g.grammar_function}</p>
                        )}
                        {g.grammar_notes && <p className="g-notes">{g.grammar_notes}</p>}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {tab === 'spacy' && (
              <div className="panel">
                <DataTable
                  columns={[
                    { key: 'index', label: '#' },
                    { key: 'text', label: '词' },
                    { key: 'lemma', label: 'lemma' },
                    { key: 'pos', label: 'pos' },
                    { key: 'tag', label: 'tag' },
                    { key: 'dep', label: 'dep' },
                    { key: 'head_text', label: 'head' },
                  ]}
                  rows={spacyTokens}
                />
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
        <Empty text="选择版本并输入英文句子后点击「开始分析」" />
      )}
    </div>
  )
}
