/** life-script-author 前后端契约 */

export const PHASE_LABELS = {
  setup: '创作意图确认',
  bible: '故事圣经',
  outline: '章节大纲',
  chapter: '逐章创作',
  mid_review: '中段回顾',
  complete: '创作完成',
}

export const CHAPTER_SUB_LABELS = {
  plan: '章节计划',
  draft: '章节草稿',
  continuity: '连续性校验',
  update: '圣经回写',
}

export function emptyPayload() {
  return {
    message: '',
    session: null,
    handoff: null,
    reset: false,
  }
}

export function parseInput(value) {
  if (!value?.trim()) return emptyPayload()
  try {
    return { ...emptyPayload(), ...JSON.parse(value) }
  } catch {
    return { ...emptyPayload(), message: value }
  }
}

export function buildCommitPayload(payload, overrides = {}) {
  return {
    ...payload,
    ...overrides,
    session: overrides.session ?? payload.session,
  }
}
