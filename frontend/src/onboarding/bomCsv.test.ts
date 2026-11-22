import { describe, expect, it } from 'vitest'
import ar4Csv from '../../../docs/demo-company-bom.csv?raw'
import { bomCriteria, bomToCsv, costPerRobot, isMotorLine, parseBomCsv } from './bomCsv'

const HEADER = 'part,category,qty,unit_cost_usd,origin'

describe('parseBomCsv', () => {
  it('reads rows, upper-cases origins and keeps the cost as a decimal string', () => {
    const { rows, errors } = parseBomCsv(`${HEADER}\nDrive motor,motor,2,45.00,cn\nBase plate,frame,1,$120,US\n`)
    expect(errors).toEqual([])
    expect(rows).toEqual([
      { part: 'Drive motor', category: 'motor', qty: 2, unit_cost_usd: '45.00', origin: 'CN' },
      { part: 'Base plate', category: 'frame', qty: 1, unit_cost_usd: '120', origin: 'US' },
    ])
  })

  it('handles quoted cells, CRLF, a byte-order mark, any column order and blank lines', () => {
    const text = '﻿Origin,Qty,Part,unit_cost_usd,Category,supply_risk\r\nUS,1,"Plate, 6 mm ""A""","1,200.50",frame,\r\n\r\nCN,2,Motor,45,motor,ndfeb_magnets\r\n'
    expect(parseBomCsv(text)).toEqual({
      errors: [],
      failed: [],
      hasMotor: true,
      rows: [
        { part: 'Plate, 6 mm "A"', category: 'frame', qty: 1, unit_cost_usd: '1200.50', origin: 'US' },
        { part: 'Motor', category: 'motor', qty: 2, unit_cost_usd: '45', origin: 'CN', supply_risk: 'ndfeb_magnets' },
      ],
    })
  })

  it('turns a blank or "Unknown" origin into unknown', () => {
    const { rows } = parseBomCsv(`${HEADER}\nBattery,battery,1,80,\nWheel,frame,2,15,Unknown\n`)
    expect(rows.map((r) => r.origin)).toEqual(['unknown', 'unknown'])
  })

  it('reads a blank or "unknown" cost as no price, and copies the optional text columns', () => {
    const text = `${HEADER},part_number,supplier,source_page,notes\nJ2 motor,actuation,1,unknown,,23HS22,Stepperonline,33,check coupler\nBelt,transmission,1,,unknown,,,10,\n`
    expect(parseBomCsv(text)).toEqual({
      errors: [],
      failed: [],
      hasMotor: true,
      rows: [
        {
          part: 'J2 motor',
          category: 'actuation',
          qty: 1,
          unit_cost_usd: null,
          origin: 'unknown',
          part_number: '23HS22',
          supplier: 'Stepperonline',
          source_page: '33',
          notes: 'check coupler',
        },
        { part: 'Belt', category: 'transmission', qty: 1, unit_cost_usd: null, origin: 'unknown', source_page: '10' },
      ],
    })
  })

  it('reads the AR4 parts list in docs/ without errors', () => {
    const { rows, errors } = parseBomCsv(ar4Csv)
    expect(errors).toEqual([])
    expect(rows).toHaveLength(60)
    expect(rows.find((r) => r.part === 'J2 gear head motor')?.part_number).toBe('23HS22-2804D-YGS50-AR4')
    expect(rows.every((r) => r.unit_cost_usd === null && r.origin === 'unknown')).toBe(true)
  })

  it('names the missing columns', () => {
    expect(parseBomCsv('part,qty\nMotor,2\n')).toEqual({
      rows: [],
      errors: ['line 1: missing columns category, unit_cost_usd, origin'],
      failed: ['columns'],
      hasMotor: false,
    })
  })

  it('names the line of every bad value and keeps no rows', () => {
    const { rows, errors } = parseBomCsv(`${HEADER}\nMotor,motor,two,45,CN\n,frame,1,abc,China\n`)
    expect(rows).toEqual([])
    expect(errors).toEqual([
      'line 2: qty is not a whole number above 0',
      'line 3: part is empty',
      'line 3: unit_cost_usd is not a number or "unknown"',
      'line 3: origin must be a 2-letter country code or "unknown"',
    ])
  })

  it('rejects an empty file and a header with no parts', () => {
    expect(parseBomCsv('').errors).toEqual(['The file is empty.'])
    expect(parseBomCsv(`${HEADER}\n`).errors).toEqual(['The file has a header but no parts.'])
  })
})

describe('bomToCsv', () => {
  it('writes a file that parses back to the same rows', () => {
    const rows = [
      { part: 'Plate, 6 mm "A"', category: 'frame', qty: 1, unit_cost_usd: '120.00', origin: 'US' },
      { part: 'Motor', category: 'motor', qty: 2, unit_cost_usd: '45.00', origin: 'CN', supply_risk: 'ndfeb_magnets' },
    ]
    expect(parseBomCsv(bomToCsv(rows))).toEqual({ rows, errors: [], failed: [], hasMotor: true })
  })

  it('writes a part with no price as unknown', () => {
    const rows = [{ part: 'Belt', category: 'transmission', qty: 1, unit_cost_usd: null, origin: 'unknown' }]
    expect(parseBomCsv(bomToCsv(rows))).toEqual({ rows, errors: [], failed: [], hasMotor: false })
  })
})

describe('isMotorLine', () => {
  it('finds the motors the backend finds in the AR4 parts list (classify in to_project.py)', () => {
    const motors = parseBomCsv(ar4Csv).rows.filter(isMotorLine).map((r) => r.part)
    expect(motors).toEqual([
      'J1 gear head motor',
      'J2 gear head motor',
      'J3 gear head motor',
      'J4 gear head motor',
      'J5 linear drive motor',
      'J6 gear head motor',
    ])
  })

  it('reads the category and the name, earlier rules first, and lets a subsystem category overrule', () => {
    expect(isMotorLine({ category: 'motor', part: 'Drive motor (NEMA 23)' })).toBe(true)
    expect(isMotorLine({ category: 'electronics', part: 'NEMA 17 stepper' })).toBe(true)
    expect(isMotorLine({ category: 'actuation', part: 'Integrated servo' })).toBe(true)
    expect(isMotorLine({ category: 'Servo', part: 'Dynamixel XM430' })).toBe(true)
    expect(isMotorLine({ category: 'electronics', part: 'Motor driver' })).toBe(false)
    expect(isMotorLine({ category: 'structure', part: 'J1 & J3 motor mounts' })).toBe(false)
    expect(isMotorLine({ category: 'actuation', part: 'Planetary gearbox' })).toBe(false)
  })
})

describe('bomCriteria', () => {
  const statuses = (name: string | null, text: string | null) => bomCriteria(name, text === null ? null : parseBomCsv(text))

  it('leaves everything pending before a file is chosen', () => {
    expect(Object.values(statuses(null, null))).toEqual(Array(6).fill('pending'))
  })

  it('passes every rule for a good file with a motor line', () => {
    expect(statuses('bom.CSV', `${HEADER}\nDrive motor,Motor,2,45,CN\n`)).toEqual({
      csv: 'pass', columns: 'pass', lines: 'pass', cost: 'pass', origin: 'pass', motor: 'pass',
    })
  })

  it('fails only the rules the lines broke, and still checks for a motor', () => {
    expect(statuses('bom.csv', `${HEADER}\nPlate,frame,0,abc,US\n`)).toEqual({
      csv: 'pass', columns: 'pass', lines: 'fail', cost: 'fail', origin: 'pass', motor: 'fail',
    })
    expect(statuses('bom.csv', `${HEADER}\nMotor,motor,2,45,China\n`).origin).toBe('fail')
  })

  it('does not check lines it never read: missing columns, an empty file, a non-csv name', () => {
    expect(statuses('bom.csv', 'part,qty\nMotor,2\n')).toMatchObject({ csv: 'pass', columns: 'fail', lines: 'pending', motor: 'pending' })
    expect(statuses('bom.csv', '')).toMatchObject({ csv: 'fail', columns: 'pending' })
    expect(statuses('bom.xlsx', `${HEADER}\nMotor,motor,2,45,CN\n`).csv).toBe('fail')
  })

  it('passes the AR4 demo company: subsystem categories and no prices or origins', () => {
    expect(Object.values(statuses('demo-company-bom.csv', ar4Csv))).toEqual(Array(6).fill('pass'))
  })
})

describe('costPerRobot', () => {
  const row = (unit_cost_usd: string | null, qty = 1) => ({ part: 'P', category: 'frame', qty, unit_cost_usd, origin: 'US' })

  it('totals qty x price and counts the lines with no price, never as $0', () => {
    expect(costPerRobot([row('45', 2), row('120')])).toBe('$210 per robot')
    expect(costPerRobot([row('45', 2), row(null)])).toBe('$90 per robot + 1 unpriced')
    expect(costPerRobot([row(null), row(null)])).toBe('no prices')
  })
})
