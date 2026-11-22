// What onboarding ends with, and the pure functions that turn it into the Robot a job runs on.

import type { BomRow, Robot, RobotRequirements } from '../types'
import type { CompanyFact, KnownArm, SpecRow } from './intake'
import type { OpenAnswers } from './questions'

/** The confirmed result of onboarding: the user's words, their BOM, and the facts and numbers
 * they accepted on the review screen. */
export interface Onboarded {
  answers: OpenAnswers
  bom: BomRow[]
  company: CompanyFact[]
  specs: SpecRow[]
  /** The researched arm the parts list matched, if any. The specs are then not used. */
  arm?: KnownArm | null
}

export const fact = (company: CompanyFact[], field: string): string | undefined =>
  company.find((c) => c.field === field)?.value

/** The demo robot's name without its "(placeholder values, ...)" note. */
export const cleanName = (name: string) => name.replace(/\s*\(.*\)\s*$/, '')

/** Facts the job needs even when the answers did not state them: shown on the review screen
 * with the demo robot's value so the user can correct them. */
export function withDefaults(company: CompanyFact[], demo: Robot): CompanyFact[] {
  const out = [...company]
  const need: [string, string, string][] = [
    ['robot_name', 'Robot', cleanName(demo.name)],
    ['final_assembly_country', 'Final assembly', demo.final_assembly_country],
  ]
  for (const [field, label, value] of need) {
    if (!out.some((c) => c.field === field)) out.push({ field, label, value, quote: '' })
  }
  return out
}

export function toRobot(o: Onboarded, demo: Robot): Robot {
  const requirements = { ...demo.requirements }
  for (const s of o.specs) {
    if (s.robot_field in requirements) {
      requirements[s.robot_field as keyof RobotRequirements] = s.value / s.divisor
    }
  }
  return {
    name: fact(o.company, 'robot_name') || cleanName(demo.name),
    final_assembly_country: (fact(o.company, 'final_assembly_country') || demo.final_assembly_country).toUpperCase(),
    requirements,
    bom: o.bom,
  }
}

/**
 * True when a number that is written into the agent's goal differs from the demo robot's
 * (backend: SpecField.live). Recordings are keyed by that goal, so the job needs real agent runs.
 */
export function needsLiveAgents(specs: SpecRow[]): boolean {
  return specs.some((s) => s.live && s.value !== s.default)
}

/** True when a job on this robot gives the same compliance card and checks as the demo robot
 * (the name does not matter), so the demo-robot panels are still correct. */
export function matchesDemo(o: Onboarded, demo: Robot): boolean {
  const mine = toRobot(o, demo)
  const fields = Object.keys(demo.requirements) as (keyof RobotRequirements)[]
  return (
    mine.final_assembly_country === demo.final_assembly_country &&
    fields.every((f) => mine.requirements[f] === demo.requirements[f]) &&
    JSON.stringify(mine.bom) === JSON.stringify(demo.bom)
  )
}

/** What the drivetrain question should still ask for: specs no file gave us. */
export function stillMissing(specs: SpecRow[]): string[] {
  return specs.filter((s) => s.source === 'default' && s.ask).map((s) => s.ask as string)
}

export type Parsed = { ok: true; value: number } | { ok: false; error: string }

/** A value typed on the review screen, checked against the row's own limits. */
export function parseSpec(raw: string, row: Pick<SpecRow, 'integer' | 'allow_zero' | 'max'>): Parsed {
  const text = raw.trim().replaceAll(',', '')
  if (text === '') return { ok: false, error: 'needs a number' }
  if (!/^\d+(\.\d+)?$/.test(text)) return { ok: false, error: 'is not a number' }
  const value = Number(text)
  if (row.integer && !Number.isInteger(value)) return { ok: false, error: 'has to be a whole number' }
  if (value === 0 && !row.allow_zero) return { ok: false, error: 'has to be above 0' }
  if (row.max != null && value > row.max) return { ok: false, error: `cannot be above ${row.max}` }
  return { ok: true, value }
}

/** Apply the review screen's typed values. A changed value is marked 'edited'. */
export function applyDrafts(
  specs: SpecRow[],
  drafts: Record<string, string>,
): { ok: true; specs: SpecRow[] } | { ok: false; error: string } {
  const out: SpecRow[] = []
  for (const row of specs) {
    const draft = drafts[row.field]
    if (draft === undefined) {
      out.push(row)
      continue
    }
    const parsed = parseSpec(draft, row)
    if (!parsed.ok) return { ok: false, error: `${row.label} ${parsed.error}.` }
    out.push(parsed.value === row.value ? row : { ...row, value: parsed.value, source: 'edited', evidence: null })
  }
  return { ok: true, specs: out }
}

const KEY = 'onboarding-v2'

/** What the browser remembers: `onboarded: null` means the user skipped to the demo robot. */
export interface Saved {
  onboarded: Onboarded | null
}

export function loadSaved(storage?: Pick<Storage, 'getItem'>): Saved | null {
  try {
    const raw = (storage ?? localStorage).getItem(KEY)
    if (!raw) return null
    const saved = JSON.parse(raw) as Saved
    if (saved.onboarded === null) return saved
    const o = saved.onboarded
    return Array.isArray(o?.bom) && Array.isArray(o.specs) && Array.isArray(o.company) && o.answers ? saved : null
  } catch {
    return null // storage blocked or the entry is not ours: ask again
  }
}

export function saveOnboarded(onboarded: Onboarded | null, storage?: Pick<Storage, 'setItem'>) {
  try {
    ;(storage ?? localStorage).setItem(KEY, JSON.stringify({ onboarded } satisfies Saved))
  } catch {
    // storage blocked: the answers last for this page load only
  }
}
