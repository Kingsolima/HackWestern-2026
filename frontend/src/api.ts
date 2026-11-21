import type { CheckResult, ComplianceCard, DesignVariant, MotorCandidate, Robot } from './types'

const BASE = import.meta.env.VITE_API_URL ?? ''

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}: ${path}`)
  return res.json() as Promise<T>
}

export const api = {
  health: () => req<{ status: string }>('/health'),
  robot: () => req<Robot>('/api/robot'),
  compliance: () => req<ComplianceCard>('/api/compliance'),
  seedCandidates: () => req<MotorCandidate[]>('/api/candidates/seed'),
  checks: (c: MotorCandidate) =>
    req<CheckResult>('/api/checks', { method: 'POST', body: JSON.stringify(c) }),
  designs: () => req<DesignVariant[]>('/api/designs'),
}
