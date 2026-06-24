import './Timeline.less'

export default function Timeline({
  workflow,
  activeNodeId,
  stepStatus = {},
  registeredAgentIds = [],
  onNodeSelect,
}) {
  if (!workflow) return null

  const { execution_order: path = [], nodes = [] } = workflow
  const nodeMap = Object.fromEntries(nodes.map((n) => [n.id, n]))

  return (
    <section className="timeline-section" aria-label="执行顺序">
      <div className="timeline-header">
        <div className="timeline-title">
          <span className="label">Pipeline</span>
          <span className="title">执行顺序</span>
        </div>
        <span className="hint">从步骤 1 输入开始 · 点击节点查看 I/O · 青绿为已完成</span>
      </div>

      <div className="timeline-conduit">
        <div className="signal-rail" aria-hidden="true" />
        <div className="timeline-path">
          {path.map((nodeId, index) => {
            const node = nodeMap[nodeId]
            if (!node) return null
            const isAgent = node.type === 'agent'
            const isSource = node.type === 'source'
            const isPlanned = node.status === 'planned'
            const isAvailable =
              isSource ||
              (isAgent &&
                !isPlanned &&
                (registeredAgentIds.length === 0 || registeredAgentIds.includes(node.agent_id)))
            const isActive = nodeId === activeNodeId
            const status = stepStatus[nodeId] || 'pending'
            const done = status === 'success'
            return (
              <div key={nodeId} className="timeline-step">
                {index > 0 && (
                  <span className={`conduit-segment ${done ? 'lit' : ''}`} aria-hidden="true" />
                )}
                <button
                  type="button"
                  className={`node ${node.type} ${isActive ? 'active' : ''} status-${status} ${!isAvailable ? 'unavailable' : ''}`}
                  disabled={!isAvailable}
                  onClick={() => isAvailable && onNodeSelect(nodeId)}
                >
                  <span className="step-index">{index + 1}</span>
                  <span className="node-text">
                    <span className="node-label">{node.label}</span>
                    {isAgent && <span className="node-id">{node.agent_id}</span>}
                    {isSource && <span className="node-id">source</span>}
                  </span>
                  {done && <span className="flow-dot" title="已完成" />}
                </button>
              </div>
            )
          })}
        </div>
      </div>
    </section>
  )
}
