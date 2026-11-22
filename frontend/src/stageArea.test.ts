import { describe, expect, it } from 'vitest'
import { freeArea, type Box } from './stageArea'

const W = 1600
const H = 900
const box = (left: number, right: number, top: number, bottom: number): Box => ({ left, right, top, bottom })

describe('freeArea', () => {
  it('is the whole window with no panels', () => {
    expect(freeArea([], W, H)).toEqual({ shift: 0, width: W })
  })

  it('centres the model between the report on the left and the bay rail on the right', () => {
    // After a job at 1600 x 900: report 18-798, bays 1202-1582, both full height.
    expect(freeArea([box(18, 798, 190, 882), box(1202, 1582, 66, 882)], W, H)).toEqual({ shift: 200, width: 404 })
  })

  it('ignores a dock along the bottom edge and a hidden panel', () => {
    // Onboarding: console bottom-left reaching the middle, bays docked bottom-right, a hidden panel
    // (all zeros, as getBoundingClientRect gives for display: none).
    expect(freeArea([box(18, 558, 380, 882), box(1222, 1582, 842, 882), box(0, 0, 0, 0)], W, H)).toEqual({
      shift: 279,
      width: 1042,
    })
  })

  it('falls back to the whole window when the panels leave too little room', () => {
    expect(freeArea([box(0, 760, 0, H), box(900, W, 0, H)], W, H)).toEqual({ shift: 0, width: W })
  })
})
