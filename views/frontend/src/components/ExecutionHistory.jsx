import './ExecutionHistory.less'

function formatTime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString()
}

export default function ExecutionHistory({
  runs,
  activeRunId,
  reviewMode,
  onSelectRun,
  onNewRun,
  onExitReview,
}) {
  return (
    <aside className="execution-history">
      <div className="history-header">
        <h2>运行记录</h2>
        <button type="button" className="new-run-btn" onClick={onNewRun}>
          新建
        </button>
      </div>

      {reviewMode && activeRunId && (
        <div className="review-banner">
          正在回顾
          <button type="button" onClick={onExitReview}>
            返回当前
          </button>
        </div>
      )}

      {runs.length === 0 ? (
        <p className="empty">尚无运行记录。运行任意节点后将自动保存。</p>
      ) : (
        <ul>
          {runs.map((run) => (
            <li key={run.id}>
              <button
                type="button"
                className={run.id === activeRunId ? 'active' : ''}
                onClick={() => onSelectRun(run.id)}
              >
                <span className="run-id">#{run.id}</span>
                <span className="run-meta">
                  {formatTime(run.created_at)} · {run.step_count} 步 · {run.status}
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
