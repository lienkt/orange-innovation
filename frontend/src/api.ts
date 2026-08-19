import type { BriefMeta, Competition, Coverage, FilterState, MarketSize, Meta, RadarView, Topic, TopicDescription } from './types'

const BASE = '/api'

async function get<T>(path: string, params?: Record<string, string | string[] | undefined>): Promise<T> {
  const url = new URL(BASE + path, window.location.origin)
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value === undefined || value === '') continue
    // Multi-select filters repeat the key — FastAPI reads them as a list (AC-04).
    if (Array.isArray(value)) value.forEach((v) => url.searchParams.append(key, v))
    else url.searchParams.set(key, value)
  }
  const res = await fetch(url.toString())
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new Error(`${res.status} ${res.statusText} — ${body.slice(0, 200)}`)
  }
  return res.json() as Promise<T>
}

async function post<T>(path: string): Promise<T> {
  const res = await fetch(BASE + path, { method: 'POST' })
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    // The API puts the real reason in `detail` — a model failure, a missing
    // key — and swallowing it would leave the user with "500".
    let message = body.slice(0, 300)
    try { message = JSON.parse(body).detail ?? message } catch { /* not JSON */ }
    throw new Error(message || `${res.status} ${res.statusText}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  meta: () => get<Meta>('/meta'),

  view: (role: string, filters: FilterState, limit?: number | null, sort?: string) =>
    get<RadarView>('/view', {
      role,
      limit: limit ? String(limit) : undefined,
      sort: sort && sort !== 'rank' ? sort : undefined,
      vertical: filters.vertical,
      domain: filters.domain,
      persona: filters.persona,
      geography: filters.geography,
      horizon: filters.horizon,
      competition: filters.competition,
      has_brief: filters.has_brief ? 'true' : undefined,
      q: filters.q || undefined,
    }),

  topic: (id: string) => get<Topic>(`/topics/${id}`),

  marketSize: (id: string) => get<{ topic_id: string; estimates: MarketSize[] }>(`/topics/${id}/market-size`),

  competition: (id: string) => get<Competition>(`/topics/${id}/competition`),

  /** §4.3.4 reference data vintage — the UI shows how old the denominators are. */
  referenceData: () => get<{ count: number; series: Record<string, any>[] }>('/reference-data'),

  /** Generation is a POST because it writes a derived artefact. Both calls are
   *  slow enough (one model call) that callers show a pending state. */
  generateDescription: (id: string, force = false) =>
    post<TopicDescription>(`/topics/${id}/description${force ? '?force=true' : ''}`),

  brief: (id: string) => get<BriefMeta>(`/topics/${id}/brief`),

  generateBrief: (id: string, force = false) =>
    post<BriefMeta>(`/topics/${id}/brief${force ? '?force=true' : ''}`),

  /** Cache-busted so a regenerated brief is never served from the iframe cache. */
  briefUrl: (id: string, version?: string) =>
    `${BASE}/topics/${id}/brief.pdf${version ? `?v=${encodeURIComponent(version)}` : ''}`,

  briefDownloadUrl: (id: string) => `${BASE}/topics/${id}/brief.pdf?download=1`,

  whitespace: (filters?: FilterState) =>
    get<{ count: number; total_unfiltered: number; topics: Topic[] }>('/whitespace', {
      vertical: filters?.vertical,
      domain: filters?.domain,
      persona: filters?.persona,
      geography: filters?.geography,
      horizon: filters?.horizon,
      competition: filters?.competition,
      q: filters?.q || undefined,
    }),

  coverage: () => get<Coverage>('/coverage'),

  orphanOffers: () => get<{ count: number; offers: { id: string; label: string }[] }>('/orphan-offers'),

  /** FR-23 / FR-34 / DR-15 — exposure context travels with every event. */
  feedback: (payload: {
    role: string
    kind: 'rating' | 'comparison' | 'override' | 'engagement'
    opportunity_id?: string
    other_opportunity_id?: string
    verdict?: string
    reason?: string
    exposure_context?: Record<string, unknown>
  }) =>
    fetch(`${BASE}/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }).then((r) => r.json()),
}
