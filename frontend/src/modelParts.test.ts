import { describe, expect, it } from 'vitest'
import { matchLine, partInfo, partRole, type PartLine } from './modelParts'

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
    expect(partRole('robot', 'motor_left', { deep: false, build: false })).toBeNull()
    expect(partRole('robot', 'motor_left', { deep: true, build: false })).toBe('deep')
    expect(partRole('robot', 'bracket_right', { deep: true, build: false })).toBeNull()
    expect(partRole('robot', 'bracket_right', { deep: true, build: true })).toBe('build')
    expect(partRole('ar4', 'j2_motor_shaft', { deep: true, build: true })).toBeNull()
    expect(partRole('stretch', 'mount_plate', { deep: true, build: true })).toBe('build')
    expect(partRole('unknown_root', 'motor_left', { deep: true, build: true })).toBeNull()
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
