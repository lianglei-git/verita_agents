import { Link } from 'react-router-dom'
import StepDataBlock from './StepDataBlock'
import AgentViewResolver from '../agents/AgentViewResolver'
import './AgentPanel.less'

export default function AgentPanel({
  agent,
  context,
  userInput,
  onInputChange,
  onRun,
  loading,
  reviewMode,
  activeRunId,
  viewResult,
}) {
  if (!agent) {
    return (
      <section className="agent-panel empty">
        <p>从执行顺序中选择一个 Agent 节点</p>
      </section>
    )
  }

  const { upstream = [], downstream = [], current = null } = context || {}
  const selfManagedRun = agent?.id === 'user-profile' || agent?.id === 'goal-bridge'

  return (
    <section className="agent-panel">
      <header>
        <div>
          <h2>{agent.name}</h2>
          <p>{agent.description}</p>
        </div>
        <div className="header-badges">
          {activeRunId && <span className="run-badge">#{activeRunId}</span>}
          <Link to={`/agent/${agent.id}`} className="workbench-link" title="在独立工作台打开">
            独立调试
          </Link>
          <span className="agent-badge">{agent.id}</span>
        </div>
      </header>

      <div className="io-grid">
        <section className="io-column">
          <h3>上游输入</h3>
          {upstream.length === 0 ? (
            <p className="muted">无上游节点</p>
          ) : (
            upstream.map((step) => (
              <StepDataBlock
                key={step.node_id}
                title={step.label}
                params={step.params}
                result={step.result}
                status={step.status}
                ranAt={step.ran_at}
              />
            ))
          )}
        </section>

        <section className="io-column current">
          <h3>当前节点</h3>
          <StepDataBlock
            title={current?.label || agent.name}
            params={current?.params}
            result={current?.result}
            status={current?.status || 'pending'}
            ranAt={current?.ran_at}
          />
        </section>

        <section className="io-column">
          <h3>下游输出</h3>
          {downstream.length === 0 ? (
            <p className="muted">无下游节点</p>
          ) : (
            downstream.map((step) => (
              <StepDataBlock
                key={step.node_id}
                title={step.label}
                params={step.params}
                result={step.result}
                status={step.status}
                ranAt={step.ran_at}
              />
            ))
          )}
        </section>
      </div>

      <div className="agent-input-section">
        <AgentViewResolver
          agent={agent}
          mode="embedded"
          sessionKey={activeRunId}
          userInput={userInput}
          onInputChange={onInputChange}
          onRun={onRun}
          loading={loading}
          result={viewResult}
          reviewMode={reviewMode}
        />

        {!reviewMode && !selfManagedRun && (
          <button type="button" className="run-btn" onClick={onRun} disabled={loading}>
            {loading ? '运行中…' : '运行'}
          </button>
        )}
      </div>

      {reviewMode && (
        <p className="review-hint">正在回顾历史运行。返回当前执行后可继续运行节点。</p>
      )}
    </section>
  )
}
