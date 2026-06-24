/** 自管理 Agent 新建运行时的空白输入（避免复制上一份 session） */

const SELF_MANAGED = new Set(['goal-bridge', 'user-profile'])

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
  return ''
}
