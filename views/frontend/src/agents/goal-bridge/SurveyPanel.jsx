import { useState } from 'react'
import { gbLog } from './debug'
import QuestionRenderer from './QuestionRenderer'
import { buildAnswer, buildPartialBatch, isAnswerValid } from './types'

/**
 * 问卷模式：一次展示全部题目，答完后 answers_batch 提交重判
 * @param {Object} props
 * @param {import('./types').AgentQuestion[]} props.questions
 * @param {string} [props.reply]
 * @param {boolean} [props.loading]
 * @param {(batch: import('./types').AnswerPayload[]) => void} props.onSubmitBatch
 * @param {(batch: import('./types').AnswerPayload[]) => void} [props.onFinishHere]
 * @param {() => void} props.onReset
 */
export default function SurveyPanel({
  questions,
  reply,
  loading = false,
  onSubmitBatch,
  onFinishHere,
  onReset,
}) {
  const [drafts, setDrafts] = useState({})

  const draftFor = (q) => drafts[q.id] ?? (q.type === 'multi' ? [] : '')

  const buildBatch = () =>
    questions.map((q) => buildAnswer(q, draftFor(q))).filter(isAnswerValid)

  const canSubmit =
    questions.length > 0 &&
    questions
      .filter((q) => q.required !== false)
      .every((q) => isAnswerValid(buildAnswer(q, draftFor(q))))

  const handleFinishHere = () => {
    const batch = buildPartialBatch(questions, drafts)
    gbLog('survey.finish_here ▶', { answers_batch: batch })
    onFinishHere?.(batch)
  }

  return (
    <div className="survey-panel">
      {reply && <p className="question-hint">{reply}</p>}
      <ol className="survey-list">
        {questions.map((q, i) => (
          <li key={q.id}>
            <span className="survey-index">{i + 1}.</span>
            <QuestionRenderer
              question={q}
              value={draftFor(q)}
              onChange={(v) => setDrafts((prev) => ({ ...prev, [q.id]: v }))}
              disabled={loading}
            />
          </li>
        ))}
      </ol>
      <div className="actions">
        <button
          type="button"
          className="primary-btn"
          disabled={loading || !canSubmit}
          onClick={() => {
            const batch = buildBatch()
            gbLog('survey.submit ▶', { answers_batch: batch, question_ids: questions.map((q) => q.id) })
            onSubmitBatch(batch)
          }}
        >
          {loading ? '提交中…' : '提交全部回答'}
        </button>
        {onFinishHere && (
          <button
            type="button"
            className="ghost-btn finish-here-btn"
            disabled={loading}
            onClick={handleFinishHere}
          >
            就这样
          </button>
        )}
        <button type="button" className="ghost-btn" onClick={onReset} disabled={loading}>
          重新开始
        </button>
      </div>
    </div>
  )
}
