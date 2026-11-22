import { describe, expect, it } from 'vitest'
import type { JobEvent } from './events'
import ar4 from './fixtures/ar4-company.json'
import stretch from './fixtures/stretch.json'
import wheeled from './fixtures/wheeled-demo.json'
import { applyEvent, initialJobState } from './job'
import {
  actionPlan,
  deepLineComparison,
  designChanges,
  evidenceBySource,
  firstClause,
  reportSummary,
  shortPart,
  supplyMap,
} from './report'

// Recorded replays (scripts: backend TestClient + sse_events): the AR4 demo company from
// docs/DEMO-COMPANY.md, the wheeled demo robot and the Stretch project, each run to DONE.
const fold = (events: unknown) => (events as JobEvent[]).reduce(applyEvent, initialJobState)
const AR4 = fold(ar4)
const WHEELED = fold(wheeled)
const STRETCH = fold(stretch)

describe('check_result folding', () => {
  it("keeps both of the CAD worker's fit rows, which share the name fit_cad", () => {
    expect(AR4.checks['CPM-SDSK-2331S-RLN'].map((c) => c.note).filter((n) => n.includes('_'))).toEqual([
      'j2_envelope',
      'shaft_to_gearbox_bore',
    ])
  })
})

describe('deepLineComparison', () => {
  it('says why no AR4 candidate fits: the shaft is too big for the gearbox bore', () => {
    const deep = deepLineComparison(AR4)!
    expect(deep.part).toBe('J2 gear head motor')
    expect(deep.status).toBe(
      'None of the 3 candidates fits the J2 gear head motor as it is. They fail on shaft vs gearbox bore (2), continuous torque (1).',
    )
    const teknic = deep.options.find((o) => o.id === 'CPM-SDSK-2331S-RLN')!
    expect(teknic).toMatchObject({ failed: ['Shaft vs gearbox bore'], open: ['Speed (not verified)'], origin: 'US (T1)' })
    expect(teknic.price).toBe('$336, not verified')

    const bore = deep.rows.find((r) => r.label === 'Shaft vs gearbox bore')!
    expect(bore.required).toBe('at most 6.35 mm')
    expect(bore.cells.map((c) => [c.text, c.tone])).toEqual(
      deep.options.map((o) => (o.failed.includes('Shaft vs gearbox bore') ? [expect.any(String), 'lo'] : [expect.any(String), 'hi'])),
    )
  })

  it('links each value to the quote behind it, and shows readings the verifier threw out', () => {
    const deep = deepLineComparison(AR4)!
    const col = deep.options.findIndex((o) => o.id === 'CPM-SDSK-2331S-RLN')
    const torque = deep.rows.find((r) => r.label === 'Continuous torque')!.cells[col]
    expect(torque).toMatchObject({ text: '0.84 N·m', tone: 'hi', margin: 1.094 })
    expect(torque.evidence[0]).toMatchObject({ field: 'continuous_torque', raw_value: '119.0' })
    expect(torque.evidence[0].source.run_id).toBeTruthy()

    const speed = deep.rows.find((r) => r.label === 'Speed')!.cells[col]
    expect(speed.text).toBe('not verified')
    expect(speed.rejected.map((c) => [c.claim.field, c.claim.raw_value])).toEqual([['max_speed', '2580.0']])
  })

  it('orders usable candidates first and works without a project (wheeled demo)', () => {
    const deep = deepLineComparison(WHEELED)!
    expect(deep.line).toBeNull()
    expect(deep.part).toBe('NEMA 23 stepper')
    expect(deep.options.map((o) => o.verdict)).toEqual(['review', 'review', 'review', 'rejected'])
    expect(deep.options[0].name).toBe('Teknic CPM-SDSK-2310S-RLN')
    expect(deep.status).toBe(
      'No candidate passes every check yet. Closest: Teknic CPM-SDSK-2310S-RLN, with 1 open check: shaft vs wheel bore (to review).',
    )
  })
})

describe('reportSummary', () => {
  it("leads with the backend's first-ranked action, not the first action type", () => {
    const { verdict } = reportSummary(STRETCH, deepLineComparison(STRETCH))
    expect(STRETCH.recommendations[0].line_id).toBe('battery')
    expect(verdict[0]).toMatch(/^First: investigate the LiFePO4 battery pack, which cannot stay as it is\./)
  })

  it('reports the numbers behind it, with tones', () => {
    const { figures } = reportSummary(AR4, deepLineComparison(AR4))
    expect(Object.fromEntries(figures.map((f) => [f.label, [f.value, f.tone]]))).toEqual({
      'Parts mapped': ['60', 'lo'],
      'Parts to change': ['0', 'mid'],
      'Candidates for the J2 gear head motor': ['3', 'lo'],
      'Readings verified': ['13 / 26', 'mid'],
      'Agent runs': ['7 / 11', 'mid'],
      'Domestic content': ['0%', 'lo'],
    })
  })
})

describe('report sections', () => {
  it('groups actions by what to do and the supply map by domain, riskiest first', () => {
    expect(actionPlan(STRETCH).map((g) => [g.action, g.items.length])).toEqual([
      ['dual_source', 2],
      ['investigate', 1],
      ['keep', 1],
    ])
    const actuation = supplyMap(AR4)[0]
    expect(actuation.domain).toBe('actuation')
    expect(actuation.rows[0].risk.priority?.level).toBe('high')
    expect(actuation.counts.high).toBe(6)
  })

  it('counts each site’s verified and rejected readings', () => {
    expect(evidenceBySource(AR4).map((g) => [g.host, g.verified.length, g.rejected.length])).toEqual([
      ['automationtechnologiesinc.com', 1, 9],
      ['teknic.com', 5, 4],
      ['mclennan.co.uk', 7, 0],
    ])
  })

  it('shortens a part name to its head', () => {
    expect(shortPart('Arm shoulder motor, NEMA 34 closed-loop stepper (ILLUSTRATIVE stand-in)')).toBe('Arm shoulder motor')
    expect(shortPart('NEMA 23 stepper (baseline)')).toBe('NEMA 23 stepper')
  })
})

describe('designChanges', () => {
  it("lists an arm's mount, bore and motor space, not wheel rows", () => {
    const rows = designChanges(AR4.baseline!, AR4.candidates[0])
    const labels = rows.map((r) => r.label)
    expect(labels).toEqual(expect.arrayContaining(['Motor shaft', 'Gearbox bore', 'Mount plate', 'Space for the motor']))
    expect(labels).not.toContain('Wheel bore')
    expect(rows.find((r) => r.label === 'Gearbox bore')).toMatchObject({ before: '6.35 mm', after: '6.35 mm' })
  })

  it('keeps the wheeled bracket and hub rows', () => {
    const labels = designChanges(WHEELED.baseline!, WHEELED.candidates[0]).map((r) => r.label)
    expect(labels).toEqual(expect.arrayContaining(['Bolt square', 'Ground clearance']))
  })
})

describe('firstClause', () => {
  it('cuts a reason at its first ";" or sentence end, not inside parentheses or a decimal', () => {
    expect(
      firstClause(
        'Conflict: you sell to US federal buyers, and it is made in CN; likely depends on magnets (inferred, not verified: x. y) and is made in CN.',
      ),
    ).toBe('Conflict: you sell to US federal buyers, and it is made in CN.')
    expect(firstClause('Adds 41.5% duty (HTS 8501.31). No alternative.')).toBe('Adds 41.5% duty (HTS 8501.31).')
    expect(firstClause('Fine as it is')).toBe('Fine as it is')
  })

  it('keeps the summary lead to one clause', () => {
    const { verdict } = reportSummary(AR4, deepLineComparison(AR4))
    expect(verdict[0]).toMatch(/^First: investigate the J5 linear drive motor, which cannot stay as it is\. Conflict: [^;]+ made in CN\.$/)
  })
})
