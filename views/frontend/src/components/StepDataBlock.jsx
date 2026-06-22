import './StepDataBlock.less'

function formatValue(value) {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'string') return value
  return JSON.stringify(value, null, 2)
}

export default function StepDataBlock({ title, params, result, status = 'pending', ranAt }) {
  const hasData = params || result

  return (
    <div className={`step-data-block status-${status}`}>
      <div className="step-data-header">
        <h4>{title}</h4>
        {status !== 'pending' && (
          <span className={`status-tag ${status}`}>
            {status === 'success' ? '已完成' : status}
          </span>
        )}
      </div>

      {!hasData ? (
        <p className="empty">等待执行</p>
      ) : (
        <>
          <div className="data-section">
            <span className="data-label">参数</span>
            <pre>{formatValue(params)}</pre>
          </div>
          <div className="data-section">
            <span className="data-label">结果</span>
            <pre>{formatValue(result)}</pre>
          </div>
          {ranAt && <span className="ran-at">{new Date(ranAt).toLocaleString()}</span>}
        </>
      )}
    </div>
  )
}
