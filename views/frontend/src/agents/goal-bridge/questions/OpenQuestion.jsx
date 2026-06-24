import './questions.less'

/**
 * 开放题
 * @param {Object} props
 * @param {import('./types').AgentQuestion} props.question
 * @param {string} props.value
 * @param {(v: string) => void} props.onChange
 * @param {boolean} [props.disabled]
 */
export default function OpenQuestion({ question, value, onChange, disabled = false }) {
  return (
    <label className="gb-question gb-open">
      <span className="gb-question-label">{question.text}</span>
      <textarea
        rows={4}
        value={value}
        placeholder="请输入…"
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  )
}
