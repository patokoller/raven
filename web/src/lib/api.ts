/**
 * Raven API Client
 * Typed wrappers around all FastAPI endpoints.
 */

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('raven_token') : null
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }))
    throw new ApiError(res.status, err.detail || 'Request failed')
  }
  return res.json()
}

// ── Auth ─────────────────────────────────────────────────────
export const auth = {
  login: (email: string, password: string) =>
    request<{ access_token: string; user: any }>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
}

// ── Counterparties ────────────────────────────────────────────
export const counterparties = {
  list: (params?: { entity_type?: string; risk_tier?: string }) => {
    const q = new URLSearchParams(params as any).toString()
    return request<any[]>(`/api/v1/counterparties${q ? '?' + q : ''}`)
  },
  get: (id: string) => request<any>(`/api/v1/counterparties/${id}`),
  scores: (id: string, days = 90) =>
    request<any>(`/api/v1/counterparties/${id}/scores?days=${days}`),
  override: (id: string, body: { dimension: string; new_value: number; rationale: string }) =>
    request<any>(`/api/v1/counterparties/${id}/override`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
}

// ── Portfolios ────────────────────────────────────────────────
export const portfolios = {
  list: () => request<any[]>('/api/v1/portfolios'),
  get: (id: string) => request<any>(`/api/v1/portfolios/${id}`),
  metrics: (id: string) => request<any>(`/api/v1/portfolios/${id}/metrics`),
  positions: (id: string) => request<any[]>(`/api/v1/portfolios/${id}/positions`),
  upload: (formData: FormData) =>
    fetch(`${BASE_URL}/api/v1/portfolios/upload`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${localStorage.getItem('raven_token')}` },
      body: formData,
    }).then(r => r.json()),
  stress: (id: string, scenario_id: string) =>
    request<any>(`/api/v1/portfolios/${id}/stress`, {
      method: 'POST',
      body: JSON.stringify({ scenario_id }),
    }),
}

// ── Reports ───────────────────────────────────────────────────
export const reports = {
  list: (status?: string) =>
    request<any[]>(`/api/v1/reports${status ? '?status=' + status : ''}`),
  get: (id: string) => request<any>(`/api/v1/reports/${id}`),
  generate: (body: { portfolio_id: string; client_id: string; report_period: string }) =>
    request<any>('/api/v1/reports/generate', { method: 'POST', body: JSON.stringify(body) }),
  editSection: (id: string, section: string, content: any) =>
    request<any>(`/api/v1/reports/${id}/sections`, {
      method: 'PATCH',
      body: JSON.stringify({ section, content }),
    }),
  approve: (id: string) =>
    request<any>(`/api/v1/reports/${id}/approve`, { method: 'POST' }),
  deliver: (id: string, channel: string, note?: string) =>
    request<any>(`/api/v1/reports/${id}/deliver`, {
      method: 'POST',
      body: JSON.stringify({ channel, note }),
    }),
}

// ── Alerts ────────────────────────────────────────────────────
export const alerts = {
  list: (status?: string) =>
    request<any[]>(`/api/v1/alerts${status ? '?status=' + status : ''}`),
  action: (id: string, action: string, note?: string) =>
    request<any>(`/api/v1/alerts/${id}/action`, {
      method: 'POST',
      body: JSON.stringify({ action, note }),
    }),
}

// ── Stress Scenarios ──────────────────────────────────────────
export const stress = {
  scenarios: () => request<any[]>('/api/v1/stress/scenarios'),
  results: (portfolioId: string) =>
    request<any[]>(`/api/v1/stress/results/${portfolioId}`),
}

// ── Agents ────────────────────────────────────────────────────
export const agents = {
  runAllScores: () =>
    request<any>('/api/v1/agents/score/run-all', { method: 'POST' }),
  runScore: (counterpartyId: string) =>
    request<any>(`/api/v1/agents/score/${counterpartyId}`, { method: 'POST' }),
}
