import { describe, expect, it } from 'vitest'
import type { Alternative, BomLine, Claim, JobEvent, Level, LineRisk, Recommendation } from './events'
import {
  applyEvent,
  createJob,
  domesticShare,
  followJob,
  initialJobState,
  isTerminal,
  rankRecommendations,
  type JobState,
} from './job'
import type { Robot } from './types'

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

describe('check_result', () => {
  const check = (candidate_id: string, name: string, verdict: 'pass' | 'fail' | 'review') => ({
    candidate_id,
    check: name,
    verdict,
    value: 0.5,
    threshold: 0.3,
    unit: 'N·m',
    margin: 0.2,
    claim_ids: [],
    note: '',
  })

  it('groups checks by candidate and lets a later result replace the same check', () => {
    const state = fold([
      ev('check_result', { check: check('c1', 'torque_cont', 'review') }),
      ev('check_result', { check: check('c1', 'speed', 'pass') }),
      ev('check_result', { check: check('c2', 'torque_cont', 'fail') }),
      ev('check_result', { check: check('c1', 'torque_cont', 'pass') }),
    ])
    expect(Object.keys(state.checks)).toEqual(['c1', 'c2'])
    expect(state.checks.c1.map((c) => [c.check, c.verdict])).toEqual([
      ['speed', 'pass'],
      ['torque_cont', 'pass'],
    ])
    expect(state.checks.c2).toHaveLength(1)
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
    await createJob('live', { liveToken: 'tok' }, fetchImpl)
    await createJob('replay', { liveToken: 'tok' }, fetchImpl)
    expect(header(calls[0])).toBe('tok')
    expect(header(calls[1])).toBeUndefined()
  })

  it('surfaces a refused live job as an error', async () => {
    const fetchImpl = (async () => new Response('{"detail":"live jobs need a valid X-Live-Token"}', { status: 403 })) as unknown as typeof fetch
    await expect(createJob('live', { liveToken: 'bad' }, fetchImpl)).rejects.toThrow('403')
  })

  it('sends the onboarded company facts, but not on top of a preset project', async () => {
    const { calls, fetchImpl } = capture()
    const company = [{ field: 'company_name', label: 'Name', value: 'Example Robotics', quote: '' }]
    await createJob('replay', { company }, fetchImpl)
    await createJob('replay', { company, projectId: 'ar4_club' }, fetchImpl)
    expect(JSON.parse(calls[0].body as string).company).toEqual(company)
    expect(JSON.parse(calls[1].body as string).company).toBeUndefined()
  })

  it('sends project_id only when a project is picked', async () => {
    const { calls, fetchImpl } = capture()
    await createJob('replay', {}, fetchImpl)
    await createJob('replay', { projectId: 'ar4_club' }, fetchImpl)
    expect(JSON.parse(calls[0].body as string)).toEqual({ mode: 'replay' })
    expect(JSON.parse(calls[1].body as string)).toEqual({ mode: 'replay', project_id: 'ar4_club' })
  })

  it('sends the onboarding robot when there is one', async () => {
    const { calls, fetchImpl } = capture()
    const robot = { name: 'Tote bot', final_assembly_country: 'US', requirements: { mass_kg: 5 }, bom: [] } as unknown as Robot
    await createJob('mixed', { liveToken: 'tok', robot }, fetchImpl)
    expect(JSON.parse(calls[0].body as string)).toEqual({ mode: 'mixed', robot })
    expect(header(calls[0])).toBe('tok')
  })
})

const line = (id: string, over: Partial<BomLine> = {}): BomLine => ({
  id,
  domain: 'actuation',
  qty: 1,
  part: `part ${id}`,
  manufacturer: null,
  unit_price_usd: 100,
  origin_country: 'CN',
  origin_tier: 'none',
  availability: 'in_stock',
  lead_time_days: null,
  illustrative: false,
  sources: [],
  ...over,
})
const risk = (lineId: string, overall: Level): LineRisk => ({ line_id: lineId, factors: [], overall })
const rec = (lineId: string, before: Level, after: Level, cost: number | null): Recommendation => ({
  line_id: lineId,
  action: 're_source',
  alternative_id: `${lineId}-alt`,
  cost_delta_usd: cost,
  risk_before: before,
  risk_after: after,
  reason: '',
})
const alt = (id: string, lineId: string, price: number): Alternative => ({
  id,
  line_id: lineId,
  manufacturer: 'Teknic',
  part_number: id,
  origin_country: 'US',
  origin_tier: 'T1',
  unit_price_usd: price,
  availability: 'in_stock',
  lead_time_days: null,
  verdict: null,
  risk: risk(lineId, 'low'),
  live: true,
})

describe('v4 supply-risk events', () => {
  it('stores the project and its criteria', () => {
    const s = fold([
      ev('project', {
        project: {
          id: 'ar4_club',
          kind: 'club',
          name: 'Western robotics club',
          robot: 'AR4',
          use_case: 'teaching arm',
          robot_kind: 'arm',
          cad_robot: 'ar4',
          robot_params: {},
          deep_line: 'j2_motor',
          bom: [],
          facts: {
            sells_to_us_federal: null,
            deploy_countries: ['CA'],
            uptime_critical: null,
            budget_usd: 2000,
            need_by_days: 30,
          },
          fact_basis: [{ field: 'budget_usd', value: '2000', basis: 'stated', claim_id: null }],
        },
        criteria: {
          objectives: ['performance', 'cost'],
          domestic_threshold: null,
          max_lead_time_days: 30,
          blocking_lists: [],
          reasons: [],
        },
      }),
    ])
    expect(s.project?.id).toBe('ar4_club')
    expect(s.criteria?.max_lead_time_days).toBe(30)
  })

  it('keeps one risk row per BOM line, in arrival order, the latest winning', () => {
    const s = fold([
      ev('risk_line', { line: line('a'), risk: risk('a', 'high') }),
      ev('risk_line', { line: line('b'), risk: risk('b', 'low') }),
      ev('risk_line', { line: line('a'), risk: risk('a', 'medium') }),
    ])
    expect(s.riskLines.map((r) => [r.line.id, r.risk.overall])).toEqual([
      ['a', 'medium'],
      ['b', 'low'],
    ])
  })

  it('groups alternatives by line and drops repeats of the same id', () => {
    const s = fold([
      ev('alternative', { alternative: alt('x1', 'a', 10) }),
      ev('alternative', { alternative: alt('x2', 'a', 20) }),
      ev('alternative', { alternative: alt('x1', 'a', 15) }),
      ev('alternative', { alternative: alt('y1', 'b', 5) }),
    ])
    expect(s.alternatives.a.map((a) => [a.id, a.unit_price_usd])).toEqual([
      ['x2', 20],
      ['x1', 15],
    ])
    expect(s.alternatives.b).toHaveLength(1)
  })

  it('ranks recommendations by levels dropped, then cheaper first', () => {
    const s = fold([
      ev('recommendation', { recommendation: rec('keep', 'low', 'low', 0) }),
      ev('recommendation', { recommendation: rec('one', 'high', 'medium', 5) }),
      ev('recommendation', { recommendation: rec('two', 'high', 'low', 50) }),
      ev('recommendation', { recommendation: rec('one-cheap', 'medium', 'low', -10) }),
    ])
    expect(s.recommendations.map((r) => r.line_id)).toEqual(['two', 'one-cheap', 'one', 'keep'])
  })

  it('does not count unknown levels as a drop, and puts unknown cost last', () => {
    const ranked = rankRecommendations([
      rec('unknown', 'unknown', 'low', -100),
      rec('nocost', 'medium', 'low', null),
      rec('cost', 'medium', 'low', 30),
    ])
    expect(ranked.map((r) => r.line_id)).toEqual(['cost', 'nocost', 'unknown'])
  })

  it('replaces a line recommendation instead of listing it twice', () => {
    const s = fold([
      ev('recommendation', { recommendation: rec('a', 'high', 'high', 0) }),
      ev('recommendation', { recommendation: rec('a', 'high', 'low', 0) }),
    ])
    expect(s.recommendations).toHaveLength(1)
    expect(s.recommendations[0].risk_after).toBe('low')
  })
})

describe('domesticShare', () => {
  it('weighs by cost and counts only US lines at T1/T2', () => {
    const share = domesticShare([
      line('us', { origin_country: 'US', origin_tier: 'T1', unit_price_usd: 300 }),
      line('us-t3', { origin_country: 'US', origin_tier: 'T3', unit_price_usd: 100 }),
      line('cn', { qty: 2, unit_price_usd: 50 }),
      line('unpriced', { unit_price_usd: null }),
    ])
    expect(share).toEqual({ pct: 60, unpriced: 1 })
  })

  it('is null when nothing has a price', () => {
    expect(domesticShare([line('a', { unit_price_usd: null })])).toBeNull()
  })
})
