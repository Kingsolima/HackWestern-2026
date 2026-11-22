// One color scale for how far to trust a value or a result: green (hi), yellow (mid), red (lo).
// Grey ('none') is for things not assessed yet.

import type { Level, Outcome } from './events'
import type { Source } from './onboarding/intake'

export type Accuracy = 'hi' | 'mid' | 'lo' | 'none'

/** A number on the review screen: the user's words or files are high, an estimate mid, a default low. */
export function specAccuracy(source: Source, evidence: string | null): Accuracy {
  if (source === 'default') return 'lo'
  if (evidence?.startsWith('estimate')) return 'mid'
  return 'hi'
}

/** An agent run: verified source green, partial yellow, anything that failed or was blocked red. */
export function outcomeAccuracy(outcome: Outcome | null): Accuracy {
  if (outcome === null) return 'none'
  if (outcome === 'success') return 'hi'
  if (outcome === 'incomplete') return 'mid'
  return 'lo'
}

/** A supply-risk level: low risk reads green, high risk red. */
export function levelAccuracy(level: Level): Accuracy {
  return ({ low: 'hi', medium: 'mid', high: 'lo', unknown: 'none' } as const)[level]
}
