import './ExecutionHistory.less'

function formatTime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString()
}

const STATUS_LABELS = {
  in_progress: '进行中',
  completed: '已完成',
}

export default function ExecutionHistory({
  runs,
  activeRunId,
  reviewMode,
  onSelectRun,
  onNewRun,
  onExitReview,
  mode = 'standalone',
  workflowName,
  workflowFilter,
}) {
  const isPipeline = mode === 'pipeline'
  const filteredRuns = isPipeline && workflowFilter
    ? runs.filter((run) => run.workflow_name === workflowFilter)
    : runs

  return (
    <aside className={`execution-history mode-${mode}`}>
      <div className="history-header">
        <div>
          <h2>{isPipeline ? '流水线运行' : '调试会话'}</h2>
          <p className="history-desc">
            {isPipeline
              ? `整条 ${workflowName || workflowFilter || 'Workflow'} 的执行记录，含各节点 I/O`
              : '当前 Agent 的独立调试历史'}
          </p>
        </div>
        <button type="button" className="new-run-btn" onClick={onNewRun}>
          {isPipeline ? '新运行' : '新建'}
        </button>
      </div>

      {reviewMode && activeRunId && (
        <div className="review-banner">
          正在回顾本次流水线运行
          <button type="button" onClick={onExitReview}>
            返回当前
          </button>
        </div>
      )}

      {filteredRuns.length === 0 ? (
        <p className="empty">
          {isPipeline
            ? '尚无该流水线的运行记录。从步骤 1 填写输入后，依次运行各 Agent 节点。'
            : '尚无运行记录。运行后将自动保存。'}
        </p>
      ) : (
        <ul>
          {filteredRuns.map((run) => (
            <li key={run.id}>
              <button
                type="button"
                className={run.id === activeRunId ? 'active' : ''}
                onClick={() => onSelectRun(run.id)}
              >
                <span className="run-id">#{run.id}</span>
                <span className="run-meta">
                  {isPipeline && run.workflow_name && (
                    <em className="wf-tag">{run.workflow_name}</em>
                  )}
                  {formatTime(run.created_at)} · {run.step_count} 步 ·{' '}
                  {STATUS_LABELS[run.status] || run.status}
                </span>
                <span className="run-preview">{run.source_input || '(空输入)'}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </aside>
  )
}
