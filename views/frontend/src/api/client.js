const BASE = '/api'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    throw new Error(data.error || `Request failed: ${res.status}`)
  }
  return data
}

export function fetchAgents() {
  return request('/agents')
}

export function fetchAgent(id) {
  return request(`/agents/${id}`)
}

export function runAgent(id, input, options = {}, runId = null) {
  const body = { input, options }
  if (runId) body.run_id = runId
  return request(`/agents/${id}/run`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function fetchWorkflow() {
  return request('/workflow')
}

export function fetchSpec() {
  return request('/spec')
}

export function createRun(sourceInput) {
  return request('/runs', {
    method: 'POST',
    body: JSON.stringify({ source_input: sourceInput }),
  })
}

export function fetchRuns() {
  return request('/runs')
}

export function fetchRun(runId) {
  return request(`/runs/${runId}`)
}

export function fetchRunContext(runId, agentId) {
  return request(`/runs/${runId}/context/${agentId}`)
}

export function executeInRun(runId, agentId, input, options = {}) {
  const body = { options }
  if (input !== undefined && input !== null) body.input = input
  return request(`/runs/${runId}/execute/${agentId}`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}
