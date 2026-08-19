/** Shapes served by radar.api. Mirrors radar/readmodel.py. */

export interface VocabItem {
  id: string
  label: string
  definition: string
}

export interface RoleMode {
  id: string
  label: string
  description: string
  primary_action: string
  link_types: string[]
  acceptance?: string
  ranking: Record<string, number>
}

export interface LinkTypeInfo {
  id: string
  meaning: string
  definition: string
  owner: string
  action: string
}

export interface Meta {
  verticals: VocabItem[]
  use_cases: VocabItem[]
  technologies: VocabItem[]
  domains: VocabItem[]
  personas: VocabItem[]
  signal_types: VocabItem[]
  horizons: string[]
  states: string[]
  link_types: LinkTypeInfo[]
  roles: RoleMode[]
  weight_set: string
  sorts?: { id: SortId; label: string }[]
  sizing_version?: string
  competitor_register_version?: string
  competition_levels?: { id: string; meaning: string }[]
  attractiveness_weights: Record<string, number>
  right_to_win_weights: Record<string, number>
  pipeline_version: string
  last_refresh: RefreshRow | null
  strategy: {
    plan: string
    period: string
    ambitions: { id: string; label: string; implication: string }[]
    privileged_verticals: Record<string, number>
  }
}

export interface RefreshRow {
  id: string
  started_at: string
  finished_at: string | null
  reference_date: string
  is_replay: number
  weight_set?: string
  pipeline_version?: string
}

export interface ScoreBlock {
  score: number
  components: Record<string, number>
  /** Present only on the detail endpoint — the raw inputs behind each component (DR-05). */
  inputs: Record<string, any> | null
  weight_set: string
  computed_at: string
}

export interface Claim {
  claim: string
  signals: string[]
}

export interface TopicLink {
  node_id: string
  node_type: string
  label: string
  link_type: string
  link_meaning: string
  owner: string
  action: string
  confidence: number
  evidence: Record<string, any>
  confirmed_by: string | null
}

export interface Signal {
  id: string
  title: string
  url: string
  publisher: string
  published_at: string
  signal_type: string | null
  tier: number
  extract: string
  language: string
  geographies: string[]
}

export interface WorkflowState {
  stage: string
  stage_label: string
  owner_role: string | null
  owner: string | null
  entered_stage_at: string | null
  age_in_stage_days: number
  stalled: boolean
  note: string | null
  next_stage: string | null
}

export interface ConvictionAxis {
  label: string
  score: number
  raw_mean: number
  n: number
  rater_spread: number
  contested: boolean
  voices: { role: string; rating: number; confidence: number; rationale: string | null; author: string; at: string }[]
}

export interface Conviction {
  assessed: number
  axes: Record<string, ConvictionAxis>
  score: number | null
  roles_responded: string[]
  roles_missing: string[]
  sufficient: boolean
}

export interface Divergence {
  review_trigger: boolean
  flags: {
    axis: string; axis_label: string; internal: number; external: number
    external_label: string; delta: number; direction: string; reading: string
  }[]
}

/** §4.3.4 market sizing. Every figure is computed; `factors` carries the
 *  working, so the UI can show where each number came from rather than asking
 *  the reader to trust it. */
export interface SizeFactor {
  name: string
  label: string
  value: number
  unit: string
  basis: 'observed' | 'proxy' | 'assumption'
  low: number | null
  high: number | null
  source: {
    publisher?: string; dataset?: string; indicator?: string
    url?: string; period?: string; updated?: string; licence?: string; owner?: string
  }
  detail: Record<string, any>
  note: string
}

export interface SizeBand { low: number | null; base: number | null; high: number | null }

export interface MarketSize {
  method: 'bottom_up_adoption' | 'procurement_observed'
  method_label: string
  currency: string
  tam: SizeBand
  sam: SizeBand
  som: SizeBand
  confidence: 'observed' | 'partial' | 'modelled'
  factors: SizeFactor[]
  coverage: Record<string, any>
  caveats: string[]
  sizing_version: string
  computed_at: string
}

export interface CompetitorMention {
  signal_id: string
  publisher: string
  published_at: string
  url: string
  title: string
  quote: string
}

export interface Competitor {
  id: string
  label: string
  type: string
  type_label: string
  relationship: 'competitor' | 'partner' | 'both'
  partner_id?: string | null
  basis: 'evidenced' | 'structural'
  why: string
  note?: string
  mentions: CompetitorMention[]
  contribution: number
}

/** §4.3.3 — a FOURTH quantity beside attractiveness, right to win and
 *  conviction, never folded into any of them. */
export interface Competition {
  level: 'none' | 'low' | 'medium' | 'high'
  level_label: string
  meaning: string
  score: number
  competitors: Competitor[]
  counts: { listed: number; evidenced: number; partners_who_also_compete: number; total?: number }
  inputs: Record<string, any>
  register_version: string
  computed_at: string
}

export interface DiagramNode { label: string; provider: 'orange' | 'partner' | 'customer' | 'third_party' }
export interface DiagramLayer { label: string; nodes: DiagramNode[] }
export interface SolutionDiagram {
  title: string
  caption: string
  layers: DiagramLayer[]
  flows: { from: string; to: string; label: string }[]
}

export interface TopicDescription {
  sections: Record<string, { text: string; signals: string[] }>
  section_order: string[]
  section_titles: Record<string, string>
  qualifying_questions: string[]
  objection_handling: { objection: string; response: string }[]
  diagram: SolutionDiagram | null
  stripped: { section: string; reason: string }[]
  generated_at: string
  topic_version: number
  stale: boolean
  provenance: Record<string, string>
}

export interface BriefMeta {
  topic_id: string
  generated_at?: string
  topic_version?: number
  filename?: string
  bytes?: number
  content_hash?: string
  exists: boolean
  stale?: boolean
  /** Which kind of staleness — the topic, the narrative, the sizing or the file. */
  stale_reason?: string | null
  weight_set?: string
  sizing_version?: string
  prompt_version?: string
  model_version?: string
  url?: string
  description_available?: boolean
}

export interface Topic {
  id: string
  version: number
  triple: { vertical: string; use_case: string; technology: string }
  labels: { vertical: string; use_case: string; technology: string }
  statement: string
  domains: string[]
  domain_labels: string[]
  personas: string[]
  persona_labels: string[]
  geographies: string[]
  state: string
  state_reason: string
  horizon: string | null
  horizon_basis: string | null
  why_hot: Claim[]
  next_actions: Record<string, string>
  attractiveness: ScoreBlock | null
  right_to_win: ScoreBlock | null
  portfolio_distance: number
  link_types: string[]
  links: TopicLink[]
  evidence_gap_warning: boolean
  reference_density: Record<string, any>
  critic_score: number | null
  first_seen: string
  last_refresh: string
  signal_count: number
  signals?: Signal[]
  /** Detail endpoint only. */
  market_size?: MarketSize[]
  description?: TopicDescription | null
  brief?: BriefMeta | null
  /** List rows carry the headline figure only. */
  market_size_summary?: {
    method: string; sam_base: number | null; tam_base: number | null; confidence: string
  } | null
  competition?: Competition | null
  /** List rows only — so a row can say whether the brief exists before you click. */
  has_description?: boolean
  has_brief?: boolean
  workflow?: WorkflowState | null
  conviction?: Conviction | null
  divergence?: Divergence | null
  provenance: Record<string, string | null>
  rank_score?: number
  rank_explanation?: Record<string, { value: number; weight: number; contribution: number }>
  exploration_slot?: boolean
  strategist_flag?: string
}

export interface RadarView {
  role: string
  role_label: string
  primary_action: string
  filters: Record<string, unknown>
  total_matching: number
  /** Server-computed counts per filter value, over the whole role-eligible set. */
  facets: Record<string, Record<string, number>>
  sort: SortId
  cap: number
  topics: Topic[]
  exploration: Topic[]
  last_refresh: RefreshRow | null
  weight_set: string
}

export interface Coverage {
  languages: Record<string, number>
  tiers: Record<string, number>
  signal_types: Record<string, number>
  sources: Record<string, number>
  geographies: Record<string, number>
  topics_per_vertical: Record<string, number>
}

export type FilterState = {
  vertical: string[]
  domain: string[]
  persona: string[]
  geography: string[]
  horizon: string[]
  /** §4.3.3 — filter on how crowded the field is. */
  competition: string[]
  /** FR-18 — "what can I actually take to a meeting tomorrow". */
  has_brief: boolean
  q: string
}

export const EMPTY_FILTERS: FilterState = {
  vertical: [], domain: [], persona: [], geography: [], horizon: [],
  competition: [], has_brief: false, q: '',
}

/** Orderings the API offers beyond the role's own ranking function (FR-13). */
export type SortId = 'rank' | 'market_size' | 'attractiveness' | 'right_to_win'
  | 'competition' | 'signals' | 'recent'
