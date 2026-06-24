import OpenQuestion from './questions/OpenQuestion'
import SingleChoice from './questions/SingleChoice'
import MultiChoice from './questions/MultiChoice'

/**
 * 按 AgentQuestion.type 渲染对应题型组件
 * @param {Object} props
 * @param {import('./types').AgentQuestion} props.question
 * @param {string|string[]} props.value
 * @param {(v: string|string[]) => void} props.onChange
 * @param {boolean} [props.disabled]
 */
export default function QuestionRenderer({ question, value, onChange, disabled = false }) {
  if (!question) return null

  switch (question.type) {
    case 'single':
      return (
        <SingleChoice
          question={question}
          value={typeof value === 'string' ? value : ''}
          onChange={onChange}
          disabled={disabled}
        />
      )
    case 'multi':
      return (
        <MultiChoice
          question={question}
          value={Array.isArray(value) ? value : []}
          onChange={onChange}
          disabled={disabled}
        />
      )
    case 'open':
    default:
      return (
        <OpenQuestion
          question={question}
          value={typeof value === 'string' ? value : ''}
          onChange={onChange}
          disabled={disabled}
        />
      )
  }
}
