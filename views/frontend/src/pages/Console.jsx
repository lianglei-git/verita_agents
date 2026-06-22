import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  createRun,
  executeInRun,
  fetchAgents,
  fetchRun,
  fetchRunContext,
  fetchRuns,
  fetchWorkflow,
} from '../api/client'
import AgentPanel from '../components/AgentPanel'
import AppShell from '../components/AppShell'
import ExecutionHistory from '../components/ExecutionHistory'
import Timeline from '../components/Timeline'
import '../App.less'

export default function Console() {
  const [agents, setAgents] = useState([])
  const [workflow, setWorkflow] = useState(null)
  const [activeAgentId, setActiveAgentId] = useState(null)
  const [userInput, setUserInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [showData, setShowData] = useState(false)

  const [runs, setRuns] = useState([])
  const [activeRunId, setActiveRunId] = useState(null)
  const [activeRun, setActiveRun] = useState(null)
  const [context, setContext] = useState(null)
  const [reviewMode, setReviewMode] = useState(false)
  const [liveRunId, setLiveRunId] = useState(null)

  const stepStatus = useMemo(() => {
    const status = {}
    if (!activeRun?.steps) return status
    Object.entries(activeRun.steps).forEach(([nodeId, step]) => {
      status[nodeId] = step.status || 'success'
    })
    return status
  }, [activeRun])

  const refreshRuns = useCallback(async () => {
    const data = await fetchRuns()
    setRuns(data.runs || [])
  }, [])

  const loadRunContext = useCallback(async (runId, agentId) => {
    if (!runId || !agentId) {
      setContext(null)
      return
    }
    const data = await fetchRunContext(runId, agentId)
    setContext(data)
  }, [])

  const loadRun = useCallback(
    async (runId, agentId = activeAgentId) => {
      const data = await fetchRun(runId)
      setActiveRun(data.run)
      setActiveRunId(runId)
      if (agentId) await loadRunContext(runId, agentId)
    },
    [activeAgentId, loadRunContext],
  )

  useEffect(() => {
    Promise.all([fetchAgents(), fetchWorkflow(), fetchRuns()])
      .then(([agentRes, workflowRes, runsRes]) => {
        setAgents(agentRes.agents || [])
        setWorkflow(workflowRes)
        setRuns(runsRes.runs || [])

        const path = workflowRes.execution_order || []
        const firstAgentNodeId = path.find((nodeId) => {
          const node = workflowRes.nodes.find((n) => n.id === nodeId)
          return node?.type === 'agent'
        })
        if (firstAgentNodeId) {
          const node = workflowRes.nodes.find((n) => n.id === firstAgentNodeId)
          setActiveAgentId(node.agent_id)
        }
      })
      .catch((err) => setError(err.message))
  }, [])

  useEffect(() => {
    if (activeRunId && activeAgentId) {
      loadRunContext(activeRunId, activeAgentId)
    }
  }, [activeAgentId, activeRunId, loadRunContext])

  const ensureLiveRun = async () => {
    if (liveRunId) {
      const data = await fetchRun(liveRunId)
      return data.run
    }
    const data = await createRun(userInput)
    const run = data.run
    setLiveRunId(run.id)
    setActiveRunId(run.id)
    setActiveRun(run)
    setReviewMode(false)
    await refreshRuns()
    return run
  }

  const handleAgentSelect = (agentId) => {
    setActiveAgentId(agentId)
    setError('')
  }

  const handleRun = async () => {
    if (!activeAgentId) return
    setLoading(true)
    setError('')
    try {
      const run = await ensureLiveRun()
      const inputToSend = userInput.trim() ? userInput : undefined
      const data = await executeInRun(run.id, activeAgentId, inputToSend)
      setActiveRun(data.run)
      setContext(data.context)
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
    setActiveRun(null)
    setContext(null)
    setError('')
    try {
      const data = await createRun(userInput)
      setLiveRunId(data.run.id)
      setActiveRunId(data.run.id)
      setActiveRun(data.run)
      await refreshRuns()
      if (activeAgentId) await loadRunContext(data.run.id, activeAgentId)
    } catch (err) {
      setError(err.message)
    }
  }

  const handleSelectRun = async (runId) => {
    setReviewMode(runId !== liveRunId)
    setError('')
    try {
      await loadRun(runId, activeAgentId)
    } catch (err) {
      setError(err.message)
    }
  }

  const handleExitReview = async () => {
    setReviewMode(false)
    if (liveRunId) {
      await loadRun(liveRunId, activeAgentId)
    } else {
      setActiveRunId(null)
      setActiveRun(null)
      setContext(null)
    }
  }

  const activeAgent = agents.find((a) => a.id === activeAgentId)
  const viewResult = context?.current?.result ? { result: context.current.result } : null

  return (
    <AppShell
      eyebrow="Verita · Pipeline"
      title="流水线调试台"
      description="沿执行顺序运行 Agent，查看上下游参数与结果，回顾每次运行记录。"
      actions={(
        <button
          type="button"
          className="ghost-btn"
          onClick={() => setShowData((v) => !v)}
        >
          {showData ? '收起原始数据' : '查看原始数据'}
        </button>
      )}
    >
      {error && <div className="error-banner">{error}</div>}

      <Timeline
        workflow={workflow}
        activeAgentId={activeAgentId}
        stepStatus={stepStatus}
        onAgentSelect={handleAgentSelect}
      />

      <div className="workspace">
        <ExecutionHistory
          runs={runs}
          activeRunId={activeRunId}
          reviewMode={reviewMode}
          onSelectRun={handleSelectRun}
          onNewRun={handleNewRun}
          onExitReview={handleExitReview}
        />

        <AgentPanel
          agent={activeAgent}
          context={context}
          userInput={userInput}
          onInputChange={setUserInput}
          onRun={handleRun}
          loading={loading}
          reviewMode={reviewMode}
          activeRunId={activeRunId}
          viewResult={viewResult}
        />
      </div>

      {showData && (
        <section className="data-panel">
          <h3>原始数据</h3>
          <div className="data-grid">
            <pre>{JSON.stringify(workflow, null, 2)}</pre>
            <pre>{JSON.stringify({ activeRun, context, runs }, null, 2)}</pre>
          </div>
        </section>
      )}
    </AppShell>
  )
}
