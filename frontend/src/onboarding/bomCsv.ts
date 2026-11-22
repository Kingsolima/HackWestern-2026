// BOM CSV: parse an uploaded file into BomRow[] (with line-numbered errors), and write rows back
// out for the template download.

import type { BomRow } from '../types'

export const BOM_COLUMNS = ['part', 'category', 'qty', 'unit_cost_usd', 'origin'] as const
const OPTIONAL_COLUMN = 'supply_risk'

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

export interface BomParse {
  rows: BomRow[]
  errors: string[]
  /** Which welcome-screen rules the file broke (see bomCriteria). */
  failed: CriterionId[]
  /** True when some line has category motor, the part the agents look for. */
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
 * Header row required: part, category, qty, unit_cost_usd, origin (supply_risk optional, any
 * order, extra columns ignored). A blank origin becomes "unknown", which the backend counts as
 * foreign. Any error means the file is not usable: the caller should not keep `rows`.
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

    const cost = get('unit_cost_usd').replace(/^\$/, '').replaceAll(',', '')
    if (!/^\d+(\.\d+)?$/.test(cost)) bad('cost', `line ${n}: unit_cost_usd is not a number`)

    const rawOrigin = get('origin')
    let origin = 'unknown'
    if (/^[A-Za-z]{2}$/.test(rawOrigin)) origin = rawOrigin.toUpperCase()
    else if (rawOrigin !== '' && rawOrigin.toLowerCase() !== 'unknown') {
      bad('origin', `line ${n}: origin must be a 2-letter country code or "unknown"`)
    }

    const risk = col(OPTIONAL_COLUMN) >= 0 ? get(OPTIONAL_COLUMN) : ''
    rows.push({
      part,
      category,
      qty: Number(qty),
      unit_cost_usd: cost,
      origin,
      ...(risk ? { supply_risk: risk } : {}),
    })
  })
  if (rows.length === 0 && errors.length === 0) bad('lines', 'The file has a header but no parts.')
  const hasMotor = rows.some((r) => r.category.toLowerCase() === 'motor')
  return { rows: errors.length > 0 ? [] : rows, errors, failed: [...failed], hasMotor }
}

const quote = (cell: string) => (/[",\r\n]/.test(cell) ? `"${cell.replaceAll('"', '""')}"` : cell)

export function bomToCsv(rows: BomRow[]): string {
  const out = [[...BOM_COLUMNS, OPTIONAL_COLUMN].join(',')]
  for (const r of rows) {
    out.push(
      [r.part, r.category, String(r.qty), r.unit_cost_usd, r.origin, r.supply_risk ?? ''].map(quote).join(','),
    )
  }
  return out.join('\n') + '\n'
}
