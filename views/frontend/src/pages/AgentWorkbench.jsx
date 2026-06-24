import { Link, useParams } from 'react-router-dom'
import { useCallback, useEffect, useState } from 'react'
import {
  createRun,
  fetchAgent,
  fetchRun,
  fetchRuns,
  runAgent,
} from '../api/client'
import { freshInputForAgent } from '../agents/freshInput'
import AgentViewResolver from '../agents/AgentViewResolver'
import AppShell from '../components/AppShell'
import '../components/AppShell.less'
import ExecutionHistory from '../components/ExecutionHistory'
import '../components/ExecutionHistory.less'
import './AgentWorkbench.less'

export default function AgentWorkbench() {
  const { id: agentId } = useParams()
  const [agent, setAgent] = useState(null)
  const [userInput, setUserInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [lastResult, setLastResult] = useState(null)

  const [runs, setRuns] = useState([])
  const [activeRunId, setActiveRunId] = useState(null)
  const [reviewMode, setReviewMode] = useState(false)
  const [liveRunId, setLiveRunId] = useState(null)

  const refreshRuns = useCallback(async () => {
    const data = await fetchRuns()
    setRuns(data.runs || [])
  }, [])

  useEffect(() => {
    setUserInput('')
    setLastResult(null)
    setError('')
    fetchAgent(agentId)
      .then(setAgent)
      .catch((err) => setError(err.message))
    refreshRuns()
  }, [agentId, refreshRuns])

  const ensureLiveRun = async () => {
    if (liveRunId) {
      const data = await fetchRun(liveRunId)
      return data.run
    }
    const data = await createRun(userInput, undefined)
    setLiveRunId(data.run.id)
    setActiveRunId(data.run.id)
    setReviewMode(false)
    await refreshRuns()
    return data.run
  }

  const handleRun = async (inputOverride) => {
    if (!agent) return
    setLoading(true)
    setError('')
    try {
      const run = await ensureLiveRun()
      const raw = typeof inputOverride === 'string' ? inputOverride : userInput
      const inputToSend = raw?.trim() ? raw : undefined
      const data = await runAgent(agentId, inputToSend, {}, run.id)
      setLastResult(data)
      setActiveRunId(run.id)
      await refreshRuns()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleNewRun = async () => {
    setReviewMode(false)
    setLiveRunId(null)
    setActiveRunId(null)
    setLastResult(null)
    setError('')
    const freshInput = freshInputForAgent(agentId)
    setUserInput(freshInput)
    try {
      const data = await createRun(freshInput, undefined)
      setLiveRunId(data.run.id)
      setActiveRunId(data.run.id)
      await refreshRuns()
    } catch (err) {
      setError(err.message)
    }
  }

  const handleSelectRun = async (runId) => {
    setReviewMode(runId !== liveRunId)
    setActiveRunId(runId)
    setError('')
    try {
      const data = await fetchRun(runId)
      const step = data.run?.steps
      const agentStep = step
        ? Object.values(step).find((s) => s.agent_id === agentId)
        : null
      if (agentStep?.result) {
        setLastResult({ result: agentStep.result, input: agentStep.params?.input })
        if (agentStep.params?.input) setUserInput(agentStep.params.input)
      }
    } catch (err) {
      setError(err.message)
    }
  }

  const handleExitReview = () => {
    setReviewMode(false)
    if (liveRunId) {
      setActiveRunId(liveRunId)
    } else {
      setActiveRunId(null)
      setLastResult(null)
    }
  }

  if (!agent && !error) {
    return (
      <AppShell eyebrow="Verita · Workbench" title="加载中…" />
    )
  }

  if (!agent) {
    return (
      <AppShell eyebrow="Verita · Workbench" title="未找到 Agent">
        <div className="error-banner">{error || `Agent "${agentId}" 不存在`}</div>
        <Link to="/agents" className="back-link">返回列表</Link>
      </AppShell>
    )
  }

  return (
    <AppShell
      eyebrow="Verita · Workbench"
      title={agent.name}
      description={agent.description}
      actions={<Link to="/agents" className="ghost-btn">全部 Agent</Link>}
    >
      {error && <div className="error-banner">{error}</div>}

      <div className="workbench-layout">
        <ExecutionHistory
          mode="standalone"
          runs={runs}
          activeRunId={activeRunId}
          reviewMode={reviewMode}
          onSelectRun={handleSelectRun}
          onNewRun={handleNewRun}
          onExitReview={handleExitReview}
        />

        <section className="workbench-main">
          <header className="workbench-header">
            <span className="agent-badge">{agentId}</span>
            {agent.source && <span className="source">{agent.source}</span>}
          </header>

          <AgentViewResolver
            agent={agent}
            mode="standalone"
            sessionKey={activeRunId ?? 'new'}
            userInput={userInput}
            onInputChange={setUserInput}
            onRun={handleRun}
            loading={loading}
            result={lastResult}
            reviewMode={reviewMode}
          />

          {!reviewMode && agent.id !== 'user-profile' && agent.id !== 'goal-bridge' && (
            <button type="button" className="run-btn" onClick={() => handleRun()} disabled={loading}>
              {loading ? '运行中…' : '运行'}
            </button>
          )}

          {reviewMode && (
            <p className="review-hint">正在回顾历史运行。返回当前后可继续调试。</p>
          )}
        </section>
      </div>
    </AppShell>
  )
}
