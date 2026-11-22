// Where the 3D model should sit: the part of the window the floating panels leave free.

import { useEffect, useState } from 'react'

export interface Box {
  left: number
  right: number
  top: number
  bottom: number
}

export interface FreeArea {
  /** Horizontal offset (px) of the free area's centre from the window's centre. */
  shift: number
  /** Width (px) of the free area. */
  width: number
}

/** Narrowest free strip worth framing into; below it the model may sit behind a panel. */
const MIN_WIDTH = 240

/**
 * The strip between the panels on the left and those on the right. Only panels that reach the
 * middle band of the window count: a dock along the bottom edge does not hide the model.
 */
export function freeArea(panels: Box[], width: number, height: number): FreeArea {
  let left = 0
  let right = width
  for (const p of panels) {
    if (p.top > height * 0.6 || p.bottom < height * 0.4) continue
    if ((p.left + p.right) / 2 < width / 2) left = Math.max(left, p.right)
    else right = Math.min(right, p.left)
  }
  if (right - left < MIN_WIDTH) return { shift: 0, width }
  return { shift: (left + right) / 2 - width / 2, width: right - left }
}

const PANELS = '.shell.on .console, .shell.on .dossier, .shell.on .part-card'

/** freeArea for the panels on screen, measured again when `layout` changes, when a panel
 * resizes and when the window does. */
export function useFreeArea(layout: string): FreeArea {
  const [area, setArea] = useState<FreeArea>({ shift: 0, width: window.innerWidth })
  useEffect(() => {
    const measure = () => {
      const boxes = [...document.querySelectorAll(PANELS)].map((el) => el.getBoundingClientRect())
      const next = freeArea(boxes, window.innerWidth, window.innerHeight)
      setArea((a) => (Math.abs(a.shift - next.shift) < 1 && Math.abs(a.width - next.width) < 1 ? a : next))
    }
    measure()
    const ro = new ResizeObserver(measure)
    document.querySelectorAll(PANELS).forEach((el) => ro.observe(el))
    window.addEventListener('resize', measure)
    // Panels slide and grow with CSS transitions after a layout change.
    const settle = setTimeout(measure, 800)
    return () => {
      ro.disconnect()
      window.removeEventListener('resize', measure)
      clearTimeout(settle)
    }
  }, [layout])
  return area
}
