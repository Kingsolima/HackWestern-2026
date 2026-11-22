import type { OpenAnswers } from './onboarding/questions'
import type { ComplianceCard, Robot } from './types'

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
  /** The recorded example answers behind onboarding's "Use the example". */
  example: () => req<OpenAnswers>('/api/intake/example'),
  compliance: () => req<ComplianceCard>('/api/compliance'),
}
