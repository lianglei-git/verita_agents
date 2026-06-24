import './questions.less'

/**
 * 单选题
 * @param {Object} props
 * @param {import('../types').AgentQuestion} props.question
 * @param {string} props.value - 选中的 option.id
 * @param {(id: string) => void} props.onChange
 * @param {boolean} [props.disabled]
 */
export default function SingleChoice({ question, value, onChange, disabled = false }) {
  const options = question.options || []
  return (
    <fieldset className="gb-question gb-single" disabled={disabled}>
      <legend className="gb-question-label">{question.text}</legend>
      <div className="gb-options">
        {options.map((opt) => (
          <label key={opt.id} className={`gb-option ${value === opt.id ? 'selected' : ''}`}>
            <input
              type="radio"
              name={question.id}
              value={opt.id}
              checked={value === opt.id}
              onChange={() => onChange(opt.id)}
            />
            <span>{opt.label}</span>
          </label>
        ))}
      </div>
    </fieldset>
  )
}
