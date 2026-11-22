// Job view state. The UI is a pure function of the event log: `applyEvent` folds one event
// into the state, and `useJob` feeds it from the SSE stream.

import { useCallback, useEffect, useReducer, useRef } from 'react'
import type { Claim, Design, JobEvent, JobMode, JobStatus, Outcome, Stage } from './events'
import { TERMINAL_STAGES } from './events'
import type { ComplianceCard } from './types'

const BASE = import.meta.env.VITE_API_URL ?? ''

export interface Run {
  runId: string
  worker: string
  site: string
  url: string | null
  /** False for a replayed run: its streaming URL points at a browser that no longer exists. */
  live: boolean
  streamingUrl: string | null
  steps: string[]
  outcome: Outcome | null
  reason: string | null
}

export interface ClaimRow {
  claim: Claim
  verified: boolean
  reason: string | null
}

export interface JobState {
  jobId: string | null
  mode: JobMode | null
  stage: Stage | null
  lastEventId: number
  runs: Record<string, Run>
  runOrder: string[]
  claims: ClaimRow[]
  compliance: ComplianceCard | null
  /** The robot before the swap, and each redesigned candidate (one per tournament entry). */
  baseline: Design | null
  candidates: Design[]
  errors: string[]
  connection: 'idle' | 'starting' | 'streaming' | 'closed' | 'failed'
}

export const initialJobState: JobState = {
  jobId: null,
  mode: null,
  stage: null,
  lastEventId: 0,
  runs: {},
  runOrder: [],
  claims: [],
  compliance: null,
  baseline: null,
  candidates: [],
  errors: [],
  connection: 'idle',
}

export function isTerminal(state: JobState): boolean {
  return state.stage !== null && TERMINAL_STAGES.has(state.stage)
}

function updateRun(state: JobState, runId: string, patch: Partial<Run>): JobState {
  const run = state.runs[runId]
  if (!run) return state // event for a run we never saw start; ignore rather than invent one
  return { ...state, runs: { ...state.runs, [runId]: { ...run, ...patch } } }
}

/** Fold one event into the state. Events at or below lastEventId are duplicates from a resume. */
export function applyEvent(prev: JobState, ev: JobEvent): JobState {
  if (ev.id <= prev.lastEventId) return prev
  const state = { ...prev, lastEventId: ev.id }

  switch (ev.type) {
    case 'stage':
      return { ...state, stage: ev.data.stage }
    case 'run_started': {
      const d = ev.data
      const run: Run = {
        runId: d.run_id,
        worker: d.worker,
        site: d.site,
        url: d.url,
        live: d.live,
        streamingUrl: null,
        steps: [],
        outcome: null,
        reason: null,
      }
      return {
        ...state,
        runs: { ...state.runs, [d.run_id]: run },
        runOrder: state.runOrder.includes(d.run_id) ? state.runOrder : [...state.runOrder, d.run_id],
      }
    }
    case 'run_streaming_url':
      return updateRun(state, ev.data.run_id, { streamingUrl: ev.data.streaming_url })
    case 'run_progress': {
      const run = state.runs[ev.data.run_id]
      return run ? updateRun(state, run.runId, { steps: [...run.steps, ev.data.purpose] }) : state
    }
    case 'run_finished':
      return updateRun(state, ev.data.run_id, {
        outcome: ev.data.outcome,
        reason: ev.data.reason,
        live: ev.data.live,
      })
    case 'claim_verified':
      return { ...state, claims: [...state.claims, { claim: ev.data.claim, verified: true, reason: null }] }
    case 'claim_rejected':
      return {
        ...state,
        claims: [...state.claims, { claim: ev.data.claim, verified: false, reason: ev.data.reason }],
      }
    case 'compliance':
      return { ...state, compliance: ev.data.card }
    case 'error':
      return { ...state, errors: [...state.errors, ev.data.message] }
    case 'design_ready':
      return ev.data.role === 'baseline'
        ? { ...state, baseline: ev.data }
        : { ...state, candidates: [...state.candidates, ev.data] }
    default:
      return state // check_result, advocate, synthesis: not rendered yet
  }
}

type Action =
  | { kind: 'reset' }
  | { kind: 'started'; status: JobStatus }
  | { kind: 'event'; event: JobEvent }
  | { kind: 'connection'; connection: JobState['connection'] }
  | { kind: 'failed'; message: string }

function reducer(state: JobState, action: Action): JobState {
  switch (action.kind) {
    case 'reset':
      return { ...initialJobState, connection: 'starting' }
    case 'started':
      return {
        ...state,
        jobId: action.status.job_id,
        mode: action.status.mode,
        stage: action.status.stage,
        connection: 'streaming',
      }
    case 'event': {
      const next = applyEvent(state, action.event)
      return isTerminal(next) ? { ...next, connection: 'closed' } : next
    }
    case 'connection':
      return { ...state, connection: action.connection }
    case 'failed':
      return { ...state, connection: 'failed', errors: [...state.errors, action.message] }
  }
}

/**
 * Start a job and follow its events.
 *
 * EventSource reconnects on its own (resuming via Last-Event-ID), including after the server
 * ends the stream when the job finishes. That would loop forever, so we close it ourselves as
 * soon as the job reaches a terminal stage.
 */
export function useJob() {
  const [state, dispatch] = useReducer(reducer, initialJobState)
  const source = useRef<EventSourceLike | null>(null)

  const stop = useCallback(() => {
    source.current?.close()
    source.current = null
  }, [])

  useEffect(() => stop, [stop]) // close on unmount

  const start = useCallback(
    async (mode: JobMode = 'replay', liveToken?: string) => {
      stop()
      dispatch({ kind: 'reset' })
      let status: JobStatus
      try {
        status = await createJob(mode, liveToken)
      } catch (e) {
        dispatch({ kind: 'failed', message: `could not start job: ${String(e)}` })
        return
      }
      dispatch({ kind: 'started', status })

      const es = followJob(
        `${BASE}/api/jobs/${status.job_id}/events`,
        (event) => dispatch({ kind: 'event', event }),
        () => dispatch({ kind: 'connection', connection: 'failed' }),
      )
      source.current = es
    },
    [stop],
  )

  return { state, start, stop }
}

/**
 * POST /api/jobs. On the public deploy, live/mixed jobs need the X-Live-Token header (they spend
 * TinyFish credit); replay jobs never send it. `fetchImpl` is injectable for tests.
 */
export async function createJob(
  mode: JobMode,
  liveToken?: string,
  fetchImpl: typeof fetch = fetch,
): Promise<JobStatus> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (mode !== 'replay' && liveToken) headers['X-Live-Token'] = liveToken
  const res = await fetchImpl(`${BASE}/api/jobs`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ mode }),
  })
  if (!res.ok) throw new Error(`${res.status} ${(await res.text()).slice(0, 200)}`)
  return (await res.json()) as JobStatus
}

type EventSourceLike = Pick<EventSource, 'onmessage' | 'onerror' | 'readyState' | 'close'>

/**
 * Open the job's event stream, pass each event on, and close the stream at a terminal stage
 * (otherwise the browser reconnects to the finished job forever). `makeSource` is injectable
 * for tests.
 */
export function followJob(
  url: string,
  onEvent: (event: JobEvent) => void,
  onFailed: () => void,
  makeSource: (url: string) => EventSourceLike = (u) => new EventSource(u),
): EventSourceLike {
  const es = makeSource(url)
  es.onmessage = (msg: MessageEvent<string>) => {
    const event = JSON.parse(msg.data) as JobEvent
    onEvent(event)
    if (event.type === 'stage' && TERMINAL_STAGES.has(event.data.stage)) es.close()
  }
  es.onerror = () => {
    // readyState CONNECTING (0) = the browser is retrying and will resume from the last id.
    if (es.readyState === 2) onFailed()
  }
  return es
}
