const BASE = '/api'

function errorMessage(data, status) {
  const err = data?.error
  if (typeof err === 'string' && err) return err
  if (err && typeof err === 'object' && err.message) return err.message
  return `Request failed: ${status}`
}

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    throw new Error(errorMessage(data, res.status))
  }
  return data
}

export function fetchAgents() {
  return request('/agents')
}

export function fetchAgent(id) {
  return request(`/agents/${id}`)
}

export async function runAgent(id, input, options = {}, runId = null) {
  const body = { input, options }
  if (runId) body.run_id = runId
  const res = await fetch(`${BASE}/agents/${id}/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    // 业务 4xx 仍带 result，工作台继续展示
    if (data && data.result !== undefined) return data
    throw new Error(errorMessage(data, res.status))
  }
  return data
}

export function fetchWorkflow(name) {
  const qs = name ? `?name=${encodeURIComponent(name)}` : ''
  return request(`/workflow${qs}`)
}

export function fetchWorkflows() {
  return request('/workflows')
}

export function fetchSpec() {
  return request('/spec')
}

export function createRun(sourceInput, workflow) {
  const body = { source_input: sourceInput }
  if (workflow) body.workflow = workflow
  return request('/runs', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function updateRunInput(runId, sourceInput) {
  return request(`/runs/${runId}/input`, {
    method: 'PATCH',
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

/**
 * Consume SSE from POST /api/agents/{id}/stream.
 * @param {string} id
 * @param {string} input
 * @param {object} options
 * @param {(event: object) => void} onEvent
 * @param {AbortSignal} [signal]
 */
export async function streamAgent(id, input, options = {}, onEvent, signal) {
  const res = await fetch(`/api/agents/${id}/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ input, options }),
    signal,
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.error || `Stream failed: ${res.status}`)
  }
  const reader = res.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop() || ''
    for (const part of parts) {
      for (const line of part.split('\n')) {
        if (!line.startsWith('data:')) continue
        const raw = line.slice(5).trim()
        if (!raw) continue
        try {
          onEvent(JSON.parse(raw))
        } catch {
          /* ignore */
        }
      }
    }
  }
}

