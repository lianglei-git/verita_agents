import './WorkflowSwitcher.less'

export default function WorkflowSwitcher({ workflows, activeId, onChange }) {
  if (!workflows?.length) return null

  const active = workflows.find((w) => w.id === activeId)

  return (
    <div className="workflow-switcher">
      <label htmlFor="workflow-select">工作流</label>
      <select
        id="workflow-select"
        value={activeId}
        onChange={(e) => onChange(e.target.value)}
      >
        {workflows.map((wf) => (
          <option key={wf.id} value={wf.id}>
            {wf.name}
          </option>
        ))}
      </select>
      {active?.description && (
        <p className="workflow-desc">{active.description}</p>
      )}
    </div>
  )
}
