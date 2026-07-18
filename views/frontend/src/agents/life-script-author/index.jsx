import './LifeScriptView.less'

import { useEffect, useState } from 'react'
import {
  CHAPTER_SUB_LABELS,
  PHASE_LABELS,
  buildCommitPayload,
  parseInput,
} from './types'

function StoryBiblePanel({ bible }) {
  if (!bible) return null
  const intent = bible.creative_intent || {}
  return (
    <div className="panel bible-panel">
      <h4>故事圣经</h4>
      {bible.core_conflict && <p>{bible.core_conflict}</p>}
      <dl>
        {intent.narrative_perspective && (
          <div>
            <dt>视角</dt>
            <dd>{intent.narrative_perspective}</dd>
          </div>
        )}
        {intent.time_span && (
          <div>
            <dt>时间跨度</dt>
            <dd>{intent.time_span}</dd>
          </div>
        )}
        {intent.genre_intensity && (
          <div>
            <dt>题材</dt>
            <dd>{intent.genre_intensity}</dd>
          </div>
        )}
      </dl>
      {(bible.themes?.length ?? 0) > 0 && (
        <>
          <h4>主题</h4>
          <ul>
            {bible.themes.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
        </>
      )}
      {(bible.characters?.length ?? 0) > 0 && (
        <>
          <h4>人物</h4>
          <ul>
            {bible.characters.slice(0, 6).map((c) => (
              <li key={c.id || c.name}>
                <strong>{c.name}</strong>
                {c.role && ` — ${c.role}`}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}

function OutlinePanel({ outline }) {
  const chapters = outline?.chapters || []
  if (!chapters.length) return null
  return (
    <div className="panel outline-panel">
      <h4>章节目录（{chapters.length} 章）</h4>
      <ul>
        {chapters.slice(0, 8).map((ch) => (
          <li key={ch.chapter_number || ch.title} className="outline-item">
            <strong>
              第{ch.chapter_number}章 {ch.title}
            </strong>
            {ch.summary && <span>{ch.summary}</span>}
          </li>
        ))}
      </ul>
      {chapters.length > 8 && (
        <p className="progress-meta">… 另有 {chapters.length - 8} 章</p>
      )}
    </div>
  )
}

function ChapterPlanPanel({ plan }) {
  if (!plan) return null
  return (
    <div className="panel chapter-plan">
      <h4>
        章节计划 · 第{plan.chapter_number}章 {plan.title}
      </h4>
      {plan.conflict && <p>{plan.conflict}</p>}
      {(plan.objectives?.length ?? 0) > 0 && (
        <ul>
          {plan.objectives.map((o) => (
            <li key={o}>{o}</li>
          ))}
        </ul>
      )}
      {(plan.beats?.length ?? 0) > 0 && (
        <ul className="beats">
          {plan.beats.map((b) => (
            <li key={b}>{b}</li>
          ))}
        </ul>
      )}
      <p className="progress-meta">
        状态：{plan.approval?.status || 'draft'}
        {plan.expected_word_count &&
          ` · 目标 ${plan.expected_word_count.min}–${plan.expected_word_count.max} 字`}
      </p>
    </div>
  )
}

function ChapterDraftPanel({ draft, continuityReport }) {
  if (!draft && !continuityReport) return null
  const flags =
    continuityReport?.issues ||
    draft?.continuity_flags ||
    []
  return (
    <div className="panel chapter-draft">
      <h4>
        章节草稿
        {draft?.chapter_number && ` · 第${draft.chapter_number}章`}
        {draft?.title && ` ${draft.title}`}
      </h4>
      {draft?.fiction_disclaimer && (
        <p className="fiction-note">{draft.fiction_disclaimer}</p>
      )}
      {draft?.content && <div className="draft-content">{draft.content}</div>}
      {draft?.word_count > 0 && (
        <p className="progress-meta">约 {draft.word_count} 字</p>
      )}
      {flags.length > 0 && (
        <ul className="continuity-flags">
          {flags.map((f, i) => (
            <li key={i} className={f.severity || 'warning'}>
              [{f.severity || 'warning'}] {f.message}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function ActiveQuestion({ question, value, onChange, disabled }) {
  if (!question) return null
  return (
    <div className="question-block">
      <h4>{question.text || question.question}</h4>
      <textarea
        rows={3}
        value={value}
        placeholder={question.hint || '请输入…'}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  )
}

export default function LifeScriptAuthorView({
  mode,
  userInput,
  onInputChange,
  onRun,
  loading = false,
  result,
  reviewMode,
}) {
  const [payload, setPayload] = useState(() => parseInput(userInput))
  const [draftText, setDraftText] = useState('')
  const [answerText, setAnswerText] = useState('')

  useEffect(() => {
    setPayload(parseInput(userInput))
  }, [userInput])

  const runResult = result?.result || null
  const session = runResult?.session ?? payload.session
  const phase = runResult?.current_phase || session?.current_phase || 'setup'
  const phaseLabel = runResult?.phase_label || PHASE_LABELS[phase] || phase
  const chapterSub = runResult?.chapter_subphase
  const subLabel = chapterSub ? CHAPTER_SUB_LABELS[chapterSub] : null
  const activeQuestion = runResult?.active_question

  useEffect(() => {
    if (!runResult) return
    const next = buildCommitPayload(payload, {
      message: '',
      session: runResult.session || payload.session,
    })
    setPayload(next)
    onInputChange(JSON.stringify(next))
    setAnswerText('')
    setDraftText('')
  }, [result])

  const commit = (overrides) => {
    if (loading || !onRun) return
    const next = buildCommitPayload(payload, {
      session: session || payload.session,
      ...overrides,
    })
    const json = JSON.stringify(next)
    setPayload(next)
    onInputChange(json)
    onRun(json)
  }

  const startFresh = () => commit({ reset: true, session: null })
  const bootstrap = () => commit({ session: session || payload.session })
  const submitAnswer = () => {
    if (!answerText.trim()) return
    commit({
      message: answerText.trim(),
      answer: { question_id: activeQuestion?.id, value: answerText.trim() },
      session: session || payload.session,
    })
  }
  const approvePlan = () =>
    commit({ approve_plan: true, session: session || payload.session })
  const rejectPlan = () =>
    commit({
      reject_plan: true,
      user_notes: draftText.trim(),
      session: session || payload.session,
    })
  const acceptDraft = () =>
    commit({ accept_draft: true, session: session || payload.session })
  const confirmBible = () =>
    commit({ confirm_bible: true, session: session || payload.session })
  const confirmOutline = () =>
    commit({ confirm_outline: true, session: session || payload.session })
  const confirmMidReview = () =>
    commit({
      confirm_mid_review: true,
      notes: draftText.trim(),
      session: session || payload.session,
    })

  const meta = runResult?.meta || {}
  const chaptersDone = meta.chapters_completed ?? 0
  const chaptersTotal = meta.chapters_total ?? 0

  if (reviewMode) {
    return (
      <div className={`life-script-view mode-${mode} review`}>
        <span className="phase-badge">{phaseLabel}</span>
        <StoryBiblePanel bible={runResult?.story_bible} />
        <OutlinePanel outline={runResult?.outline} />
        <ChapterPlanPanel plan={runResult?.chapter_plan} />
        <ChapterDraftPanel
          draft={runResult?.chapter_draft}
          continuityReport={runResult?.continuity_report}
        />
      </div>
    )
  }

  return (
    <div className={`life-script-view mode-${mode}`}>
      <span className="phase-badge">
        {phaseLabel}
        {subLabel && ` · ${subLabel}`}
      </span>

      {runResult?.reply && <p className="reply-hint">{runResult.reply}</p>}

      {chaptersTotal > 0 && (
        <p className="progress-meta">
          章节进度 {chaptersDone}/{chaptersTotal}
          {meta.all_complete && ' · 已全部完成'}
        </p>
      )}

      <StoryBiblePanel bible={runResult?.story_bible} />
      <OutlinePanel outline={runResult?.outline} />
      <ChapterPlanPanel plan={runResult?.chapter_plan} />
      <ChapterDraftPanel
        draft={runResult?.chapter_draft}
        continuityReport={runResult?.continuity_report}
      />

      <ActiveQuestion
        question={activeQuestion}
        value={answerText}
        onChange={setAnswerText}
        disabled={loading}
      />

      <div className="actions">
        {!session && (
          <button type="button" className="primary-btn" onClick={bootstrap} disabled={loading}>
            {loading ? '启动中…' : '开始创作'}
          </button>
        )}

        {phase === 'setup' && session && activeQuestion && (
          <button
            type="button"
            className="primary-btn"
            onClick={submitAnswer}
            disabled={!answerText.trim() || loading}
          >
            {loading ? '提交中…' : '提交回答'}
          </button>
        )}

        {phase === 'bible' && runResult?.story_bible && !meta.bible_approved && (
          <button type="button" className="primary-btn" onClick={confirmBible} disabled={loading}>
            {loading ? '处理中…' : '确认故事圣经'}
          </button>
        )}

        {phase === 'outline' && runResult?.outline && !meta.outline_approved && (
          <button type="button" className="primary-btn" onClick={confirmOutline} disabled={loading}>
            {loading ? '处理中…' : '确认章节大纲'}
          </button>
        )}

        {phase === 'chapter' && chapterSub === 'plan' && runResult?.chapter_plan && (
          <>
            <button type="button" className="primary-btn" onClick={approvePlan} disabled={loading}>
              {loading ? '处理中…' : '确认章节计划'}
            </button>
            <button type="button" className="ghost-btn" onClick={rejectPlan} disabled={loading}>
              退回修订
            </button>
          </>
        )}

        {phase === 'chapter' && chapterSub === 'plan' && !runResult?.chapter_plan && session && (
          <button type="button" className="primary-btn" onClick={bootstrap} disabled={loading}>
            {loading ? '生成中…' : '生成章节计划'}
          </button>
        )}

        {phase === 'chapter' && chapterSub === 'draft' && !runResult?.chapter_draft && (
          <button type="button" className="primary-btn" onClick={advanceChapter} disabled={loading}>
            {loading ? '写作中…' : '生成章节草稿'}
          </button>
        )}

        {phase === 'chapter' &&
          (chapterSub === 'draft' || chapterSub === 'continuity') &&
          runResult?.chapter_draft && (
            <button type="button" className="primary-btn" onClick={acceptDraft} disabled={loading}>
              {loading ? '处理中…' : '接受草稿并继续'}
            </button>
          )}

        {phase === 'mid_review' && (
          <>
            <label className="question-block">
              <span>中段回顾备注（可选）</span>
              <textarea
                rows={2}
                value={draftText}
                onChange={(e) => setDraftText(e.target.value)}
                disabled={loading}
              />
            </label>
            <button type="button" className="primary-btn" onClick={confirmMidReview} disabled={loading}>
              {loading ? '处理中…' : '确认继续创作'}
            </button>
          </>
        )}

        <button type="button" className="ghost-btn" onClick={startFresh} disabled={loading}>
          重新开始
        </button>
      </div>
    </div>
  )
}
