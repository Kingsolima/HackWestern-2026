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
/** Declared in the catalog, payload models not written yet; kept so they don't break the UI. */
export type PendingEvent = Envelope<
  'check_result' | 'design_ready' | 'advocate' | 'synthesis',
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
  | PendingEvent

/** GET/POST /api/jobs response (backend/app/api/jobs.py JobStatus). */
export interface JobStatus {
  job_id: string
  mode: JobMode
  stage: Stage
  created_at: string
  events: number
}
