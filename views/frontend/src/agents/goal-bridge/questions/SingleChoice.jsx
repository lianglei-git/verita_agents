import './questions.less'

import { optionIdSet } from '../types'

/**
 * 单选题（选项 + 自行填写）
 * @param {Object} props
 * @param {import('../types').AgentQuestion} props.question
 * @param {string} props.value
 * @param {(id: string) => void} props.onChange
 * @param {boolean} [props.disabled]
 */
export default function SingleChoice({ question, value, onChange, disabled = false }) {
  const options = question.options || []
  const optionIds = optionIdSet(options)
  const selectedOptionId = optionIds.has(value) ? value : ''
  const customText = selectedOptionId ? '' : typeof value === 'string' ? value : ''

  return (
    <fieldset className="gb-question gb-single" disabled={disabled}>
      <legend className="gb-question-label">{question.text}</legend>
      <div className="gb-options">
        {options.map((opt) => (
          <label key={opt.id} className={`gb-option ${selectedOptionId === opt.id ? 'selected' : ''}`}>
            <input
              type="radio"
              name={question.id}
              value={opt.id}
              checked={selectedOptionId === opt.id}
              onChange={() => onChange(opt.id)}
            />
            <span>{opt.label}</span>
          </label>
        ))}
      </div>
      <label className="gb-custom-input">
        <span className="gb-custom-label">或自行填写</span>
        <input
          type="text"
          value={customText}
          placeholder="输入您的回答"
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
        />
      </label>
    </fieldset>
  )
}
