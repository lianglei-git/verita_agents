import './StoryScenarioView.less'

import { useEffect, useState } from 'react'
import {
  ARCHETYPE_LABELS,
  buildRunPayload,
  claimText,
  mergeRunResult,
  parseInput,
} from './types'

function ScenarioCard({ scenario, selected, onSelect, reviewMode }) {
  const archetype = scenario.archetype || 'balanced'
  const label = ARCHETYPE_LABELS[archetype] || archetype

  return (
    <button
      type="button"
      className={`scenario-card ${archetype} ${selected ? 'selected' : ''}`}
      onClick={() => !reviewMode && onSelect(scenario.id)}
      disabled={reviewMode}
    >
      <div className="card-head">
        <h4>{scenario.title}</h4>
        <span className="archetype-tag">{label}</span>
      </div>
      {scenario.tagline && <p className="tagline">{scenario.tagline}</p>}

      {(scenario.premises?.length ?? 0) > 0 && (
        <>
          <span className="section-label">前提</span>
          <ul>
            {scenario.premises.slice(0, 3).map((p, i) => (
              <li key={i}>{claimText(p)}</li>
            ))}
          </ul>
        </>
      )}

      {(scenario.opportunity_costs?.length ?? 0) > 0 && (
        <>
          <span className="section-label">机会成本</span>
          <ul>
            {scenario.opportunity_costs.slice(0, 2).map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </>
      )}

      {(scenario.failure_modes?.length ?? 0) > 0 && (
        <>
          <span className="section-label">失败模式</span>
          <ul>
            {scenario.failure_modes.slice(0, 2).map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
        </>
      )}

      {(scenario.reversible_actions?.length ?? 0) > 0 && (
        <>
          <span className="section-label">可逆操作</span>
          <ul>
            {scenario.reversible_actions.slice(0, 2).map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </>
      )}

      {scenario.confidence_notes && (
        <p className="confidence">{scenario.confidence_notes}</p>
      )}
    </button>
  )
}

export default function StoryScenarioView({
  mode,
  userInput,
  onInputChange,
  onRun,
  loading = false,
  result,
  reviewMode,
}) {
  const [payload, setPayload] = useState(() => parseInput(userInput))

  useEffect(() => {
    setPayload(parseInput(userInput))
  }, [userInput])

  useEffect(() => {
    if (!result?.result) return
    const next = mergeRunResult(payload, result)
    setPayload(next)
    onInputChange(JSON.stringify(buildRunPayload(next)))
  }, [result])

  const runResult = result?.result || null
  const scenarioSet = runResult?.scenario_set || payload.scenario_set
  const scenarios = scenarioSet?.scenarios || []
  const selectedId =
    payload.selected_scenario_id || scenarioSet?.selected_scenario_id || ''
  const selectedScenario = scenarios.find((s) => s.id === selectedId)
  const hasScenarios = scenarios.length > 0
  const source = runResult?.meta?.source

  const commit = (overrides) => {
    if (loading || !onRun) return
    const next = { ...payload, ...overrides }
    const json = JSON.stringify(buildRunPayload(next))
    setPayload(next)
    onInputChange(json)
    onRun(json)
  }

  const generateScenarios = () => {
    commit({ action: 'generate', heuristic_only: true })
  }

  const selectScenario = (id) => {
    const next = { ...payload, selected_scenario_id: id }
    const json = JSON.stringify(buildRunPayload(next))
    setPayload(next)
    onInputChange(json)
  }

  const confirmMainline = () => {
    if (!selectedId) return
    commit({
      action: 'confirm',
      selected_scenario_id: selectedId,
      selection_rationale: payload.selection_rationale,
    })
  }

  if (reviewMode && hasScenarios) {
    return (
      <div className={`story-scenario-view mode-${mode} review`}>
        <p className="disclaimer">{scenarioSet.disclaimer}</p>
        <div className="comparison-grid">
          {scenarios.map((s) => (
            <ScenarioCard
              key={s.id}
              scenario={s}
              selected={s.id === selectedId}
              reviewMode
            />
          ))}
        </div>
        {selectedScenario && (
          <div className="confirmed-banner">
            <strong>已确认主线</strong>
            <p>{selectedScenario.title}</p>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className={`story-scenario-view mode-${mode}`}>
      <p className="intro">
        基于画像与差距诊断，生成三种互斥情景供比较。请选择最符合你风险偏好的主线后确认，再进入路线规划。
      </p>

      {scenarioSet?.disclaimer && (
        <p className="disclaimer">{scenarioSet.disclaimer}</p>
      )}

      {hasScenarios && (
        <div className="state-badge">
          <span className="state-label">
            {selectedId ? '已生成 · 待确认或已选线' : '已生成 · 请选择主线'}
          </span>
          {source && <span className="source-hint">来源：{source}</span>}
        </div>
      )}

      {!hasScenarios && (
        <>
          <p className="empty-hint">
            尚未生成情景。请确保上游「差距诊断」已运行，然后点击下方按钮生成三种情景（启发式，无需 LLM）。
          </p>
          <div className="actions">
            <button
              type="button"
              className="primary-btn"
              onClick={generateScenarios}
              disabled={loading}
            >
              {loading ? '生成中…' : '生成三种情景'}
            </button>
          </div>
        </>
      )}

      {hasScenarios && (
        <>
          <div className="comparison-grid">
            {scenarios.map((s) => (
              <ScenarioCard
                key={s.id}
                scenario={s}
                selected={s.id === selectedId}
                onSelect={selectScenario}
              />
            ))}
          </div>

          <label className="rationale-field">
            <span>选择理由（可选）</span>
            <textarea
              rows={mode === 'standalone' ? 3 : 2}
              value={payload.selection_rationale || ''}
              placeholder="例：我更看重可逆性，愿意接受较慢的进展节奏"
              disabled={loading || reviewMode}
              onChange={(e) =>
                setPayload({ ...payload, selection_rationale: e.target.value })
              }
            />
          </label>

          <div className="actions">
            <button
              type="button"
              className="primary-btn"
              onClick={confirmMainline}
              disabled={!selectedId || loading}
            >
              {loading ? '确认中…' : '确认主线'}
            </button>
            <button
              type="button"
              className="ghost-btn"
              onClick={generateScenarios}
              disabled={loading}
            >
              重新生成
            </button>
          </div>

          {selectedId && selectedScenario && scenarioSet?.selected_scenario_id === selectedId && (
            <div className="confirmed-banner">
              <strong>主线已确认</strong>
              <p>
                {selectedScenario.title}
                {payload.selection_rationale && ` — ${payload.selection_rationale}`}
              </p>
            </div>
          )}
        </>
      )}
    </div>
  )
}
