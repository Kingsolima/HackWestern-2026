import { describe, expect, it } from 'vitest'
import type { Robot } from '../types'
import {
  applyDrafts,
  loadSaved,
  matchesDemo,
  needsLiveAgents,
  parseSpec,
  saveOnboarded,
  stillMissing,
  toRobot,
  withDefaults,
  type Onboarded,
} from './answers'
import { ApiError, intake, measureCad, type SpecRow } from './intake'
import { QUESTIONS, listOf, type OpenAnswers } from './questions'

const EXAMPLE_ANSWERS: OpenAnswers = { who: 'We are Acme.', market: 'US buyers.', limits: '$600.', drivetrain: '5 kg.' }

// Same values as data/demo_robot.json.
const demo: Robot = {
  name: 'Demo wheeled robot (placeholder values, owner 3 to tune)',
  final_assembly_country: 'CA',
  requirements: {
    mass_kg: 5,
    wheel_radius_m: 0.06,
    n_drive_motors: 2,
    gear_ratio: 1,
    efficiency: 0.9,
    crr: 0.02,
    max_slope_deg: 5,
    accel_mps2: 0.5,
    v_max_mps: 1,
    bus_voltage_v: 24,
    envelope_mm: 90,
    safety_factor: 1.5,
  },
  bom: [{ part: 'Drive motor (NEMA 23)', category: 'motor', qty: 2, unit_cost_usd: '45.00', origin: 'CN' }],
}

const spec = (field: string, robot_field: string, value: number, over: Partial<SpecRow> = {}): SpecRow => ({
  field,
  label: field,
  group: 'Drivetrain',
  unit: '',
  value,
  source: 'default',
  evidence: null,
  default: value,
  live: false,
  ask: null,
  robot_field,
  divisor: 1,
  integer: false,
  allow_zero: false,
  max: null,
  ...over,
})
// The rows the backend sends for the demo robot, cut down to the ones these tests touch.
const demoSpecs = (): SpecRow[] => [
  spec('mass_kg', 'mass_kg', 5, { live: true, ask: 'its total mass with payload' }),
  spec('wheel_radius_mm', 'wheel_radius_m', 60, { live: true, divisor: 1000, ask: 'the drive wheel size' }),
  spec('n_drive_motors', 'n_drive_motors', 2, { live: true, integer: true, source: 'bom', evidence: '2 x Drive motor' }),
  spec('v_max_mps', 'v_max_mps', 1, { ask: 'its top speed' }),
  spec('max_slope_deg', 'max_slope_deg', 5, { live: true, allow_zero: true, max: 60 }),
]
const change = (specs: SpecRow[], field: string, value: number): SpecRow[] =>
  specs.map((s) => (s.field === field ? { ...s, value } : s))
const onboarded = (over: Partial<Onboarded> = {}): Onboarded => ({
  answers: EXAMPLE_ANSWERS,
  bom: demo.bom,
  company: withDefaults([], demo),
  specs: demoSpecs(),
  ...over,
})

describe('toRobot', () => {
  it('gives back exactly the demo requirements for default rows, so the recorded agent goal still matches', () => {
    expect(toRobot(onboarded(), demo).requirements).toEqual(demo.requirements)
  })

  it('carries the confirmed values and facts into the robot', () => {
    const robot = toRobot(
      onboarded({
        specs: change(demoSpecs(), 'wheel_radius_mm', 75),
        company: [
          { field: 'robot_name', label: 'Robot', value: 'Scout', quote: 'We build Scout' },
          { field: 'final_assembly_country', label: 'Final assembly', value: 'us', quote: 'built in Ohio' },
        ],
      }),
      demo,
    )
    expect(robot.name).toBe('Scout')
    expect(robot.final_assembly_country).toBe('US')
    expect(robot.requirements.wheel_radius_m).toBe(0.075)
    expect(robot.requirements.efficiency).toBe(0.9) // no row for it: the demo value stays
    expect(robot.bom).toBe(demo.bom)
  })

  it('falls back to the demo name and country when the answers gave none', () => {
    const robot = toRobot(onboarded({ company: [] }), demo)
    expect(robot.name).toBe('Demo wheeled robot')
    expect(robot.final_assembly_country).toBe('CA')
  })
})

describe('needsLiveAgents', () => {
  it('is true only when a live number differs from the demo', () => {
    expect(needsLiveAgents(demoSpecs())).toBe(false)
    expect(needsLiveAgents(change(demoSpecs(), 'v_max_mps', 3))).toBe(false)
    expect(needsLiveAgents(change(demoSpecs(), 'mass_kg', 20))).toBe(true)
  })
})

describe('matchesDemo', () => {
  it('ignores the name but not the country, the numbers or the BOM', () => {
    const named = [{ field: 'robot_name', label: 'Robot', value: 'Scout', quote: '' }]
    expect(matchesDemo(onboarded({ company: named }), demo)).toBe(true)
    const us = [{ field: 'final_assembly_country', label: 'Final assembly', value: 'US', quote: '' }]
    expect(matchesDemo(onboarded({ company: us }), demo)).toBe(false)
    expect(matchesDemo(onboarded({ specs: change(demoSpecs(), 'v_max_mps', 3) }), demo)).toBe(false)
    expect(matchesDemo(onboarded({ bom: [] }), demo)).toBe(false)
  })
})

describe('review screen', () => {
  it('asks only for specs no file gave us', () => {
    expect(stillMissing(demoSpecs())).toEqual(['its total mass with payload', 'the drive wheel size', 'its top speed'])
  })

  it('adds the robot name and assembly country when the answers did not state them', () => {
    const stated = [{ field: 'robot_name', label: 'Robot', value: 'Scout', quote: 'We build Scout' }]
    expect(withDefaults(stated, demo)).toEqual([
      ...stated,
      { field: 'final_assembly_country', label: 'Final assembly', value: 'CA', quote: '' },
    ])
  })

  it('parseSpec checks a typed value against the row limits', () => {
    const row = { integer: false, allow_zero: false, max: 60 }
    expect(parseSpec(' 12.5 ', row)).toEqual({ ok: true, value: 12.5 })
    expect(parseSpec('0', { ...row, allow_zero: true })).toEqual({ ok: true, value: 0 })
    for (const raw of ['', 'abc', '-3', '0', '61']) expect(parseSpec(raw, row).ok, raw).toBe(false)
    expect(parseSpec('2.5', { ...row, integer: true }).ok).toBe(false)
  })

  it('applyDrafts marks a changed value as edited and leaves the rest alone', () => {
    const specs = demoSpecs()
    const applied = applyDrafts(specs, { mass_kg: '20', n_drive_motors: '2' })
    if (!applied.ok) throw new Error(applied.error)
    expect(applied.specs[0]).toMatchObject({ value: 20, source: 'edited', evidence: null })
    expect(applied.specs[2]).toBe(specs[2]) // typed the same value: still "from BOM"
    expect(applied.specs[3]).toBe(specs[3])
  })

  it('applyDrafts names the row that is wrong', () => {
    expect(applyDrafts(demoSpecs(), { max_slope_deg: '90' })).toEqual({
      ok: false,
      error: 'max_slope_deg cannot be above 60.',
    })
  })
})

describe('saved onboarding', () => {
  const memory = () => {
    const items = new Map<string, string>()
    return {
      getItem: (k: string) => items.get(k) ?? null,
      setItem: (k: string, v: string) => void items.set(k, v),
    }
  }

  it('round-trips, including a skip', () => {
    const store = memory()
    expect(loadSaved(store)).toBeNull()
    saveOnboarded(onboarded(), store)
    expect(loadSaved(store)).toEqual({ onboarded: onboarded() })
    saveOnboarded(null, store)
    expect(loadSaved(store)).toEqual({ onboarded: null })
  })

  it('is ignored when the entry is not ours or storage is blocked', () => {
    expect(loadSaved({ getItem: () => '{"onboarded":{"company":"x"}}' })).toBeNull()
    expect(loadSaved({ getItem: () => 'not json' })).toBeNull()
    const blocked = () => {
      throw new Error('blocked')
    }
    expect(loadSaved({ getItem: blocked })).toBeNull()
    expect(() => saveOnboarded(null, { setItem: blocked })).not.toThrow()
  })
})

describe('questions', () => {
  it('are four, and only the first has to be answered', () => {
    expect(QUESTIONS.map((q) => q.id)).toEqual(['who', 'market', 'limits', 'drivetrain'])
    expect(QUESTIONS.filter((q) => q.required).map((q) => q.id)).toEqual(['who'])
  })

  it('listOf reads like a sentence', () => {
    expect([listOf([]), listOf(['a']), listOf(['a', 'b']), listOf(['a', 'b', 'c'])]).toEqual([
      '',
      'a',
      'a and b',
      'a, b and c',
    ])
  })
})

describe('intake client', () => {
  const capture = (response: () => Response) => {
    const calls: { url: string; init: RequestInit }[] = []
    const fetchImpl = (async (url: string, init: RequestInit) => {
      calls.push({ url, init })
      return response()
    }) as unknown as typeof fetch
    return { calls, fetchImpl }
  }
  const ok = () => new Response(JSON.stringify({ robot_kind: 'wheeled', company: [], specs: [], dropped: [] }))

  it('posts the files and answers, with the live token only when there is one', async () => {
    const { calls, fetchImpl } = capture(ok)
    await intake({ bom: demo.bom, cad: null, answers: null }, null, fetchImpl)
    await intake({ bom: demo.bom, cad: null, answers: EXAMPLE_ANSWERS }, 'tok', fetchImpl)
    expect(calls[0].url).toBe('/api/intake')
    expect(JSON.parse(calls[0].init.body as string)).toEqual({ robot_kind: 'wheeled', bom: demo.bom, cad: null, answers: null })
    const headers = calls.map((c) => (c.init.headers as Record<string, string>)['X-Live-Token'])
    expect(headers).toEqual([undefined, 'tok'])
  })

  it('turns a refusal into an ApiError with the status and the backend message', async () => {
    const { fetchImpl } = capture(() => new Response('{"detail":"live jobs need a valid X-Live-Token"}', { status: 403 }))
    const error = await intake({ bom: [], cad: null, answers: EXAMPLE_ANSWERS }, null, fetchImpl).catch((e) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 403, message: 'live jobs need a valid X-Live-Token' })
  })

  it('reports an unreachable backend in plain words', async () => {
    const down = (async () => {
      throw new TypeError('fetch failed')
    }) as unknown as typeof fetch
    await expect(measureCad(new Blob(['x']), down)).rejects.toThrow('The backend is unreachable.')
  })
})
