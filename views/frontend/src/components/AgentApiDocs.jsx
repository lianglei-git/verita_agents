import { useMemo, useState } from 'react'
import './AgentApiDocs.less'

function pretty(value) {
  if (value == null) return ''
  if (typeof value === 'string') return value
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

function copyText(text) {
  if (!text) return Promise.resolve()
  if (navigator.clipboard?.writeText) {
    return navigator.clipboard.writeText(text)
  }
  return Promise.resolve()
}

function SchemaBlock({ title, schema }) {
  if (!schema) {
    return <p className="docs-empty">暂无 {title} schema。可在 agents/&#123;id&#125;/schema.json 补充。</p>
  }
  return <pre className="docs-pre">{pretty(schema)}</pre>
}

function ExampleBlock({ example, endpoint }) {
  const [copied, setCopied] = useState('')
  const requestText = pretty(example.request)
  const responseText = example.response ? pretty(example.response) : ''
  const curl = useMemo(() => {
    const body = example.request ? JSON.stringify(example.request) : '{}'
    return `curl -sS -X POST "http://127.0.0.1:5000${endpoint}" \\\n  -H "Content-Type: application/json" \\\n  -d '${body}'`
  }, [endpoint, example.request])

  const handleCopy = async (key, text) => {
    await copyText(text)
    setCopied(key)
    window.setTimeout(() => setCopied(''), 1200)
  }

  return (
    <article className="docs-example">
      <header>
        <h4>{example.title || example.id || '示例'}</h4>
        {example.description && <p>{example.description}</p>}
      </header>
      <div className="docs-toolbar">
        <button type="button" onClick={() => handleCopy('curl', curl)}>
          {copied === 'curl' ? '已复制 curl' : '复制 curl'}
        </button>
        <button type="button" onClick={() => handleCopy('req', requestText)}>
          {copied === 'req' ? '已复制请求' : '复制请求'}
        </button>
      </div>
      <span className="docs-label">Request</span>
      <pre className="docs-pre">{requestText || '—'}</pre>
      {responseText ? (
        <>
          <span className="docs-label">Response</span>
          <pre className="docs-pre">{responseText}</pre>
        </>
      ) : null}
    </article>
  )
}

export default function AgentApiDocs({ agent }) {
  const [open, setOpen] = useState(false)
  const [tab, setTab] = useState('contract')

  if (!agent) return null

  const endpoint = agent.endpoint || `/api/agents/${agent.skill || agent.id}/run`
  const examples = agent.examples || []
  const errors = agent.errors || []
  const schema = agent.schema || {}

  return (
    <section className={`agent-api-docs ${open ? 'is-open' : ''}`}>
      <button type="button" className="docs-toggle" onClick={() => setOpen((v) => !v)}>
        <span>API 文档</span>
        <span className="docs-toggle-meta">
          {agent.skill ? <code>{agent.skill}</code> : <code>{agent.id}</code>}
          <span className="docs-chevron">{open ? '收起' : '展开'}</span>
        </span>
      </button>

      {open && (
        <div className="docs-body">
          <p className="docs-endpoint">
            <span>POST</span>
            <code>{endpoint}</code>
          </p>
          <p className="docs-note">
            工作台用 <code>{'{ input, options, run_id }'}</code>；LS 用扁平字段 + <code>request_id</code>。
            设了 <code>INTERNAL_TOKEN</code>（或 <code>AGENT_TOKEN</code>）时，LS 需带
            <code>X-Internal-Token</code>。未设或 <code>AGENT_AUTH_DISABLED=1</code> 时跳过，工作台不用带头。
          </p>

          <nav className="docs-tabs">
            {[
              ['contract', '契约'],
              ['examples', `示例${examples.length ? ` ${examples.length}` : ''}`],
              ['errors', '错误码'],
            ].map(([id, label]) => (
              <button
                key={id}
                type="button"
                className={tab === id ? 'active' : ''}
                onClick={() => setTab(id)}
              >
                {label}
              </button>
            ))}
          </nav>

          {tab === 'contract' && (
            <div className="docs-pane">
              <span className="docs-label">成功信封</span>
              <pre className="docs-pre">
                {pretty({
                  request_id: '01J…',
                  skill: agent.skill || agent.id,
                  output: {},
                  usage: {
                    provider: '',
                    model: '',
                    tokens: 0,
                    usage_sec: 0,
                    cost_micros: null,
                    latency_ms: 0,
                  },
                  versions: { skill_version: agent.version || '1.0', package_version: agent.version || '0.0.0' },
                })}
              </pre>
              <span className="docs-label">Input schema</span>
              <SchemaBlock title="input" schema={schema.input || schema} />
              {schema.output && (
                <>
                  <span className="docs-label">Output schema</span>
                  <SchemaBlock title="output" schema={schema.output} />
                </>
              )}
            </div>
          )}

          {tab === 'examples' && (
            <div className="docs-pane">
              {examples.length === 0 ? (
                <p className="docs-empty">暂无示例。在 agents/&#123;id&#125;/examples/ 放 JSON 即可出现在这里。</p>
              ) : (
                examples.map((example) => (
                  <ExampleBlock
                    key={example.id || example.title}
                    example={example}
                    endpoint={endpoint}
                  />
                ))
              )}
            </div>
          )}

          {tab === 'errors' && (
            <div className="docs-pane">
              <table className="docs-table">
                <thead>
                  <tr>
                    <th>HTTP</th>
                    <th>code</th>
                    <th>重试</th>
                    <th>说明</th>
                  </tr>
                </thead>
                <tbody>
                  {errors.map((row) => (
                    <tr key={`${row.http}-${row.code}`}>
                      <td>{row.http}</td>
                      <td>
                        <code>{row.code}</code>
                      </td>
                      <td>{row.retry ? '可' : '否'}</td>
                      <td>{row.message}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </section>
  )
}
