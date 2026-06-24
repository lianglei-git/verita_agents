import './UserProfileView.less'

import { useEffect, useState } from 'react'

const RELEASED_PHASES = ['p0_sufficient', 'p0_conditional']

function emptyPayload() {
  return {
    story: '',
    answers: {},
    action: 'answer',
    universal: null,
    collection: null,
  }
}

function parseInput(value) {
  if (!value?.trim()) return emptyPayload()
  try {
    const data = JSON.parse(value)
    return { ...emptyPayload(), ...data }
  } catch {
    return { ...emptyPayload(), story: value }
  }
}

function TwinSection({ title, children }) {
  return (
    <section className="twin-section">
      <h4>{title}</h4>
      {children}
    </section>
  )
}

function FieldGrid({ data, labels }) {
  const entries = Object.entries(data || {}).filter(([k]) => k !== 'labels')
  if (entries.length === 0) return <p className="muted">暂无</p>
  return (
    <dl className="field-grid">
      {entries.map(([key, val]) => (
        <div key={key} className="field-row">
          <dt>{labels?.[key] || key}</dt>
          <dd>{val === null || val === '' ? '—' : String(val)}</dd>
        </div>
      ))}
    </dl>
  )
}

const IDENTITY_LABELS = {
  age_range: '年龄',
  region_anchor: '地区',
  occupation: '职业',
  native_language: '母语',
  role_anchor: '身份',
}

const CAPABILITY_LABELS = {
  self_assessed_level: '自评水平',
  strongest: '强项',
  weakest: '弱项',
}

const PHASE_LABELS = {
  p0_collecting: '采集中',
  p0_sufficient: '可放行',
  p0_conditional: '条件放行',
}

const RELEASE_LABELS = {
  collecting: '继续收集',
  sufficient: '信息充足',
  conditional: '条件放行',
}

const META_STATUS_LABELS = {
  open: '待确认',
  inferred: '自动推断',
  confirmed: '已确认',
  waived: '已跳过',
}

const PRIORITY_LABELS = {
  blocking: '关键',
  important: '重要',
  optional: '可选',
}

function metaProgress(collection) {
  const items = collection?.journey_meta || []
  const blocking = items.filter((m) => m.priority === 'blocking')
  const closed = blocking.filter((m) => ['inferred', 'confirmed', 'waived'].includes(m.status))
  return { blocking_total: blocking.length, blocking_closed: closed.length }
}

export default function UserProfileView({
  mode,
  userInput,
  onInputChange,
  onRun,
  loading = false,
  result,
  reviewMode,
}) {
  const [payload, setPayload] = useState(() => parseInput(userInput))
  const [answerText, setAnswerText] = useState('')

  useEffect(() => {
    setPayload(parseInput(userInput))
  }, [userInput])

  const runResult = result?.result || null
  const universal = runResult?.universal || payload.universal
  const twin = runResult?.twin || null
  const collection = runResult?.collection || payload.collection
  const question = runResult?.next_questions?.[0] || null
  const phase = runResult?.phase
  const completeness = runResult?.completeness
  const handoff = runResult?.handoff
  const routeSketch = collection?.route_sketch
  const anchors = universal?.anchors || {}
  const prog = metaProgress(collection)

  useEffect(() => {
    const r = result?.result
    if (!r) return
    setPayload((prev) => {
      const next = {
        story: '',
        answers: {},
        action: 'answer',
        universal: r.universal || prev.universal,
        collection: r.collection || prev.collection,
      }
      onInputChange(JSON.stringify(next))
      return next
    })
    setAnswerText('')
  }, [result])

  useEffect(() => {
    setAnswerText('')
  }, [question?.target])

  const buildPayload = (action = 'answer', answers = {}) => ({
    story: payload.story,
    answers,
    action,
    universal: universal || payload.universal,
    collection: collection || payload.collection,
  })

  const commitAndRun = (action, answers) => {
    if (loading || !onRun) return
    const nextPayload = buildPayload(action, answers)
    const json = JSON.stringify(nextPayload)
    setPayload(nextPayload)
    onInputChange(json)
    onRun(json)
  }

  const startFresh = () => {
    if (loading || !onRun) return
    const json = JSON.stringify(emptyPayload())
    setPayload(emptyPayload())
    onInputChange(json)
    onRun(json)
  }

  const submitAnswer = () => {
    if (!question || !answerText.trim() || loading) return
    const target = question.target || question.field
    commitAndRun('answer', { target, [target]: answerText.trim() })
  }

  const submitStory = () => {
    if (!payload.story.trim() || loading) return
    const nextPayload = {
      story: payload.story.trim(),
      answers: {},
      action: 'answer',
      universal: payload.universal,
      collection: payload.collection,
    }
    const json = JSON.stringify(nextPayload)
    setPayload(nextPayload)
    onInputChange(json)
    onRun?.(json)
  }

  const submitChoice = (choice) => {
    if (!question || loading) return
    const target = question.target || question.field
    commitAndRun('answer', { target, [target]: choice })
  }

  const skipQuestion = () => {
    if (!question?.skippable || loading) return
    const target = question.target || question.field
    commitAndRun('skip', { _skip_field: target, target })
  }

  const turnCount = collection?.turn_count ?? 0
  const hasMoreQuestions = (runResult?.next_questions?.length ?? 0) > 0
  const released = !hasMoreQuestions && (handoff || RELEASED_PHASES.includes(phase))
  const hasChoices = (question?.choices?.length ?? 0) > 0
  const showStoryBlock = !released && !question && !anchors.goal

  if (reviewMode) {
    return (
      <div className={`user-profile-view mode-${mode} review`}>
        <TwinDashboard
          twin={twin}
          universal={universal}
          collection={collection}
          completeness={completeness}
          phase={phase}
          routeSketch={routeSketch}
          handoff={handoff}
        />
      </div>
    )
  }

  return (
    <div className={`user-profile-view mode-${mode}`}>
      {showStoryBlock && (
        <div className="story-block">
          <label>
            <span>个人故事（可选）</span>
            <textarea
              rows={mode === 'standalone' ? 5 : 4}
              value={payload.story}
              placeholder="可选：用一段话介绍你自己和目标，AI 会从中推断并减少追问。"
              onChange={(e) => setPayload({ ...payload, story: e.target.value })}
              disabled={loading}
            />
          </label>
          <div className="story-actions">
            <button
              type="button"
              className="primary-btn story-start-btn"
              onClick={submitStory}
              disabled={!payload.story.trim() || loading}
            >
              {loading ? '处理中…' : '从故事开始'}
            </button>
            <button type="button" className="ghost-btn" onClick={startFresh} disabled={loading}>
              直接开始对话
            </button>
          </div>
        </div>
      )}

      {(anchors.goal || anchors.current) && (
        <div className="anchors-preview">
          {anchors.goal && (
            <p>
              <span className="path-label">目标</span> {anchors.goal}
            </p>
          )}
          {anchors.current && (
            <p>
              <span className="path-label">现在</span> {anchors.current}
            </p>
          )}
        </div>
      )}

      {collection && (
        <div className="progress-bar-wrap">
          <div className="progress-meta">
            <span>关键信息</span>
            <span className="progress-count">
              {prog.blocking_closed}/{prog.blocking_total || '—'} · 第 {turnCount} 轮
            </span>
          </div>
          <div className="progress-track">
            <div
              className="progress-fill"
              style={{
                width: `${
                  prog.blocking_total
                    ? Math.min(100, (prog.blocking_closed / prog.blocking_total) * 100)
                    : 10
                }%`,
              }}
            />
          </div>
          {collection.release?.status && (
            <span className={`release-chip ${collection.release.status}`}>
              {RELEASE_LABELS[collection.release.status] || collection.release.status}
            </span>
          )}
          {collection.release?.reason && (
            <p className="release-reason muted">{collection.release.reason}</p>
          )}
          {typeof collection.release?.confidence === 'number' && (
            <p className="release-confidence muted">
              置信度 {Math.round(collection.release.confidence * 100)}%
            </p>
          )}
        </div>
      )}

      {collection && (
        <CollectionTrace
          collection={collection}
          runMeta={runResult?.meta}
          turnCount={turnCount}
        />
      )}

      {routeSketch?.title && (
        <div className="path-preview">
          <span className="path-label">路线草图</span>
          <strong>{routeSketch.title}</strong>
          {routeSketch.summary && <p>{routeSketch.summary}</p>}
          {routeSketch.milestones?.length > 0 && (
            <ol className="milestones">
              {routeSketch.milestones.map((m) => (
                <li key={m}>{m}</li>
              ))}
            </ol>
          )}
        </div>
      )}

      {question && !released && (
        <div className={`followup-block single ${loading ? 'is-loading' : ''}`}>
          <div className="question-meta">
            <span className="depth-tag">
              {question.target?.startsWith('anchor:')
                ? '锚点'
                : question.target?.startsWith('universal:')
                  ? '基础身份'
                  : 'Journey'}
            </span>
            <span className="phase-tag-sm">{question.phase || collection?.phase}</span>
          </div>
          <h3>{question.question}</h3>
          {question.why && <p className="question-why">{question.why}</p>}

          {hasChoices && (
            <div className="choice-row">
              {question.choices.map((c) => (
                <button
                  key={c}
                  type="button"
                  className="choice-btn"
                  disabled={loading}
                  onClick={() => submitChoice(c)}
                >
                  {c}
                </button>
              ))}
            </div>
          )}

          {!hasChoices && (
            <>
              <label className="followup-item">
                <textarea
                  rows={mode === 'standalone' ? 3 : 2}
                  value={answerText}
                  placeholder={question.hint || '用你自己的话回答…'}
                  disabled={loading}
                  onChange={(e) => setAnswerText(e.target.value)}
                />
              </label>
              <div className="followup-actions">
                <button
                  type="button"
                  className="primary-btn"
                  onClick={submitAnswer}
                  disabled={!answerText.trim() || loading}
                >
                  {loading ? '提交中…' : '提交并继续'}
                </button>
              </div>
            </>
          )}

          {loading && <p className="loading-hint">正在处理您的回答…</p>}

          {runResult?.meta?.inferred_fields?.length > 0 && (
            <p className="inferred-hint">
              已从您的回答自动推断 {runResult.meta.inferred_fields.length} 项，跳过重复追问
            </p>
          )}

          <div className="followup-actions secondary">
            {question.skippable && (
              <button type="button" className="ghost-btn" onClick={skipQuestion} disabled={loading}>
                跳过
              </button>
            )}
          </div>
        </div>
      )}

      {released && (
        <div className="release-banner">
          <strong>画像采集完成</strong>
          <p>{runResult?.output}</p>
          {collection?.release?.reason && (
            <p className="release-reason">放行依据：{collection.release.reason}</p>
          )}
          {handoff?.route_sketch?.title && <p>路线：{handoff.route_sketch.title}</p>}
        </div>
      )}

      {(twin || universal) && (
        <TwinDashboard
          twin={twin}
          universal={universal}
          collection={collection}
          completeness={completeness}
          phase={phase}
          routeSketch={routeSketch}
          handoff={handoff}
        />
      )}
    </div>
  )
}

function TwinDashboard({ twin, universal, collection, completeness, phase, routeSketch, handoff }) {
  if (!twin && !universal) return null

  const anchors = universal?.anchors || {}
  const ident = universal?.identity || twin?.identity || {}
  const cap = universal?.capability_snapshot || {}

  return (
    <div className="twin-dashboard">
      <div className="dashboard-header">
        <span className="engine-tag">Digital Twin · v2</span>
        {phase && <span className={`phase-tag ${phase}`}>{PHASE_LABELS[phase] || phase}</span>}
        {completeness && (
          <span className="completeness">
            锚点 {Math.round((completeness.anchors || 0) * 100)}% · 基础身份{' '}
            {Math.round((completeness.baseline || 0) * 100)}% · 关键信息{' '}
            {Math.round((completeness.meta_blocking || 0) * 100)}%
          </span>
        )}
      </div>

      <div className="twin-grid">
        <TwinSection title="锚点 Anchors">
          <FieldGrid
            data={{
              goal: anchors.goal,
              current: anchors.current || twin?._current_narrative,
              goal_clarity: anchors.goal_clarity,
              current_clarity: anchors.current_clarity,
            }}
            labels={{
              goal: '目标',
              current: '现状',
              goal_clarity: '目标清晰度',
              current_clarity: '现状清晰度',
            }}
          />
        </TwinSection>
        <TwinSection title="身份 Identity">
          <FieldGrid data={ident} labels={IDENTITY_LABELS} />
        </TwinSection>
        <TwinSection title="能力快照">
          <FieldGrid data={cap} labels={CAPABILITY_LABELS} />
        </TwinSection>
        {twin?.growth && (
          <TwinSection title="成长 Growth">
            <FieldGrid
              data={twin.growth}
              labels={{
                goal: '目标',
                timeline_urgency: '时间线',
                deadline: '截止日期',
              }}
            />
          </TwinSection>
        )}
        {twin?.scenario && Object.keys(twin.scenario).some((k) => twin.scenario[k]) && (
          <TwinSection title="场景 Scenario">
            <FieldGrid
              data={twin.scenario}
              labels={{
                interview_type: '面试类型',
                target_market: '目标市场',
                target_exam: '目标考试',
              }}
            />
          </TwinSection>
        )}
      </div>

      {(collection?.journey_meta?.length ?? 0) > 0 && (
        <div className="assumptions journey-meta-panel">
          <h4>Journey 元信息</h4>
          <ul className="meta-list">
            {collection.journey_meta.map((m) => (
              <li key={m.key} className={`meta-item status-${m.status}`}>
                <span className="meta-priority">{PRIORITY_LABELS[m.priority] || m.priority}</span>
                <span className="meta-label">{m.label}</span>
                <span className="meta-value">{m.value || '—'}</span>
                <span className="meta-status">{META_STATUS_LABELS[m.status] || m.status}</span>
                {m.source && m.source !== 'user' && (
                  <span className="meta-source">← {m.source}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {(handoff?.assumptions?.length ?? 0) > 0 && (
        <div className="assumptions">
          <h4>假设补全</h4>
          <ul>
            {handoff.assumptions.map((a, i) => (
              <li key={i}>
                {a.field}: {a.value} — {a.reason}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function CollectionTrace({ collection, runMeta, turnCount }) {
  const [open, setOpen] = useState(true)
  const askedLog = collection?.asked_log || []
  const answered = collection?.answered_effective || {}
  const inferred = runMeta?.inferred_fields || []

  if (!collection) return null

  return (
    <div className="collection-trace">
      <button type="button" className="trace-toggle" onClick={() => setOpen((v) => !v)}>
        {open ? '▼' : '▶'} 采集记录（{turnCount} 轮对话）
      </button>
      {open && (
        <div className="trace-body">
          {runMeta?.inference_mode && (
            <p className="trace-hint muted">
              推断模式：{runMeta.inference_mode === 'llm' ? 'LLM 语义理解' : '无 LLM，原样记录用户表述'}
              {!runMeta.llm_available && '（请配置 OPENAI_API_KEY 以启用智能理解）'}
            </p>
          )}
          <p className="trace-hint muted">
            系统根据语义理解你的目标与回答，自动闭合 journey 项（标记为「自动推断」）。
          </p>

          {askedLog.length > 0 && (
            <div className="trace-section">
              <h5>对话轮次</h5>
              <ol className="trace-log">
                {askedLog.map((entry, i) => (
                  <li key={`${entry.turn}-${entry.target}-${i}`}>
                    <span className="trace-turn">第 {entry.turn} 轮</span>
                    <code>{entry.target}</code>
                    {entry.question && entry.question !== '(跳过)' && (
                      <span className="trace-answer">「{entry.question}」</span>
                    )}
                    {entry.question === '(跳过)' && <span className="muted">（跳过）</span>}
                  </li>
                ))}
              </ol>
            </div>
          )}

          {Object.keys(answered).length > 0 && (
            <div className="trace-section">
              <h5>有效回答</h5>
              <ul className="trace-log">
                {Object.entries(answered).map(([target, entry]) => (
                  <li key={target}>
                    <code>{target}</code>
                    <span className="trace-answer">「{entry.raw}」</span>
                    {(entry.inferred || []).length > 0 && (
                      <span className="trace-inferred">
                        → 推断 {entry.inferred.join(', ')}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {inferred.length > 0 && (
            <div className="trace-section">
              <h5>本轮新推断</h5>
              <p className="trace-inferred-inline">{inferred.join(' · ')}</p>
            </div>
          )}

          {askedLog.length === 0 && Object.keys(answered).length === 0 && (
            <p className="muted">尚无对话记录；提交故事或回答后这里会显示每轮 target 与推断路径。</p>
          )}
        </div>
      )}
    </div>
  )
}
