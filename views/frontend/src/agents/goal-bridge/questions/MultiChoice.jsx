import './questions.less'

import { optionIdSet } from '../types'

/**
 * 多选题（选项 + 自行填写）
 * @param {Object} props
 * @param {import('../types').AgentQuestion} props.question
 * @param {string[]} props.value
 * @param {(ids: string[]) => void} props.onChange
 * @param {boolean} [props.disabled]
 */
export default function MultiChoice({ question, value, onChange, disabled = false }) {
  const options = question.options || []
  const optionIds = optionIdSet(options)
  const selected = new Set((value || []).filter((v) => optionIds.has(v)))
  const customText = (value || []).find((v) => !optionIds.has(v)) || ''

  const toggle = (id) => {
    const next = new Set(selected)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    const merged = [...next]
    if (customText.trim()) merged.push(customText.trim())
    onChange(merged)
  }

  const setCustom = (text) => {
    const merged = [...selected]
    if (text.trim()) merged.push(text.trim())
    onChange(merged)
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
      <label className="gb-custom-input">
        <span className="gb-custom-label">或自行填写</span>
        <input
          type="text"
          value={customText}
          placeholder="输入您的回答（可与上方选项同时填写）"
          onChange={(e) => setCustom(e.target.value)}
          disabled={disabled}
        />
      </label>
    </fieldset>
  )
}
