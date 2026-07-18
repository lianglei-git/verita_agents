/** story-scenario 前后端数据契约 */

export const ARCHETYPE_LABELS = {
  conservative: '稳健路径',
  balanced: '平衡路径',
  aggressive: '进取路径',
}

export const COMPARISON_AXIS_LABELS = {
  risk: '风险',
  upside: '收益',
  reversibility: '可逆性',
  effort: '投入',
}

export function emptyPayload() {
  return {
    profile: null,
    gap_diagnosis: null,
    scenario_set: null,
    selected_scenario_id: '',
    selection_rationale: '',
    heuristic_only: true,
    action: 'generate',
  }
}

export function parseInput(value) {
  if (!value?.trim()) return emptyPayload()
  try {
    return { ...emptyPayload(), ...JSON.parse(value) }
  } catch {
    return { ...emptyPayload(), selection_rationale: value }
  }
}

export function mergeRunResult(payload, result) {
  const r = result?.result || result
  if (!r) return payload
  return {
    ...payload,
    profile: r.profile ?? payload.profile,
    gap_diagnosis: r.gap_diagnosis ?? payload.gap_diagnosis,
    scenario_set: r.scenario_set ?? payload.scenario_set,
    selected_scenario_id:
      r.scenario_set?.selected_scenario_id || payload.selected_scenario_id || '',
    selection_rationale:
      r.scenario_set?.selection_rationale || payload.selection_rationale || '',
  }
}

export function buildRunPayload(payload, overrides = {}) {
  const next = { ...payload, ...overrides }
  const out = {
    heuristic_only: next.heuristic_only !== false,
    action: next.action || 'generate',
  }
  if (next.profile) out.profile = next.profile
  if (next.gap_diagnosis) out.gap_diagnosis = next.gap_diagnosis
  if (next.scenario_set) out.scenario_set = next.scenario_set
  if (next.selected_scenario_id) {
    out.selected_scenario_id = next.selected_scenario_id
    if (out.scenario_set) {
      out.scenario_set = {
        ...out.scenario_set,
        selected_scenario_id: next.selected_scenario_id,
        selection_rationale: next.selection_rationale || '',
      }
    }
  }
  if (next.selection_rationale) out.selection_rationale = next.selection_rationale
  return out
}

export function claimText(claim) {
  if (!claim) return ''
  if (typeof claim === 'string') return claim
  return claim.text || ''
}
