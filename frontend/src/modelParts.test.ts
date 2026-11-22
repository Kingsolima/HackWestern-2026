import { describe, expect, it } from 'vitest'
import ar4Csv from '../../docs/demo-company-bom.csv?raw'
import { matchLine, matchLines, partInfo, partRole, type PartLine } from './modelParts'
import { parseBomCsv } from './onboarding/bomCsv'

// data/demo_robot.json
const BOM: PartLine[] = [
  { part: 'Drive motor (NEMA 23)', category: 'motor', qty: 2, price: 45, origin: 'CN' },
  { part: 'Aluminum base plate', category: 'frame', qty: 1, price: 120, origin: 'US' },
  { part: 'Wheel', category: 'frame', qty: 2, price: 15, origin: 'CN' },
  { part: 'Wheel encoder', category: 'encoder', qty: 2, price: 30, origin: 'US' },
  { part: '24V battery pack', category: 'battery', qty: 1, price: 80, origin: 'unknown' },
  { part: 'Electronics enclosure', category: 'frame', qty: 1, price: 25, origin: 'CA' },
]

describe('partRole', () => {
  it('marks the deep line once a job runs and the mount once the redesign shows', () => {
    expect(partRole('wheeled', 'motor_left', { deep: false, build: false })).toBeNull()
    expect(partRole('wheeled', 'motor_left', { deep: true, build: false })).toBe('deep')
    expect(partRole('wheeled', 'bracket_right', { deep: true, build: false })).toBeNull()
    expect(partRole('wheeled', 'bracket_right', { deep: true, build: true })).toBe('build')
    expect(partRole('ar4', 'j2_motor_shaft', { deep: true, build: true })).toBeNull()
    expect(partRole('stretch', 'mount_plate', { deep: true, build: true })).toBe('build')
  })
})

describe('matchLine', () => {
  it('finds motors by category and other parts by a word of their name', () => {
    expect(matchLine('motor_left', BOM)?.part).toBe('Drive motor (NEMA 23)')
    expect(matchLine('wheel_right', BOM)?.part).toBe('Wheel')
    expect(matchLine('base_plate', BOM)?.part).toBe('Aluminum base plate')
    expect(matchLine('electronics_box', BOM)?.part).toBe('Electronics enclosure')
  })

  it('does not call a shaft the motor, or match on short or side words', () => {
    expect(matchLine('shaft_left', BOM)).toBeNull()
    expect(matchLine('motor_shaft_left', BOM)).toBeNull()
    expect(matchLine('caster', BOM)).toBeNull()
  })
})

describe('partInfo', () => {
  it('shows the BOM line, an unknown origin, or that the part is not in the BOM', () => {
    expect(partInfo('motor_left', BOM, null)).toEqual({ title: 'Drive motor (NEMA 23)', detail: 'x2 / $45 / CN' })
    expect(partInfo('caster', BOM, null)).toEqual({ title: 'Caster', detail: 'Not in your BOM' })
    expect(partInfo('battery', BOM, null).detail).toBe('x1 / $80 / origin unknown')
  })

  it('says what the job is doing to a part with a role', () => {
    expect(partInfo('bracket_left', BOM, 'build').detail).toMatch(/Regenerated/)
  })
})

// docs/demo-company-bom.csv, as App passes an uploaded BOM to the viewer.
const AR4_COMPANY: PartLine[] = parseBomCsv(ar4Csv).rows.map((r) => ({ ...r, price: null }))
// data/projects/ar4_club.json: a project's lines carry the domain as category.
const AR4_CLUB: PartLine[] = [
  { part: 'J2 NEMA 23 stepper with 50:1 planetary gearbox and encoder', category: 'actuation', qty: 1, price: 289, origin: 'CN' },
  { part: 'Other joint motors, stepper drivers and 24 V supply (StepperOnline AR4 motor package)', category: 'actuation', qty: 1, price: 900, origin: 'CN' },
]

describe('matchLines on the AR4 parts lists', () => {
  it('names the J2 motor, not the first motor line', () => {
    expect(matchLine('j2_motor', AR4_COMPANY)?.part).toBe('J2 gear head motor')
    expect(matchLine('j2_motor', AR4_CLUB)?.part).toMatch(/^J2 NEMA 23 stepper/)
  })

  it('does not guess between lines that all name the part', () => {
    expect(matchLines('turret', AR4_COMPANY).map((l) => l.part.split(' (')[0])).toEqual([
      'J1 machined aluminum parts',
      'J2 machined aluminum parts',
      'J4 machined aluminum parts',
    ])
    expect(matchLine('turret', AR4_COMPANY)).toBeNull()
    expect(partInfo('turret', AR4_COMPANY, null)).toEqual({
      title: 'Turret',
      detail: 'In 3 BOM lines: J1 machined aluminum parts, J2 machined aluminum parts, J4 machined aluminum parts',
    })
  })
})
