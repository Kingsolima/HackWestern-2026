// BOM CSV: parse an uploaded file into BomRow[] (with line-numbered errors), and write rows back
// out for the template download.

import type { BomRow } from '../types'

export const BOM_COLUMNS = ['part', 'category', 'qty', 'unit_cost_usd', 'origin'] as const
const OPTIONAL_COLUMN = 'supply_risk'
// Copied through as text when the file has them.
const EXTRA_COLUMNS = ['part_number', 'supplier', 'source_page', 'notes'] as const

/** Split CSV text into lines of cells. Handles quoted cells, "" escapes, CRLF and a leading BOM. */
export function splitCsv(text: string): string[][] {
  const lines: string[][] = []
  let row: string[] = []
  let cell = ''
  let quoted = false
  const src = text.replace(/^﻿/, '')
  for (let i = 0; i < src.length; i++) {
    const ch = src[i]
    if (quoted) {
      if (ch === '"' && src[i + 1] === '"') {
        cell += '"'
        i++
      } else if (ch === '"') quoted = false
      else cell += ch
    } else if (ch === '"') quoted = true
    else if (ch === ',') {
      row.push(cell)
      cell = ''
    } else if (ch === '\n' || ch === '\r') {
      if (ch === '\r' && src[i + 1] === '\n') i++
      row.push(cell)
      lines.push(row)
      row = []
      cell = ''
    } else cell += ch
  }
  if (cell !== '' || row.length > 0) {
    row.push(cell)
    lines.push(row)
  }
  return lines
}

// Mirrors classify() in backend/app/intake/to_project.py, which picks the line the agents
// source. Change both together.
const RULES: [string[], string, boolean][] = [
  [['driver', 'inverter'], 'power', false],
  [['encoder'], 'sensing', false],
  [['lidar'], 'sensing', false],
  [['camera', 'sensor', 'imu'], 'sensing', false],
  [['battery'], 'power', false],
  [['harmonic', 'strain wave', 'strain-wave'], 'actuation', false],
  [['motor', 'servo', 'stepper', 'actuator'], 'actuation', true],
  [['gearbox'], 'actuation', false],
  [['computer', 'compute', 'sbc'], 'compute', false],
  [['controller', 'mcu', 'microcontroller'], 'compute', false],
  [['frame', 'bracket', 'plate', 'chassis', 'wheel', 'enclosure', 'fastener'], 'structure', false],
]
const SUBSYSTEMS = new Map([
  ['actuation', 'actuation'],
  ['transmission', 'actuation'],
  ['structure', 'structure'],
  ['power', 'power'],
  ['sensors', 'sensing'],
])

/** True when the backend reads this line as a motor: the first keyword rule that matches
 * "<category> <part>" is the motor rule, and a subsystem category does not name another domain. */
export function isMotorLine(row: Pick<BomRow, 'part' | 'category'>): boolean {
  const text = `${row.category} ${row.part}`.toLowerCase()
  const stated = SUBSYSTEMS.get(row.category.trim().toLowerCase())
  const rule = RULES.find(([words, domain]) => words.some((w) => text.includes(w)) && (stated ?? domain) === domain)
  return rule?.[2] ?? false
}

export interface BomParse {
  rows: BomRow[]
  errors: string[]
  /** Which welcome-screen rules the file broke (see bomCriteria). */
  failed: CriterionId[]
  /** True when some line is a motor (see isMotorLine), the part the agents look for. */
  hasMotor: boolean
}

export type CriterionId = 'csv' | 'columns' | 'lines' | 'cost' | 'origin' | 'motor'
export type CriterionStatus = 'pass' | 'fail' | 'pending'
export const CRITERIA: readonly CriterionId[] = ['csv', 'columns', 'lines', 'cost', 'origin', 'motor']

/**
 * The welcome checklist for one uploaded file. `parse` null = nothing uploaded yet (all pending).
 * When the header or the whole file is unusable, the per-line rules stay pending: they were
 * never checked.
 */
export function bomCriteria(fileName: string | null, parse: BomParse | null): Record<CriterionId, CriterionStatus> {
  const out = Object.fromEntries(CRITERIA.map((c) => [c, 'pending'])) as Record<CriterionId, CriterionStatus>
  if (fileName === null || parse === null) return out
  const fail = (c: CriterionId) => parse.failed.includes(c)
  out.csv = /\.csv$/i.test(fileName) && !fail('csv') ? 'pass' : 'fail'
  if (fail('csv')) return out
  out.columns = fail('columns') ? 'fail' : 'pass'
  if (fail('columns')) return out
  for (const c of ['lines', 'cost', 'origin'] as const) out[c] = fail(c) ? 'fail' : 'pass'
  out.motor = parse.hasMotor ? 'pass' : 'fail'
  return out
}

/**
 * Header row required: part, category, qty, unit_cost_usd, origin (supply_risk, part_number,
 * supplier, source_page and notes optional, any order, other columns ignored). A blank origin
 * becomes "unknown", which the backend counts as foreign. A blank or "unknown" unit_cost_usd
 * becomes null: no price, never 0. Any error means the file is not usable: the caller should
 * not keep `rows`.
 */
export function parseBomCsv(text: string): BomParse {
  const lines = splitCsv(text)
  if (lines.length === 0) return { rows: [], errors: ['The file is empty.'], failed: ['csv'], hasMotor: false }

  const header = lines[0].map((h) => h.trim().toLowerCase())
  const missing = BOM_COLUMNS.filter((c) => !header.includes(c))
  if (missing.length > 0) {
    return {
      rows: [],
      errors: [`line 1: missing column${missing.length > 1 ? 's' : ''} ${missing.join(', ')}`],
      failed: ['columns'],
      hasMotor: false,
    }
  }
  const col = (name: string) => header.indexOf(name)

  const rows: BomRow[] = []
  const errors: string[] = []
  const failed = new Set<CriterionId>()
  const bad = (c: CriterionId, text: string) => {
    failed.add(c)
    errors.push(text)
  }
  lines.slice(1).forEach((cells, i) => {
    const n = i + 2
    if (cells.every((c) => c.trim() === '')) return
    const get = (name: string) => (cells[col(name)] ?? '').trim()

    const part = get('part')
    if (!part) bad('lines', `line ${n}: part is empty`)
    const category = get('category')
    if (!category) bad('lines', `line ${n}: category is empty`)

    const qty = get('qty')
    if (!/^[1-9]\d*$/.test(qty)) bad('lines', `line ${n}: qty is not a whole number above 0`)

    const rawCost = get('unit_cost_usd').replace(/^\$/, '').replaceAll(',', '')
    const cost = rawCost === '' || rawCost.toLowerCase() === 'unknown' ? null : rawCost
    if (cost !== null && !/^\d+(\.\d+)?$/.test(cost)) bad('cost', `line ${n}: unit_cost_usd is not a number or "unknown"`)

    const rawOrigin = get('origin')
    let origin = 'unknown'
    if (/^[A-Za-z]{2}$/.test(rawOrigin)) origin = rawOrigin.toUpperCase()
    else if (rawOrigin !== '' && rawOrigin.toLowerCase() !== 'unknown') {
      bad('origin', `line ${n}: origin must be a 2-letter country code or "unknown"`)
    }

    const risk = col(OPTIONAL_COLUMN) >= 0 ? get(OPTIONAL_COLUMN) : ''
    const extras: Partial<Record<(typeof EXTRA_COLUMNS)[number], string>> = {}
    for (const name of EXTRA_COLUMNS) {
      if (col(name) >= 0 && get(name)) extras[name] = get(name)
    }
    rows.push({
      part,
      category,
      qty: Number(qty),
      unit_cost_usd: cost,
      origin,
      ...(risk ? { supply_risk: risk } : {}),
      ...extras,
    })
  })
  if (rows.length === 0 && errors.length === 0) bad('lines', 'The file has a header but no parts.')
  const hasMotor = rows.some(isMotorLine)
  return { rows: errors.length > 0 ? [] : rows, errors, failed: [...failed], hasMotor }
}

/** What the parts cost per robot, saying how many lines have no price. */
export function costPerRobot(rows: BomRow[]): string {
  const priced = rows.filter((r) => r.unit_cost_usd !== null)
  if (priced.length === 0) return 'no prices'
  const total = priced.reduce((sum, r) => sum + r.qty * Number(r.unit_cost_usd), 0)
  const unpriced = rows.length - priced.length
  return `$${total.toFixed(0)} per robot${unpriced ? ` + ${unpriced} unpriced` : ''}`
}

const quote = (cell: string) => (/[",\r\n]/.test(cell) ? `"${cell.replaceAll('"', '""')}"` : cell)

export function bomToCsv(rows: BomRow[]): string {
  const out = [[...BOM_COLUMNS, OPTIONAL_COLUMN].join(',')]
  for (const r of rows) {
    out.push(
      [r.part, r.category, String(r.qty), r.unit_cost_usd ?? 'unknown', r.origin, r.supply_risk ?? '']
        .map(quote)
        .join(','),
    )
  }
  return out.join('\n') + '\n'
}
