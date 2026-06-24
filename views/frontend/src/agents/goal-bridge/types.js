/**
 * GoalBridge 前后端数据契约（与 agents/GoalBridge/contract.py、schema.json 对齐）
 * @module goal-bridge/types
 */

/** @typedef {1|2|3} StepId */

/** @typedef {'open'|'single'|'multi'} QuestionType */

/**
 * @typedef {'sequential'|'survey'} UiMode
 * - sequential 逐题展示，每次提交一题
 * - survey     问卷模式，一次展示全部题目（answers_batch 提交）
 */

/** @typedef {Object} QuestionOption @property {string} id @property {string} label */

/**
 * @typedef {Object} AgentQuestion
 * @property {string} id
 * @property {StepId} step
 * @property {QuestionType} type
 * @property {string} text
 * @property {QuestionOption[]} [options]
 * @property {boolean} [required]
 */

/**
 * @typedef {Object} AnswerPayload
 * @property {string} question_id
 * @property {QuestionType} type
 * @property {string|string[]} value
 */

/** @typedef {Object} QuestionProgress @property {number} answered @property {number} total */

/**
 * @typedef {Object} Step1State
 * @property {'pending'|'unclear'|'clear'} clarity
 * @property {string} goal_text
 * @property {AgentQuestion[]} pending_questions
 * @property {Record<string, {type: QuestionType, value: string|string[]}>} answers
 * @property {UiMode} ui_mode
 */

/**
 * @typedef {Object} Step2State
 * @property {'pending'|'collecting'|'complete'} status
 * @property {'pending'|'need_more'|'enough'} sufficiency
 * @property {string} goal_text
 * @property {AgentQuestion[]} pending_questions
 * @property {Record<string, {type: QuestionType, value: string|string[]}>} answers
 * @property {UiMode} ui_mode
 * @property {Record<string, unknown>} data
 */

/** @typedef {Object} GoalBridgeSession @property {StepId} current_step @property {Step1State} step1 @property {Step2State} step2 */

/**
 * @typedef {Object} AgentRunPayload
 * @property {string} [message]
 * @property {AnswerPayload} [answer]
 * @property {AnswerPayload[]} [answers_batch]
 * @property {GoalBridgeSession} [session]
 * @property {boolean} [reset]
 * @property {boolean} [confirm_step]
 */

/** @typedef {Object} UserProfile @property {string} summary @property {Record<string, unknown>} structured */

export const STEP_LABELS = { 1: '目标是否明确', 2: '信息收集', 3: '差距评估' }

export const UI_MODES = { SEQUENTIAL: 'sequential', SURVEY: 'survey' }

export const QUESTION_TYPES = { OPEN: 'open', SINGLE: 'single', MULTI: 'multi' }

/** @param {import('./types').AgentQuestion['options']} options */
export function optionIdSet(options) {
  return new Set((options || []).map((o) => o.id))
}

/** @param {import('./types').AgentQuestion} question @param {string|string[]} draft */
export function buildPartialBatch(questions, drafts) {
  return questions
    .map((q) => buildAnswer(q, drafts[q.id] ?? (q.type === 'multi' ? [] : '')))
    .filter(isAnswerValid)
}

/** @param {unknown[]} raw @returns {AgentQuestion[]} */
export function normalizeQuestions(raw) {
  const used = new Set()
  return (Array.isArray(raw) ? raw : [])
    .map((item, i) => normalizeQuestion(item))
    .filter(Boolean)
    .map((q, i) => {
      let id = String(q.id || 'q')
      if (!id || id === 'q' || used.has(id)) {
        id = `q${i + 1}`
      }
      while (used.has(id)) {
        id = `q${i + 1}_${used.size}`
      }
      used.add(id)
      return { ...q, id }
    })
}

/** @param {unknown} raw @returns {AgentQuestion|null} */
export function normalizeQuestion(raw) {
  if (!raw || typeof raw !== 'object') return null
  const q = /** @type {Record<string, unknown>} */ (raw)
  const text = String(q.text || q.question || q.label || '').trim()
  if (!text) return null
  const rawOptions = Array.isArray(q.options) ? q.options : []
  const options = rawOptions
    .map((o, i) => {
      if (typeof o === 'string' && o.trim()) {
        return { id: `opt_${i}`, label: o.trim() }
      }
      if (o && typeof o === 'object' && String(/** @type {{label?: string}} */ (o).label || '').trim()) {
        const opt = /** @type {{id?: string, label?: string}} */ (o)
        return { id: opt.id || `opt_${i}`, label: String(opt.label).trim() }
      }
      return null
    })
    .filter(Boolean)
  let type = q.type || 'open'
  if ((type === 'single' || type === 'multi') && options.length === 0) {
    type = 'open'
  }
  return {
    id: String(q.id || 'q'),
    step: q.step || 1,
    type,
    text,
    options,
    required: q.required !== false,
  }
}

/** @param {AnswerPayload} answer @returns {boolean} */
export function isAnswerValid(answer) {
  if (!answer?.question_id) return false
  const { type, value } = answer
  if (type === 'open') return typeof value === 'string' && value.trim().length > 0
  if (type === 'single') {
    return typeof value === 'string' && value.trim().length > 0
  }
  if (type === 'multi') {
    return Array.isArray(value) && value.some((v) => String(v).trim().length > 0)
  }
  return false
}

/** @returns {AgentRunPayload} */
export function emptyPayload() {
  return { message: '', answer: null, session: null }
}

/** @param {string} value @returns {AgentRunPayload} */
export function parseInput(value) {
  if (!value?.trim()) return emptyPayload()
  try {
    return { ...emptyPayload(), ...JSON.parse(value) }
  } catch {
    return { ...emptyPayload(), message: value }
  }
}

/** @param {GoalBridgeSession|null} session @param {number} step @param {object|null} runResult */
export function getStepState(session, step, runResult) {
  const s1 = session?.step1
  const s2 = session?.step2
  if (step === 2) {
    const rawPending = s2?.pending_questions || runResult?.next_questions || []
    const pendingQuestions = normalizeQuestions(rawPending)
    return {
      uiMode: runResult?.ui_mode || s2?.ui_mode || UI_MODES.SURVEY,
      pendingQuestions,
      answers: s2?.answers || {},
      goal: s2?.goal_text || s1?.goal_text || '',
      showIntro: false,
    }
  }
  const pendingQuestions = normalizeQuestions(
    s1?.pending_questions || runResult?.next_questions || [],
  )
  const stepComplete = runResult?.step_complete === true
  return {
    uiMode: runResult?.ui_mode || s1?.ui_mode || UI_MODES.SEQUENTIAL,
    pendingQuestions,
    answers: s1?.answers || {},
    goal: s1?.goal_text || '',
    showIntro: !session?.turns?.length && !stepComplete && !pendingQuestions.length,
  }
}

/** @param {AgentQuestion} question @param {string|string[]} value @returns {AnswerPayload} */
export function buildAnswer(question, value) {
  return { question_id: question.id, type: question.type, value }
}
