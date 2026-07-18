import './RoutePlannerView.less'

import { useEffect, useState } from 'react'
import { buildRunPayload, mergeRunResult, parseInput, TIME_LABELS } from './types'

function PhaseCard({ phase, index }) {
  const tw = phase.time_window || {}
  const timeLabel = TIME_LABELS[tw.label] || tw.label || '阶段'

  return (
    <article className="phase-card">
      <header>
        <span className="phase-num">{index + 1}</span>
        <div>
          <h4>{phase.title}</h4>
          <p className="phase-goal">{phase.goal}</p>
          {(tw.end || tw.start) && (
            <span className="time-window">
              {timeLabel}
              {tw.end ? ` · ${tw.end}` : ''}
            </span>
          )}
        </div>
      </header>

      {(phase.actions?.length ?? 0) > 0 && (
        <section>
          <h5>行动</h5>
          <ul className="action-list">
            {phase.actions.map((a) => (
              <li key={a.id || a.description}>
                <strong>{a.description}</strong>
                {a.effort && <span className="effort">{a.effort}</span>}
              </li>
            ))}
          </ul>
        </section>
      )}

      {(phase.milestones?.length ?? 0) > 0 && (
        <section>
          <h5>里程碑</h5>
          <ul>
            {phase.milestones.map((m) => (
              <li key={m.id || m.description}>
                {m.description}
                {m.due && <span className="due"> · {m.due}</span>}
              </li>
            ))}
          </ul>
        </section>
      )}

      {(phase.risk_signals?.length ?? 0) > 0 && (
        <section className="risk-section">
          <h5>风险信号</h5>
          <ul>
            {phase.risk_signals.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </section>
      )}

      {phase.if_not_met?.adjustments?.length > 0 && (
        <section className="adjust-section">
          <h5>若未达标</h5>
          {phase.if_not_met.description && (
            <p className="adjust-desc">{phase.if_not_met.description}</p>
          )}
          <ul>
            {phase.if_not_met.adjustments.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </section>
      )}

      {phase.review_checkpoint?.questions?.length > 0 && (
        <section className="review-section">
          <h5>
            复盘
            {phase.review_checkpoint.when && (
              <span className="review-when"> · {phase.review_checkpoint.when}</span>
            )}
          </h5>
          <ul>
            {phase.review_checkpoint.questions.map((q) => (
              <li key={q}>{q}</li>
            ))}
          </ul>
        </section>
      )}
    </article>
  )
}

function RoadmapPanel({ roadmap }) {
  if (!roadmap) return null
  return (
    <div className="roadmap-panel">
      <header className="roadmap-header">
        <h3>{roadmap.title || '自适应路线图'}</h3>
        {roadmap.summary && <p className="roadmap-summary">{roadmap.summary}</p>}
        {roadmap.version > 1 && (
          <span className="version-tag">v{roadmap.version}</span>
        )}
      </header>
      <div className="phases">
        {(roadmap.phases || []).map((phase, i) => (
          <PhaseCard key={phase.id || i} phase={phase} index={i} />
        ))}
      </div>
    </div>
  )
}

export default function RoutePlannerView({
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
  const roadmap = runResult?.roadmap || payload.roadmap
  const blocked = runResult?.blocked
  const selectedScenario = runResult?.selected_scenario
  const scenarioSet = runResult?.scenario_set || payload.scenario_set
  const hasSelection = Boolean(
    scenarioSet?.selected_scenario_id || selectedScenario?.id,
  )
  const source = runResult?.meta?.source

  const generateRoadmap = () => {
    if (loading || !onRun) return
    const json = JSON.stringify(buildRunPayload(payload))
    onRun(json)
  }

  if (reviewMode && roadmap) {
    return (
      <div className={`route-planner-view mode-${mode} review`}>
        <RoadmapPanel roadmap={roadmap} />
      </div>
    )
  }

  return (
    <div className={`route-planner-view mode-${mode}`}>
      <p className="intro">
        基于已确认的情景主线与差距诊断，生成可执行的自适应路线图。每个阶段包含行动、里程碑、风险信号与复盘节点。
      </p>

      {selectedScenario && (
        <div className="scenario-context">
          <span className="context-label">情景主线</span>
          <strong>{selectedScenario.title}</strong>
          {selectedScenario.tagline && (
            <span className="context-tagline">{selectedScenario.tagline}</span>
          )}
        </div>
      )}

      {!hasSelection && !roadmap && (
        <p className="blocked-hint">
          请先在「情景推演」节点确认主线（selected_scenario_id），再生成路线图。
        </p>
      )}

      {blocked && runResult?.output && (
        <p className="blocked-hint" role="alert">{runResult.output}</p>
      )}

      {!roadmap && hasSelection && (
        <div className="actions">
          <button
            type="button"
            className="primary-btn"
            onClick={generateRoadmap}
            disabled={loading}
          >
            {loading ? '生成中…' : '生成路线图'}
          </button>
        </div>
      )}

      {roadmap && (
        <>
          {source && (
            <div className="state-badge">
              <span className="state-label">路线图已生成</span>
              <span className="source-hint">来源：{source}</span>
            </div>
          )}
          <RoadmapPanel roadmap={roadmap} />
          <div className="actions">
            <button
              type="button"
              className="ghost-btn"
              onClick={generateRoadmap}
              disabled={loading}
            >
              {loading ? '重新生成中…' : '重新生成'}
            </button>
          </div>
        </>
      )}
    </div>
  )
}
