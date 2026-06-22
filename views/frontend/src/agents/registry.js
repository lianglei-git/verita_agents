/**
 * Agent 自定义视图注册表
 * config.json 中 view.type === "custom" 时按 id 懒加载
 */
const views = {
  'user-profile': () => import('./user-profile'),
}

export function resolveAgentView(agentId) {
  return views[agentId] || null
}
