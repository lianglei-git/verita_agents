import './GoalBridgeView.less'

import { useEffect, useRef, useState } from 'react'
import { gbLog } from './debug'
import QuestionRenderer from './QuestionRenderer'
import SurveyPanel from './SurveyPanel'
import {
  STEP_LABELS,
  UI_MODES,
  buildAnswer,
  buildPartialBatch,
  getStepState,
  isAnswerValid,
  normalizeQuestion,
  parseInput,
} from './types'

function TurnLog({ turns }) {
  if (!turns?.length) return null
  return (
    <div className="turn-log">
      <h4>对话记录</h4>
      <ul>
        {turns.map((t, i) => (
          <li key={i}>
            <p className="user-line">
              <span>你</span> {t.user || '（开始）'}
            </p>
            <p className="bot-line">
              <span>AI</span> {t.assistant}
            </p>
          </li>
        ))}
      </ul>
    </div>
  )
}

function GoalBanner({ goal }) {
  if (!goal) return null
  return (
    <p className="goal-banner">
      已确认目标：<strong>{goal}</strong>
    </p>
  )
}

function StepDoneCard({ step, session }) {
  if (step === 1) {
    const goal = session?.step1?.goal_text
    if (!goal) return null
    return (
      <div className="step-done-card">
        <h4>步骤 1 完成</h4>
        <p>
          已确认目标：<strong>{goal}</strong>
        </p>
      </div>
    )
  }
  if (step === 2) {
    const data = session?.step2?.data
    const goal = session?.step2?.goal_text || session?.step1?.goal_text
    return (
      <div className="step-done-card">
        <h4>步骤 2 完成</h4>
        <p>目标：<strong>{goal}</strong></p>
        {data && Object.keys(data).length > 0 && (
          <dl className="collected-info">
            {Object.entries(data).map(([k, v]) => (
              <div key={k}>
                <dt>{k}</dt>
                <dd>{typeof v === 'string' ? v : JSON.stringify(v)}</dd>
              </div>
            ))}
          </dl>
        )}
        <p className="muted">步骤 3「差距评估」尚未实现。</p>
      </div>
    )
  }
  return null
}

function LlmDebugPanel({ calls }) {
  if (!calls?.length) return null
  return (
    <aside className="llm-debug-panel">
      <h4>AI 调用记录（本轮）</h4>
      <p className="llm-debug-hint">
        每次提交给 AI 前会先合并用户画像；下方为本次请求中每次调用的输入与输出。
      </p>
      <ul>
        {calls.map((call, i) => (
          <li key={`${call.label}-${i}`}>
            <details>
              <summary>
                <span className="llm-label">{call.label || `调用 ${i + 1}`}</span>
                {call.error && <span className="llm-error-tag">失败</span>}
              </summary>
              <div className="llm-call-body">
                <details open>
                  <summary>System</summary>
                  <pre>{call.system || '（无）'}</pre>
                </details>
                <details open>
                  <summary>Prompt（输入）</summary>
                  <pre>{call.prompt || '（无）'}</pre>
                </details>
                {call.error ? (
                  <p className="llm-error">{call.error}</p>
                ) : (
                  <details open>
                    <summary>Response（输出）</summary>
                    <pre>
                      {call.response != null
                        ? JSON.stringify(call.response, null, 2)
                        : '（无）'}
                    </pre>
                  </details>
                )}
              </div>
            </details>
          </li>
        ))}
      </ul>
    </aside>
  )
}

function UserProfilePanel({ profile }) {
  const summary = profile?.summary?.trim()
  const structured = profile?.structured || {}
  const keys = Object.keys(structured)
  if (!summary && keys.length === 0) {
    return (
      <aside className="user-profile-panel">
        <h4>已了解到的信息</h4>
        <p className="profile-empty">每次答完题、提交给 AI 前会合并画像；AI 返回后会再精炼，并显示在这里。</p>
      </aside>
    )
  }
  return (
    <aside className="user-profile-panel">
      <h4>已了解到的信息</h4>
      {summary && <p className="profile-summary">{summary}</p>}
      {keys.length > 0 && (
        <dl className="profile-facts">
          {keys.map((k) => (
            <div key={k}>
              <dt>{k}</dt>
              <dd>
                {typeof structured[k] === 'string'
                  ? structured[k]
                  : JSON.stringify(structured[k])}
              </dd>
            </div>
          ))}
        </dl>
      )}
    </aside>
  )
}

function ProgressBar({ progress }) {
  if (!progress?.total) return null
  return (
    <p className="progress-bar">
      答题进度 {progress.answered}/{progress.total}
    </p>
  )
}

export default function GoalBridgeView({
  mode,
  userInput,
  onInputChange,
  onRun,
  loading = false,
  result,
  reviewMode,
}) {
  const [payload, setPayload] = useState(() => parseInput(userInput))
  const [draftValue, setDraftValue] = useState('')

  useEffect(() => {
    setPayload(parseInput(userInput))
  }, [userInput])

  const runResult = result?.result || null
  const session = runResult?.session ?? payload.session ?? null
  const step = runResult?.current_step || session?.current_step || 1
  const stepComplete = runResult?.step_complete === true
  const stepLabel = STEP_LABELS[step] || `步骤 ${step}`

  const stepState = getStepState(session, step, runResult)
  const {
    uiMode,
    pendingQuestions,
    answers,
    goal,
    showIntro,
  } = stepState

  const activeQuestion = normalizeQuestion(
    runResult?.active_question || runResult?.next_question,
  )
  const progress = runResult?.question_progress
  const requiredPending = pendingQuestions.filter((q) => q.required !== false)
  const allQuestionsAnswered =
    requiredPending.length > 0 &&
    requiredPending.every((q) => answers[q.id] != null)
  const awaitingRejudge =
    step === 1 &&
    !stepComplete &&
    pendingQuestions.length > 0 &&
    allQuestionsAnswered &&
    !activeQuestion
  const step2NeedsPlan =
    step === 2 &&
    !stepComplete &&
    !pendingQuestions.length &&
    session?.step2?.sufficiency !== 'enough'

  const userProfile = runResult?.user_profile || session?.user_profile
  const llmCalls = runResult?.llm_calls || []
  const canFinishHere =
    !stepComplete &&
    !showIntro &&
    (step === 1 || step === 2) &&
    (pendingQuestions.length > 0 ||
      userProfile?.summary ||
      (session?.turns?.length || 0) > 0)
  const step2PlanKey = `${session?.step2?.goal_text || ''}|${session?.turns?.length || 0}`
  const step2BootstrapRef = useRef(null)
  const rejudgeAttemptRef = useRef(null)

  useEffect(() => {
    const r = result?.result
    if (!r) return
    gbLog('view.result ◀', {
      turn_source: r.meta?.turn_source,
      reply: r.reply,
      current_step: r.current_step,
      step_complete: r.step_complete,
      ui_mode: r.ui_mode,
      session: r.session,
    })
    setPayload({ message: '', answer: null, session: r.session || payload.session })
    onInputChange(
      JSON.stringify({ message: '', answer: null, session: r.session || payload.session }),
    )
    setDraftValue('')
  }, [result])

  useEffect(() => {
    setDraftValue(activeQuestion?.type === 'multi' ? [] : '')
  }, [activeQuestion?.id])

  const commit = (nextPayload) => {
    if (loading || !onRun) return
    gbLog('view.commit ▶', { payload: nextPayload })
    onInputChange(JSON.stringify(nextPayload))
    setPayload(nextPayload)
    onRun(JSON.stringify(nextPayload))
  }

  const startFresh = () => {
    rejudgeAttemptRef.current = null
    step2BootstrapRef.current = null
    commit({ reset: true })
  }
  const submitIntro = () => {
    if (!payload.message?.trim()) return
    commit({ message: payload.message.trim(), session: session || payload.session })
  }
  const submitAnswer = () => {
    if (!activeQuestion) return
    const answer = buildAnswer(activeQuestion, draftValue)
    if (!isAnswerValid(answer)) return
    commit({ answer, session: session || payload.session })
  }
  const submitBatch = (answersBatch) => {
    commit({ answers_batch: answersBatch, session: session || payload.session })
  }
  const submitRejudge = () => {
    commit({ session: session || payload.session })
  }
  const submitFinishHere = (answersBatch) => {
    const next = { confirm_step: true, session: session || payload.session }
    if (answersBatch?.length) next.answers_batch = answersBatch
    commit(next)
  }
  const submitFinishHereSequential = () => {
    const batch = []
    if (activeQuestion && isAnswerValid(buildAnswer(activeQuestion, draftValue))) {
      batch.push(buildAnswer(activeQuestion, draftValue))
    }
    submitFinishHere(batch.length ? batch : undefined)
  }

  useEffect(() => {
    if (!awaitingRejudge || loading || !onRun) return
    const key = JSON.stringify({
      ids: pendingQuestions.map((q) => q.id),
      answers,
    })
    if (rejudgeAttemptRef.current === key) return
    rejudgeAttemptRef.current = key
    commit({ session: session || payload.session })
  }, [awaitingRejudge, loading, onRun, pendingQuestions, answers, session, payload.session])

  useEffect(() => {
    if (!step2NeedsPlan || loading || !onRun) return
    if (step2BootstrapRef.current === step2PlanKey) return
    step2BootstrapRef.current = step2PlanKey
    commit({ session: session || payload.session })
  }, [step2NeedsPlan, loading, onRun, session, payload.session, step2PlanKey])

  const step2PlanFailed =
    step === 2 &&
    step2NeedsPlan &&
    !loading &&
    (runResult?.meta?.turn_source === 'error' ||
      (runResult?.meta?.turn_source === 'plan' && !pendingQuestions.length))

  const retryStep2Plan = () => {
    step2BootstrapRef.current = null
    commit({ session: session || payload.session })
  }

  const errorReply =
    runResult?.meta?.turn_source === 'error' && runResult?.reply ? runResult.reply : null

  if (reviewMode) {
    return (
      <div className={`goal-bridge-view mode-${mode} review`}>
        {session?.step1?.clarity === 'clear' && <StepDoneCard step={1} session={session} />}
        {session?.step2?.sufficiency === 'enough' && <StepDoneCard step={2} session={session} />}
        <TurnLog turns={session?.turns} />
      </div>
    )
  }

  return (
    <div className={`goal-bridge-view mode-${mode}`}>
      <div className="state-badge">
        <span className="state-label">步骤 {step} · {stepLabel}</span>
        <span className="mode-hint">
          {uiMode === UI_MODES.SURVEY ? '问卷模式' : '逐题模式'}
        </span>
        {runResult?.meta?.llm_available === false && (
          <span className="fallback-hint">需配置 LLM</span>
        )}
      </div>

      {step >= 2 && goal && <GoalBanner goal={goal} />}

      <UserProfilePanel profile={userProfile} />
      <LlmDebugPanel calls={llmCalls} />

      {errorReply && !awaitingRejudge && !step2NeedsPlan && (
        <p className="error-hint" role="alert">{errorReply}</p>
      )}

      {step === 1 && showIntro && (
        <div className="intro-block">
          <p>步骤 1：说出您的目标，AI 会判断是否需要追问（可一次抛出多道题）。</p>
          <label>
            <span>您的目标</span>
            <textarea
              rows={mode === 'standalone' ? 5 : 4}
              value={payload.message || ''}
              placeholder="例：股票年化收益 20%；雅思 7.5 分"
              onChange={(e) => setPayload({ ...payload, message: e.target.value })}
              disabled={loading}
            />
          </label>
          <div className="actions">
            <button
              type="button"
              className="primary-btn"
              onClick={submitIntro}
              disabled={!payload.message?.trim() || loading}
            >
              {loading ? '处理中…' : '开始'}
            </button>
            <button type="button" className="ghost-btn" onClick={startFresh} disabled={loading}>
              重新开始
            </button>
          </div>
        </div>
      )}

      {step === 1 &&
        !showIntro &&
        !stepComplete &&
        uiMode === UI_MODES.SEQUENTIAL &&
        activeQuestion && (
          <div className="question-block">
            <ProgressBar progress={progress} />
            {runResult?.reply && <p className="question-hint">{runResult.reply}</p>}
            <QuestionRenderer
              question={activeQuestion}
              value={draftValue}
              onChange={setDraftValue}
              disabled={loading}
            />
            <div className="actions">
              <button
                type="button"
                className="primary-btn"
                onClick={submitAnswer}
                disabled={loading || !isAnswerValid(buildAnswer(activeQuestion, draftValue))}
              >
                {loading ? '处理中…' : '下一题'}
              </button>
              {canFinishHere && (
                <button
                  type="button"
                  className="ghost-btn finish-here-btn"
                  onClick={submitFinishHereSequential}
                  disabled={loading}
                >
                  就这样
                </button>
              )}
              <button type="button" className="ghost-btn" onClick={startFresh} disabled={loading}>
                重新开始
              </button>
            </div>
          </div>
        )}

      {step === 1 && !showIntro && !stepComplete && awaitingRejudge && (
        <div className="question-block rejudge-block">
          <ProgressBar
            progress={
              progress || { answered: requiredPending.length, total: requiredPending.length }
            }
          />
          <p className="question-hint">
            {runResult?.reply || '全部题目已答完，正在提交 AI 重新评估…'}
          </p>
          <div className="actions">
            <button
              type="button"
              className="primary-btn"
              onClick={submitRejudge}
              disabled={loading}
            >
              {loading ? '评估中…' : '提交评估'}
            </button>
            {canFinishHere && (
              <button
                type="button"
                className="ghost-btn finish-here-btn"
                onClick={() => submitFinishHere()}
                disabled={loading}
              >
                就这样
              </button>
            )}
            <button type="button" className="ghost-btn" onClick={startFresh} disabled={loading}>
              重新开始
            </button>
          </div>
        </div>
      )}

      {((step === 1 && !showIntro && !stepComplete && uiMode === UI_MODES.SURVEY) ||
        (step === 2 && !stepComplete)) &&
        pendingQuestions.length > 0 && (
          <SurveyPanel
            questions={pendingQuestions}
            reply={runResult?.reply}
            loading={loading}
            onSubmitBatch={submitBatch}
            onFinishHere={canFinishHere ? submitFinishHere : undefined}
            onReset={startFresh}
          />
        )}

      {step === 2 && step2NeedsPlan && loading && (
        <p className="question-hint">正在根据您的目标生成问卷…</p>
      )}

      {step2PlanFailed && (
        <div className="question-block rejudge-block">
          <p className="error-hint" role="alert">
            {errorReply || '问卷生成失败，AI 未返回有效题目。'}
          </p>
          <div className="actions">
            <button
              type="button"
              className="primary-btn"
              onClick={retryStep2Plan}
              disabled={loading}
            >
              {loading ? '生成中…' : '重新生成问卷'}
            </button>
            <button type="button" className="ghost-btn" onClick={startFresh} disabled={loading}>
              重新开始
            </button>
          </div>
        </div>
      )}

      {stepComplete && <StepDoneCard step={step} session={session} />}
      <TurnLog turns={session?.turns} />
    </div>
  )
}
