import { describe, expect, it } from 'vitest'
import { stepsFor } from './questions'

describe('stepsFor', () => {
  it('drops the drivetrain question for an arm', () => {
    expect(stepsFor(false)).toEqual(['who', 'market', 'limits', 'drivetrain', 'review'])
    expect(stepsFor(true)).toEqual(['who', 'market', 'limits', 'review'])
  })

  it('returns the same array each call, so an effect depending on it does not loop', () => {
    expect(stepsFor(true)).toBe(stepsFor(true))
    expect(stepsFor(false)).toBe(stepsFor(false))
  })
})
