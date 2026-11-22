// Intake API (backend/app/api/intake.py): files and open answers in, specs review rows out.

import type { CadRobot } from '../events'
import type { BomRow } from '../types'
import type { OpenAnswers } from './questions'

const BASE = import.meta.env.VITE_API_URL ?? ''

/** Where a number came from. 'edited' is set in the browser when the user changes a value. */
export type Source = 'answer' | 'bom' | 'cad' | 'default' | 'edited'

export interface SpecRow {
  field: string
  label: string
  group: string
  unit: string
  value: number
  source: Source
  evidence: string | null
  /** The demo robot's value. */
  default: number
  /** True when the value is written into the agent's goal: changing it means live agent runs. */
  live: boolean
  ask: string | null
  robot_field: string
  divisor: number
  integer: boolean
  allow_zero: boolean
  max: number | null
}

export interface CompanyFact {
  field: string
  label: string
  value: string
  /** The user's own words this came from; empty for a default. */
  quote: string
}

export interface CadMeasure {
  parts: { name: string; bbox_mm: [number, number, number]; volume_mm3: number }[]
  bbox_mm: [number, number, number]
  volume_mm3: number
}

/** Set when the parts list holds the motor of an arm we have researched: the job runs on that
 * arm's joint numbers, and the drivetrain question does not apply. */
export interface KnownArm {
  robot: string
  cad_robot: CadRobot
  arm: {
    joint: string
    payload_kg: number
    reach_m: number
    gear_ratio: number
    bus_voltage_v: number
    safety_factor: number
  }
}

export interface IntakeResult {
  robot_kind: 'wheeled'
  known_arm?: KnownArm | null
  company: CompanyFact[]
  specs: SpecRow[]
  dropped: string[]
}

export class ApiError extends Error {
  status: number
  constructor(status: number, detail: string) {
    super(detail)
    this.status = status
  }
}

async function post<T>(path: string, init: RequestInit, fetchImpl: typeof fetch): Promise<T> {
  let res: Response
  try {
    res = await fetchImpl(`${BASE}${path}`, { method: 'POST', ...init })
  } catch {
    throw new ApiError(0, 'The backend is unreachable.')
  }
  if (!res.ok) {
    const text = await res.text()
    let detail = text.slice(0, 200)
    try {
      const parsed = JSON.parse(text) as { detail?: unknown }
      if (typeof parsed.detail === 'string') detail = parsed.detail
    } catch {
      // not JSON: keep the text
    }
    throw new ApiError(res.status, detail || `HTTP ${res.status}`)
  }
  return (await res.json()) as T
}

export interface IntakeInput {
  bom: BomRow[]
  cad: CadMeasure | null
  /** null = only the BOM and CAD rules run (no Gemini). */
  answers: OpenAnswers | null
}

export function intake(
  input: IntakeInput,
  liveToken?: string | null,
  fetchImpl: typeof fetch = fetch,
): Promise<IntakeResult> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (liveToken) headers['X-Live-Token'] = liveToken
  return post('/api/intake', { headers, body: JSON.stringify({ robot_kind: 'wheeled', ...input }) }, fetchImpl)
}

export function measureCad(file: Blob, fetchImpl: typeof fetch = fetch): Promise<CadMeasure> {
  return post('/api/intake/cad', { headers: { 'Content-Type': 'application/octet-stream' }, body: file }, fetchImpl)
}
