// Mirrors backend/app/schemas.py. Keep in sync (or generate from /openapi.json later).

export type AgentStatus = 'success' | 'blocked' | 'not_found' | 'auth_required' | 'incomplete'
export type Verdict = 'rejected' | 'review' | 'pass'
export type Fit = 'drop_in' | 'close' | 'needs_review'
export type Objective = 'cost' | 'performance' | 'us_first'

export interface BomRow {
  part: string
  category: string
  qty: number
  unit_cost_usd: string
  origin: string
  supply_risk?: string | null
}

export interface Robot {
  name: string
  final_assembly_country: string
  bom: BomRow[]
}

export interface ComplianceCard {
  domestic_pct: number
  thresholds_pct: number[]
  us_final_assembly: boolean
  supply_risks: string[]
  notes: string[]
}

export interface MotorCandidate {
  status: AgentStatus
  reason: string
  manufacturer?: string | null
  part_number?: string | null
  nema_frame?: string | null
  rated_torque_nm?: number | null
  rated_speed_rpm?: number | null
  voltage_v?: number | null
  price_usd?: number | null
  country_of_origin?: string | null
  product_url?: string | null
}

export interface CheckRow {
  check: string
  value: number | null
  threshold: number | null
  passed: boolean | null
  sources: string[]
}

export interface CheckResult {
  candidate: string
  verdict: Verdict
  fit: Fit
  rows: CheckRow[]
}

export interface DesignVariant {
  design_id: string
  objective: Objective
  motor: string
  cost_usd: string
  domestic_pct: number
  glb_url?: string | null
  step_url?: string | null
}
