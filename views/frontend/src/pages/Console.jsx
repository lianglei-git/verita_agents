import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  createRun,
  executeInRun,
  fetchAgents,
  fetchRun,
  fetchRunContext,
  fetchRuns,
  fetchWorkflow,
  fetchWorkflows,
  updateRunInput,
} from '../api/client'
import { freshInputForAgent, isSelfManagedAgent } from '../agents/freshInput'
import AgentPanel from '../components/AgentPanel'
import AppShell from '../components/AppShell'
import ExecutionHistory from '../components/ExecutionHistory'
import InputPanel from '../components/InputPanel'
import Timeline from '../components/Timeline'
import WorkflowSwitcher from '../components/WorkflowSwitcher'
import '../App.less'

function nodeById(workflow, nodeId) {
  return workflow?.nodes?.find((n) => n.id === nodeId) || null
}

export default function Console() {
  const [agents, setAgents] = useState([])
  const [workflow, setWorkflow] = useState(null)
  const [workflowId, setWorkflowId] = useState('demo-pipeline')
  const [workflowOptions, setWorkflowOptions] = useState([])
  const [activeNodeId, setActiveNodeId] = useState(null)
  const [userInput, setUserInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const [runs, setRuns] = useState([])
  const [activeRunId, setActiveRunId] = useState(null)
  const [activeRun, setActiveRun] = useState(null)
  const [context, setContext] = useState(null)
  const [reviewMode, setReviewMode] = useState(false)
  const [liveRunId, setLiveRunId] = useState(null)

  const activeNode = useMemo(
    () => (workflow && activeNodeId ? nodeById(workflow, activeNodeId) : null),
    [workflow, activeNodeId],
  )
  const activeAgentId = activeNode?.type === 'agent' ? activeNode.agent_id : null
  const isInputNode = activeNode?.type === 'source'

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
      const run = data.run
      setActiveRun(run)
      setActiveRunId(runId)
      if (run?.source_input !== undefined) {
        setUserInput(run.source_input || '')
      }
      if (agentId) await loadRunContext(runId, agentId)
    },
    [activeAgentId, loadRunContext],
  )

  const loadWorkflow = useCallback(async (id) => {
    const workflowRes = await fetchWorkflow(id)
    setWorkflow(workflowRes)
    setWorkflowId(id)

    const path = workflowRes.execution_order || []
    setActiveNodeId(path[0] || null)
  }, [])

  useEffect(() => {
    Promise.all([fetchAgents(), fetchWorkflows(), fetchRuns()])
      .then(([agentRes, workflowsRes, runsRes]) => {
        setAgents(agentRes.agents || [])
        setWorkflowOptions(workflowsRes.workflows || [])
        setRuns(runsRes.runs || [])
        const defaultId = workflowsRes.default || 'demo-pipeline'
        return loadWorkflow(defaultId)
      })
      .catch((err) => setError(err.message))
  }, [loadWorkflow])

  const handleWorkflowChange = async (id) => {
    setError('')
    setUserInput('')
    setLiveRunId(null)
    setActiveRunId(null)
    setActiveRun(null)
    setContext(null)
    setReviewMode(false)
    try {
      await loadWorkflow(id)
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => {
    if (activeRunId && activeAgentId) {
      loadRunContext(activeRunId, activeAgentId)
    } else if (!activeAgentId) {
      setContext(null)
    }
  }, [activeAgentId, activeRunId, loadRunContext])

  const ensureLiveRun = async () => {
    if (liveRunId) {
      const data = await fetchRun(liveRunId)
      return data.run
    }
    const data = await createRun(userInput, workflowId)
    const run = data.run
    setLiveRunId(run.id)
    setActiveRunId(run.id)
    setActiveRun(run)
    setReviewMode(false)
    await refreshRuns()
    return run
  }

  const handleNodeSelect = (nodeId) => {
    setActiveNodeId(nodeId)
    setError('')
    const node = nodeById(workflow, nodeId)
    if (node?.type === 'agent' && activeRunId) {
      loadRunContext(activeRunId, node.agent_id)
    }
  }

  const handleSaveInput = async () => {
    setLoading(true)
    setError('')
    try {
      const run = await ensureLiveRun()
      const data = await updateRunInput(run.id, userInput)
      setActiveRun(data.run)
      await refreshRuns()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleRun = async (inputOverride) => {
    if (!activeAgentId) return
    setLoading(true)
    setError('')
    try {
      const run = await ensureLiveRun()
      if (userInput.trim() && run.source_input !== userInput) {
        const updated = await updateRunInput(run.id, userInput)
        setActiveRun(updated.run)
      }
      const raw = typeof inputOverride === 'string' ? inputOverride : userInput
      const inputToSend = raw?.trim() ? raw : undefined
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
    const freshInput = isSelfManagedAgent(activeAgentId)
      ? freshInputForAgent(activeAgentId)
      : ''
    setUserInput(freshInput)
    try {
      const data = await createRun(freshInput, workflowId)
      setLiveRunId(data.run.id)
      setActiveRunId(data.run.id)
      setActiveRun(data.run)
      await refreshRuns()
      const path = workflow?.execution_order || []
      setActiveNodeId(path[0] || null)
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
  const registeredAgentIds = agents.map((a) => a.id)
  const workflowDisplayName = workflow?.name || workflowId

  return (
    <AppShell
      eyebrow="Verita · Pipeline"
      title="流水线调试台"
      description="从用户输入开始，沿执行顺序运行各 Agent，上下游 I/O 始终可见。"
    >
      {error && <div className="error-banner">{error}</div>}

      <WorkflowSwitcher
        workflows={workflowOptions}
        activeId={workflowId}
        onChange={handleWorkflowChange}
      />

      <Timeline
        workflow={workflow}
        activeNodeId={activeNodeId}
        stepStatus={stepStatus}
        registeredAgentIds={registeredAgentIds}
        onNodeSelect={handleNodeSelect}
      />

      <div className="workspace">
        <ExecutionHistory
          mode="pipeline"
          workflowName={workflowDisplayName}
          workflowFilter={workflowDisplayName}
          runs={runs}
          activeRunId={activeRunId}
          reviewMode={reviewMode}
          onSelectRun={handleSelectRun}
          onNewRun={handleNewRun}
          onExitReview={handleExitReview}
        />

        {isInputNode ? (
          <InputPanel
            node={activeNode}
            userInput={userInput}
            onInputChange={setUserInput}
            onSave={handleSaveInput}
            loading={loading}
            reviewMode={reviewMode}
            activeRun={activeRun}
            activeRunId={activeRunId}
          />
        ) : (
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
        )}
      </div>
    </AppShell>
  )
}
