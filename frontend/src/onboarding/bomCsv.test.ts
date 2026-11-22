import { describe, expect, it } from 'vitest'
import ar4Csv from '../../../docs/demo-company-bom.csv?raw'
import { bomToCsv, parseBomCsv } from './bomCsv'

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
    expect(parseBomCsv(bomToCsv(rows))).toEqual({ rows, errors: [] })
  })

  it('writes a part with no price as unknown', () => {
    const rows = [{ part: 'Belt', category: 'transmission', qty: 1, unit_cost_usd: null, origin: 'unknown' }]
    expect(parseBomCsv(bomToCsv(rows))).toEqual({ rows, errors: [] })
  })
})
