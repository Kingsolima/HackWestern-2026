import { describe, expect, it } from 'vitest'
import type { JobEvent } from './events'
import ar4 from './fixtures/ar4-company.json'
import { applyEvent, initialJobState, type JobState } from './job'
import type { PartLine } from './modelParts'
import { partDetail, worstFactor } from './partDetail'

const job: JobState = (ar4 as unknown as JobEvent[]).reduce(applyEvent, initialJobState)
const lines: PartLine[] = job.project!.bom.map((l) => ({
  id: l.id,
  part: l.part,
  category: l.domain,
  qty: l.qty,
  price: l.unit_price_usd,
  origin: l.origin_country,
}))

describe('partDetail on the finished AR4 job', () => {
  it('joins the J2 motor to its line, risk, action and the alternatives the agents found', () => {
    const d = partDetail('j2_motor', lines, job, 'deep')
    expect(d.title).toBe('J2 gear head motor')
    expect(d.facts).toEqual(['x1', '$152.52', 'CN', 'Stepperonline', 'in stock'])
    expect(d.role).toMatch(/Deep line/)
    expect(d.risk?.overall).toBe('high')
    expect(d.level).toBe(d.risk?.priority?.level)
    expect(d.worst).toMatchObject({ name: 'sources', level: 'high' })
    expect(d.recommendation?.action).toBe('investigate')
    expect(d.alternatives.map((a) => a.id)).toEqual(['CPM-SDSK-2331S-RLN', 'ISV-B23130T-D4', 'V0300-211-B-000'])
  })

  it('reads the gearbox as the J2 motor line and each link as its joint’s machined parts', () => {
    expect(partDetail('j2_gearbox', lines, job, null).line?.id).toBe('line_2')
    expect(partDetail('link_2', lines, job, null)).toMatchObject({
      title: 'J2 machined aluminum parts',
      worst: null,
      action: 'Keep',
    })
    expect(partDetail('link_5', lines, job, null).line?.id).toBe('line_34')
  })

  it('lists the candidate lines when a node could be several, and joins nothing', () => {
    const d = partDetail('turret', lines, job, null)
    expect(d.line).toBeNull()
    expect(d.candidates).toEqual(['J1 machined aluminum parts', 'J2 machined aluminum parts', 'J4 machined aluminum parts'])
  })

  it('falls back to the plain BOM facts before a job has a project', () => {
    const d = partDetail('j2_motor', lines.map((l) => ({ ...l, id: undefined })), initialJobState, null)
    expect(d.line).toBeNull()
    expect(d.risk).toBeNull()
    expect(d.facts).toEqual(['x1 / $152.52 / CN'])
  })
})

describe('worstFactor', () => {
  it('ignores low and unknown factors', () => {
    const risk = { line_id: 'x', overall: 'low' as const, factors: [
      { name: 'trade' as const, level: 'unknown' as const, value: '', reason: '', source_urls: [] },
      { name: 'sources' as const, level: 'low' as const, value: '', reason: '', source_urls: [] },
    ] }
    expect(worstFactor(risk)).toBeNull()
    expect(worstFactor({ ...risk, factors: [...risk.factors, { ...risk.factors[0], level: 'medium' }] })?.level).toBe('medium')
  })
})
