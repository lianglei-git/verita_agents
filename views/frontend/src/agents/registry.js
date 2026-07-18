/**
 * Agent 自定义视图注册表
 * config.json 中 view.type === "custom" 时按 id 懒加载
 */
const views = {
  'user-profile': () => import('./user-profile'),
  'route-planner': () => import('./route-planner'),
  'story-scenario': () => import('./story-scenario'),
  'life-script-author': () => import('./life-script-author'),
  'english-grammar-analyzer': () => import('./english-grammar-analyzer'),
  'goal-bridge': () => import('./goal-bridge'),
  'demo-goal-image': () => import('./demo-goal-image'),
}

export function resolveAgentView(agentId) {
  return views[agentId] || null
}
