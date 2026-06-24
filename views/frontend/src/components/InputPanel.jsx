import StepDataBlock from './StepDataBlock'
import './InputPanel.less'

export default function InputPanel({
  node,
  userInput,
  onInputChange,
  onSave,
  loading,
  reviewMode,
  activeRun,
  activeRunId,
}) {
  const inputStep = activeRun?.steps?.input

  return (
    <section className="input-panel">
      <header>
        <div>
          <h2>{node?.label || '用户输入'}</h2>
          <p>流水线起点：在此填写原始输入，后续 Agent 将从此处或上游节点获取数据。</p>
        </div>
        {activeRunId && <span className="run-badge">#{activeRunId}</span>}
      </header>

      <div className="io-grid single">
        <StepDataBlock
          title={node?.label || '输入节点'}
          params={inputStep?.params}
          result={inputStep?.result}
          status={inputStep?.status || (userInput.trim() ? 'success' : 'pending')}
          ranAt={inputStep?.ran_at}
        />
      </div>

      {!reviewMode && (
        <div className="input-editor">
          <label>
            <span>原始输入</span>
            <textarea
              rows={6}
              value={userInput}
              placeholder="填写本流水线要处理的原始内容，例如个人故事、目标描述…"
              onChange={(e) => onInputChange(e.target.value)}
            />
          </label>
          <button type="button" className="run-btn" onClick={onSave} disabled={loading}>
            {loading ? '保存中…' : '保存到本次运行'}
          </button>
        </div>
      )}

      {reviewMode && (
        <p className="review-hint">正在回顾历史运行。返回当前后可继续编辑输入。</p>
      )}
    </section>
  )
}
