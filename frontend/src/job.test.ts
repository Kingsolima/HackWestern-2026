import { describe, expect, it } from 'vitest'
import type { Claim, JobEvent } from './events'
import { applyEvent, createJob, followJob, initialJobState, isTerminal, type JobState } from './job'

let nextId = 1
function ev<T extends JobEvent['type']>(type: T, data: Extract<JobEvent, { type: T }>['data']): JobEvent {
  return { id: nextId++, type, job_id: 'j1', ts: '2026-11-21T00:00:00Z', data } as JobEvent
}

function fold(events: JobEvent[], start: JobState = initialJobState): JobState {
  return events.reduce(applyEvent, start)
}

const claim = (field: string, verified: boolean): Claim => ({
  id: `r1:${field}`,
  candidate_id: 'c1',
  field,
  raw_value: '265',
  raw_unit: 'USD',
  quote: 'Price $265',
  source: { url: 'https://teknic.com/x', kind: 'page', fetched_at: '', html_key: null, via: 'tinyfetch' },
  si_value: null,
  extracted_by: 'tinyagent',
  verified,
  verify_method: verified ? 'html_quote' : 'none',
})

const started = (live: boolean, runId = 'r1') =>
  ev('run_started', {
    run_id: runId,
    worker: 'swap:drive_motor',
    product: 'agent',
    site: 'teknic.com',
    url: 'https://teknic.com',
    goal: null,
    live,
  })

describe('applyEvent', () => {
  it('tracks a run from start to finish', () => {
    const s = fold([
      started(true),
      ev('run_streaming_url', { run_id: 'r1', streaming_url: 'https://stream/1' }),
      ev('run_progress', { run_id: 'r1', purpose: 'Open model list' }),
      ev('run_progress', { run_id: 'r1', purpose: 'Read spec table' }),
      ev('run_finished', { run_id: 'r1', outcome: 'success', reason: 'ok', duration_s: 3, live: true }),
    ])
    expect(s.runOrder).toEqual(['r1'])
    expect(s.runs.r1).toMatchObject({
      live: true,
      streamingUrl: 'https://stream/1',
      steps: ['Open model list', 'Read spec table'],
      outcome: 'success',
    })
  })

  it('keeps a replayed run marked not live, even if it carries a streaming url', () => {
    const s = fold([started(false), ev('run_streaming_url', { run_id: 'r1', streaming_url: 'https://dead' })])
    expect(s.runs.r1.live).toBe(false)
  })

  it('ignores duplicate events replayed after a reconnect', () => {
    const events = [started(true), ev('run_progress', { run_id: 'r1', purpose: 'step' })]
    const once = fold(events)
    const twice = fold(events, once) // the same ids again, as after a Last-Event-ID resume
    expect(twice.runs.r1.steps).toEqual(['step'])
    expect(twice.lastEventId).toBe(once.lastEventId)
  })

  it('ignores events for a run it never saw start', () => {
    const s = fold([ev('run_progress', { run_id: 'ghost', purpose: 'x' })])
    expect(s.runs).toEqual({})
  })

  it('lists verified and rejected claims, with the rejection reason', () => {
    const s = fold([
      ev('claim_verified', { claim: claim('continuous_torque', true) }),
      ev('claim_rejected', { claim: claim('price', false), reason: 'number differs from quote' }),
    ])
    expect(s.claims.map((c) => [c.claim.field, c.verified, c.reason])).toEqual([
      ['continuous_torque', true, null],
      ['price', false, 'number differs from quote'],
    ])
  })

  it('stores the compliance card and errors', () => {
    const card = { domestic_pct: 37.9, thresholds_pct: [65, 75], us_final_assembly: false, supply_risks: [], notes: [] }
    const s = fold([ev('compliance', { card }), ev('error', { message: 'boom', stage: 'EXTRACT' })])
    expect(s.compliance?.domestic_pct).toBe(37.9)
    expect(s.errors).toEqual(['boom'])
  })

  it('is terminal only at DONE, DEGRADED or FAILED', () => {
    expect(isTerminal(fold([ev('stage', { stage: 'VERIFY' })]))).toBe(false)
    for (const stage of ['DONE', 'DEGRADED', 'FAILED'] as const) {
      expect(isTerminal(fold([ev('stage', { stage })]))).toBe(true)
    }
  })

  it('passes through event types it does not render yet', () => {
    const before = fold([started(true)])
    const synthesis: JobEvent = {
      id: nextId++,
      type: 'synthesis',
      job_id: 'j1',
      ts: '2026-11-21T00:00:00Z',
      data: { text: 'later' },
    }
    const after = applyEvent(before, synthesis)
    expect(after.runs).toEqual(before.runs)
  })
})

describe('design_ready', () => {
  const design = (role: 'baseline' | 'candidate', id: string, frame: string) =>
    ev('design_ready', {
      design_id: id,
      role,
      label: id,
      motor: 'm',
      frame,
      glb_url: `/designs/${id}/glb`,
      step_url: `/designs/${id}/step`,
      fit: { bracket: { bolt_spacing_mm: frame === '17' ? 31 : 47.14 } },
    })

  it('keeps the baseline apart from the candidates', () => {
    const s = fold([design('baseline', 'j1-before', '17'), design('candidate', 'j1-after', '23')])
    expect(s.baseline?.design_id).toBe('j1-before')
    expect(s.candidates.map((d) => d.design_id)).toEqual(['j1-after'])
    expect(s.candidates[0].fit.bracket?.bolt_spacing_mm).toBe(47.14)
  })
})

describe('followJob', () => {
  class FakeSource {
    onmessage: ((m: MessageEvent<string>) => void) | null = null
    onerror: (() => void) | null = null
    readyState = 1
    closed = false
    close() {
      this.closed = true
      this.readyState = 2
    }
    send(e: JobEvent) {
      this.onmessage?.({ data: JSON.stringify(e) } as MessageEvent<string>)
    }
  }

  it('closes the stream at DONE so the browser does not reconnect to a finished job', () => {
    const fake = new FakeSource()
    const seen: string[] = []
    followJob('/x', (e) => seen.push(e.type), () => {}, () => fake as unknown as EventSource)
    fake.send(ev('stage', { stage: 'VERIFY' }))
    expect(fake.closed).toBe(false)
    fake.send(ev('stage', { stage: 'DONE' }))
    expect(fake.closed).toBe(true)
    expect(seen).toEqual(['stage', 'stage'])
  })

  it('reports failure only when the browser gives up, not while it is retrying', () => {
    const fake = new FakeSource()
    let failed = 0
    followJob('/x', () => {}, () => failed++, () => fake as unknown as EventSource)
    fake.readyState = 0 // CONNECTING: browser will resume from Last-Event-ID
    fake.onerror?.()
    expect(failed).toBe(0)
    fake.readyState = 2 // CLOSED
    fake.onerror?.()
    expect(failed).toBe(1)
  })
})

describe('createJob', () => {
  const capture = () => {
    const calls: RequestInit[] = []
    const fetchImpl = (async (_url: string, init: RequestInit) => {
      calls.push(init)
      return new Response(JSON.stringify({ job_id: 'j', mode: 'live', stage: 'CREATED', created_at: '', events: 0 }), {
        status: 201,
      })
    }) as unknown as typeof fetch
    return { calls, fetchImpl }
  }
  const header = (init: RequestInit) => (init.headers as Record<string, string>)['X-Live-Token']

  it('sends the live token only for live jobs', async () => {
    const { calls, fetchImpl } = capture()
    await createJob('live', 'tok', fetchImpl)
    await createJob('replay', 'tok', fetchImpl)
    expect(header(calls[0])).toBe('tok')
    expect(header(calls[1])).toBeUndefined()
  })

  it('surfaces a refused live job as an error', async () => {
    const fetchImpl = (async () => new Response('{"detail":"live jobs need a valid X-Live-Token"}', { status: 403 })) as unknown as typeof fetch
    await expect(createJob('live', 'bad', fetchImpl)).rejects.toThrow('403')
  })
})
