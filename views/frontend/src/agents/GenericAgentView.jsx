import './GenericAgentView.less'

function SchemaHints({ schema }) {
  if (!schema?.input) return null
  const fields = Object.entries(schema.input)
  if (fields.length === 0) return null

  return (
    <div className="schema-hints">
      <span className="schema-label">输入字段</span>
      <ul>
        {fields.map(([key, spec]) => (
          <li key={key}>
            <code>{key}</code>
            {spec.description && <span> — {spec.description}</span>}
          </li>
        ))}
      </ul>
    </div>
  )
}

export default function GenericAgentView({
  agent,
  mode,
  userInput,
  onInputChange,
  result,
  reviewMode,
  schema,
}) {
  return (
    <div className={`generic-agent-view mode-${mode}`}>
      {!reviewMode && (
        <>
          <label className="input-block">
            <span>输入</span>
            <textarea
              rows={mode === 'standalone' ? 6 : 4}
              value={userInput}
              placeholder="写入要送入此节点的内容"
              onChange={(e) => onInputChange(e.target.value)}
            />
          </label>
          <SchemaHints schema={schema} />
        </>
      )}

      {mode === 'standalone' && result && (
        <div className="result-block">
          <h3>最近结果</h3>
          <pre>{JSON.stringify(result, null, 2)}</pre>
        </div>
      )}
    </div>
  )
}
