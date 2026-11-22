import { describe, expect, it } from 'vitest'
import { levelAccuracy, outcomeAccuracy, specAccuracy } from './accuracy'

describe('accuracy scale', () => {
  it('rates review numbers by where they came from', () => {
    expect(specAccuracy('answer', 'It weighs 5 kg')).toBe('hi')
    expect(specAccuracy('bom', 'Drive motor x2')).toBe('hi')
    expect(specAccuracy('edited', null)).toBe('hi')
    expect(specAccuracy('cad', 'estimate: 0.5 L of solid x 2.70 g/cm³')).toBe('mid')
    expect(specAccuracy('default', null)).toBe('lo')
  })

  it('treats every failed or blocked run as red', () => {
    expect(outcomeAccuracy(null)).toBe('none')
    expect(outcomeAccuracy('success')).toBe('hi')
    expect(outcomeAccuracy('incomplete')).toBe('mid')
    for (const o of ['blocked', 'auth_required', 'not_found', 'error'] as const) expect(outcomeAccuracy(o)).toBe('lo')
  })

  it('maps risk levels onto the same scale', () => {
    expect([levelAccuracy('low'), levelAccuracy('medium'), levelAccuracy('high'), levelAccuracy('unknown')]).toEqual([
      'hi',
      'mid',
      'lo',
      'none',
    ])
  })
})
