/** 自管理 Agent 新建运行时的空白输入（避免复制上一份 session） */

const SELF_MANAGED = new Set([
  'goal-bridge',
  'user-profile',
  'demo-goal-image',
  'story-scenario',
  'route-planner',
  'life-script-author',
  'text-to-speech',
  'en-syntax-tagger',
])

export function isSelfManagedAgent(agentId) {
  return SELF_MANAGED.has(agentId)
}

/** @param {string} [agentId] @returns {string} */
export function freshInputForAgent(agentId) {
  if (agentId === 'goal-bridge') {
    return JSON.stringify({ message: '', answer: null, session: null })
  }
  if (agentId === 'user-profile') {
    return JSON.stringify({
      story: '',
      answers: {},
      action: 'answer',
      universal: null,
      collection: null,
    })
  }
  if (agentId === 'demo-goal-image') {
    return JSON.stringify({
      sentence: '',
      mode: 'series',
      visual_style: '',
      template: '',
    })
  }
  if (agentId === 'story-scenario') {
    return JSON.stringify({
      profile: null,
      gap_diagnosis: null,
      scenario_set: null,
      selected_scenario_id: '',
      selection_rationale: '',
      heuristic_only: true,
      action: 'generate',
    })
  }
  if (agentId === 'route-planner') {
    return JSON.stringify({
      profile: null,
      gap_diagnosis: null,
      scenario_set: null,
      heuristic_only: true,
    })
  }
  if (agentId === 'life-script-author') {
    return JSON.stringify({
      message: '',
      session: null,
      handoff: null,
      reset: false,
    })
  }
  return ''
}
