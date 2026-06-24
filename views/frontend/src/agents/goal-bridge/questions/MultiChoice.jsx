import './questions.less'

/**
 * 多选题
 * @param {Object} props
 * @param {import('../types').AgentQuestion} props.question
 * @param {string[]} props.value - 选中的 option.id 列表
 * @param {(ids: string[]) => void} props.onChange
 * @param {boolean} [props.disabled]
 */
export default function MultiChoice({ question, value, onChange, disabled = false }) {
  const options = question.options || []
  const selected = new Set(value || [])

  const toggle = (id) => {
    const next = new Set(selected)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    onChange([...next])
  }

  return (
    <fieldset className="gb-question gb-multi" disabled={disabled}>
      <legend className="gb-question-label">{question.text}</legend>
      <div className="gb-options">
        {options.map((opt) => (
          <label key={opt.id} className={`gb-option ${selected.has(opt.id) ? 'selected' : ''}`}>
            <input
              type="checkbox"
              value={opt.id}
              checked={selected.has(opt.id)}
              onChange={() => toggle(opt.id)}
            />
            <span>{opt.label}</span>
          </label>
        ))}
      </div>
    </fieldset>
  )
}
