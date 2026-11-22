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
}

/**
 * Header row required: part, category, qty, unit_cost_usd, origin (supply_risk optional, any
 * order, extra columns ignored). A blank origin becomes "unknown", which the backend counts as
 * foreign. Any error means the file is not usable: the caller should not keep `rows`.
 */
export function parseBomCsv(text: string): BomParse {
  const lines = splitCsv(text)
  if (lines.length === 0) return { rows: [], errors: ['The file is empty.'] }

  const header = lines[0].map((h) => h.trim().toLowerCase())
  const missing = BOM_COLUMNS.filter((c) => !header.includes(c))
  if (missing.length > 0) {
    return { rows: [], errors: [`line 1: missing column${missing.length > 1 ? 's' : ''} ${missing.join(', ')}`] }
  }
  const col = (name: string) => header.indexOf(name)

  const rows: BomRow[] = []
  const errors: string[] = []
  lines.slice(1).forEach((cells, i) => {
    const n = i + 2
    if (cells.every((c) => c.trim() === '')) return
    const get = (name: string) => (cells[col(name)] ?? '').trim()

    const part = get('part')
    if (!part) errors.push(`line ${n}: part is empty`)
    const category = get('category')
    if (!category) errors.push(`line ${n}: category is empty`)

    const qty = get('qty')
    if (!/^[1-9]\d*$/.test(qty)) errors.push(`line ${n}: qty is not a whole number above 0`)

    const cost = get('unit_cost_usd').replace(/^\$/, '').replaceAll(',', '')
    if (!/^\d+(\.\d+)?$/.test(cost)) errors.push(`line ${n}: unit_cost_usd is not a number`)

    const rawOrigin = get('origin')
    let origin = 'unknown'
    if (/^[A-Za-z]{2}$/.test(rawOrigin)) origin = rawOrigin.toUpperCase()
    else if (rawOrigin !== '' && rawOrigin.toLowerCase() !== 'unknown') {
      errors.push(`line ${n}: origin must be a 2-letter country code or "unknown"`)
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
  if (rows.length === 0 && errors.length === 0) errors.push('The file has a header but no parts.')
  return errors.length > 0 ? { rows: [], errors } : { rows, errors }
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
