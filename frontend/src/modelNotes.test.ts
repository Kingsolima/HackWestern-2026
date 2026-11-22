import { describe, expect, it } from 'vitest'
import type { BomLine, Project } from './events'
import { genericModelNotes } from './modelNotes'

const line = (part: string): BomLine => ({
  id: part,
  domain: 'other',
  qty: 1,
  part,
  manufacturer: null,
  unit_price_usd: null,
  origin_country: null,
  origin_tier: null,
  availability: 'unknown',
  lead_time_days: null,
  illustrative: false,
  sources: [],
})

const project = (parts: string[]) => ({ bom: parts.map(line) }) as unknown as Project

describe('genericModelNotes', () => {
  it('always says what the generic model is built from', () => {
    const notes = genericModelNotes(project(['Drive motor (NEMA 23 stepper)']))
    expect(notes).toHaveLength(1)
    expect(notes[0]).toMatch(/not drawn/)
  })

  it('warns that a gearbox in the parts list is not modelled', () => {
    const notes = genericModelNotes(project(['Drive motor', 'Planetary gearbox 5:1']))
    expect(notes).toHaveLength(2)
    expect(notes[1]).toMatch(/gearbox input bore/)
  })
})
