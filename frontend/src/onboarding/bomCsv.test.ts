import { describe, expect, it } from 'vitest'
import { bomCriteria, bomToCsv, parseBomCsv } from './bomCsv'

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
      'line 3: unit_cost_usd is not a number',
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
})
