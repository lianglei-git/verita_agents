/** route-planner AdaptiveRoadmap 契约 */

export const TIME_LABELS = {
  week: '本周',
  month: '本月',
  quarter: '本季',
  year: '本年',
}

export function emptyPayload() {
  return {
    profile: null,
    gap_diagnosis: null,
    scenario_set: null,
    heuristic_only: true,
  }
}

export function parseInput(value) {
  if (!value?.trim()) return emptyPayload()
  try {
    return { ...emptyPayload(), ...JSON.parse(value) }
  } catch {
    return emptyPayload()
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
    roadmap: r.roadmap ?? payload.roadmap,
  }
}

export function buildRunPayload(payload) {
  const out = { heuristic_only: payload.heuristic_only !== false }
  if (payload.profile) out.profile = payload.profile
  if (payload.gap_diagnosis) out.gap_diagnosis = payload.gap_diagnosis
  if (payload.scenario_set) out.scenario_set = payload.scenario_set
  return out
}
