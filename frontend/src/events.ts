// Job event contract. Mirrors backend/app/orchestrator/events.py (one model per type) and the
// Claim / Source / ComplianceCard shapes it references. Change both sides together.
//
// Every SSE message is `{id, type, job_id, ts, data}` on the plain `onmessage` channel. The
// server replays from Last-Event-ID, which the browser sends on reconnect.

import type { ComplianceCard } from './types'

export type Stage =
  | 'CREATED'
  | 'COMPLIANCE_BASELINE'
  | 'PLAN'
  | 'DISCOVER'
  | 'TRIAGE'
  | 'EXTRACT'
  | 'VERIFY'
  | 'CHECK'
  | 'RANK'
  | 'BUILD'
  | 'REPORT'
  | 'DONE'
  | 'DEGRADED'
  | 'FAILED'

export const TERMINAL_STAGES: ReadonlySet<Stage> = new Set(['DONE', 'DEGRADED', 'FAILED'])

/** The happy-path order, for the stage stepper. */
export const STAGE_ORDER: readonly Stage[] = [
  'COMPLIANCE_BASELINE',
  'PLAN',
  'DISCOVER',
  'TRIAGE',
  'EXTRACT',
  'VERIFY',
  'CHECK',
  'RANK',
  'BUILD',
  'REPORT',
  'DONE',
]

export type JobMode = 'live' | 'replay' | 'mixed'
export type Product = 'search' | 'fetch' | 'agent' | 'browser' | 'monitor' | 'gemini'
export type Outcome =
  | 'success'
  | 'blocked'
  | 'not_found'
  | 'auth_required'
  | 'incomplete'
  | 'error'

export interface Source {
  url: string
  kind: 'page' | 'pdf'
  fetched_at: string
  html_key: string | null
  via: 'tinyfetch' | 'tinyagent' | 'replay'
}

export interface Claim {
  id: string
  candidate_id: string
  field: string
  raw_value: string
  raw_unit: string | null
  quote: string
  source: Source
  si_value: number | null
  extracted_by: 'tinyagent' | 'gemini_text' | 'gemini_vision'
  verified: boolean
  verify_method: 'html_quote' | 'pdf_text' | 'none'
}

interface Envelope<T extends string, D> {
  id: number
  type: T
  job_id: string
  ts: string
  data: D
}

export type StageEvent = Envelope<'stage', { stage: Stage }>
export type RunStartedEvent = Envelope<
  'run_started',
  {
    run_id: string
    worker: string
    product: Product
    site: string
    url: string | null
    goal: string | null
    live: boolean
  }
>
export type RunStreamingUrlEvent = Envelope<
  'run_streaming_url',
  { run_id: string; streaming_url: string }
>
export type RunProgressEvent = Envelope<'run_progress', { run_id: string; purpose: string }>
export type RunFinishedEvent = Envelope<
  'run_finished',
  { run_id: string; outcome: Outcome; reason: string; duration_s: number; live: boolean }
>
export type ClaimVerifiedEvent = Envelope<'claim_verified', { claim: Claim }>
export type ClaimRejectedEvent = Envelope<'claim_rejected', { claim: Claim; reason: string }>
export type ComplianceEvent = Envelope<'compliance', { card: ComplianceCard }>
export type ErrorEvent = Envelope<'error', { message: string; stage: Stage | null }>

/** CAD worker fit numbers for one design (cad/cad_worker/robot.py measure()). */
export interface DesignFit {
  flange_mm?: number
  ground_clearance_mm?: number
  fit_ground?: boolean
  needs_hub_adapter?: boolean
  shaft_diameter_mm?: number
  wheel_bore_mm?: number
  bracket?: {
    thickness_mm?: number
    width_mm?: number
    height_mm?: number
    foot_len_mm?: number
    bolt_spacing_mm?: number
    pilot_hole_mm?: number
  }
  [key: string]: unknown
}

export interface Design {
  design_id: string
  role: 'baseline' | 'candidate'
  label: string
  motor: string
  frame: string
  /** Path on the CAD worker (/designs/{id}/glb); the UI fetches it through the /cad proxy. */
  glb_url: string
  step_url: string
  fit: DesignFit
}
export type DesignReadyEvent = Envelope<'design_ready', Design>
// --- v4 supply-risk events (docs/BUILD-PLAN-v4.md §4). Additive: a job without them renders as
// before. Envelopes follow the existing pattern ({claim}, {card}): one named object per event.

export type Domain = 'actuation' | 'sensing' | 'compute' | 'power' | 'structure' | 'other'
export type Level = 'low' | 'medium' | 'high' | 'unknown'
export type FactBasis = 'verified' | 'stated'
export type OriginTier = 'T1' | 'T2' | 'T3' | 'rejected' | 'none'
export type Availability = 'in_stock' | 'lead_time' | 'out_of_stock' | 'unknown'
export type Verdict = 'pass' | 'review' | 'rejected'

export interface ProjectFacts {
  sells_to_us_federal: boolean | null
  deploy_countries: string[]
  uptime_critical: boolean | null
  budget_usd: number | null
  need_by_days: number | null
}

export interface Fact {
  field: string
  value: string
  basis: FactBasis
  claim_id: string | null
}

export interface BomLine {
  id: string
  domain: Domain
  qty: number
  part: string
  manufacturer: string | null
  unit_price_usd: number | null
  origin_country: string | null
  origin_tier: OriginTier | null
  availability: Availability
  lead_time_days: number | null
  illustrative: boolean
  sources: Source[]
}

export interface Project {
  id: string
  kind: 'company' | 'club'
  name: string
  robot: string
  use_case: string
  robot_kind: 'wheeled' | 'arm'
  robot_params: Record<string, unknown>
  deep_line: string
  bom: BomLine[]
  facts: ProjectFacts
  fact_basis: Fact[]
}

export interface CriterionReason {
  rule_id: string
  fact_field: string | null
  text: string
}

export interface Criteria {
  objectives: string[]
  /** Fraction (0.65), set only when a rule switches the domestic objective on. */
  domestic_threshold: number | null
  max_lead_time_days: number | null
  blocking_lists: string[]
  reasons: CriterionReason[]
}

export type RiskFactorName = 'sources' | 'bottleneck' | 'trade' | 'restricted' | 'availability'
export const RISK_FACTORS: readonly RiskFactorName[] = [
  'sources',
  'bottleneck',
  'trade',
  'restricted',
  'availability',
]

export interface RiskFactor {
  name: RiskFactorName
  level: Level
  value: string
  reason: string
  source_urls: string[]
}

export interface LineRisk {
  line_id: string
  factors: RiskFactor[]
  overall: Level
}

export interface Alternative {
  id: string
  line_id: string
  manufacturer: string
  part_number: string
  origin_country: string | null
  origin_tier: OriginTier | null
  unit_price_usd: number | null
  availability: Availability
  lead_time_days: number | null
  /** Spec-check verdict; null for lines the agents did not go deep on. */
  verdict: Verdict | null
  risk: LineRisk
  /** True when a live agent found it; false for a research row. */
  live: boolean
}

export interface Recommendation {
  line_id: string
  action: 'keep' | 'dual_source' | 're_source'
  alternative_id: string | null
  cost_delta_usd: number | null
  risk_before: Level
  risk_after: Level
  reason: string
}

export type ProjectEvent = Envelope<'project', { project: Project; criteria: Criteria }>
export type RiskLineEvent = Envelope<'risk_line', { risk: LineRisk; line: BomLine }>
export type AlternativeEvent = Envelope<'alternative', { alternative: Alternative }>
export type RecommendationEvent = Envelope<'recommendation', { recommendation: Recommendation }>

/** Declared in the catalog, payload models not written yet; kept so they don't break the UI. */
export type PendingEvent = Envelope<
  'check_result' | 'advocate' | 'synthesis',
  Record<string, unknown>
>

export type JobEvent =
  | StageEvent
  | RunStartedEvent
  | RunStreamingUrlEvent
  | RunProgressEvent
  | RunFinishedEvent
  | ClaimVerifiedEvent
  | ClaimRejectedEvent
  | ComplianceEvent
  | ErrorEvent
  | DesignReadyEvent
  | ProjectEvent
  | RiskLineEvent
  | AlternativeEvent
  | RecommendationEvent
  | PendingEvent

/** GET/POST /api/jobs response (backend/app/api/jobs.py JobStatus). */
export interface JobStatus {
  job_id: string
  mode: JobMode
  stage: Stage
  created_at: string
  events: number
}
