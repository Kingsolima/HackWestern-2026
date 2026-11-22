// What each part of a CAD-worker model is: its role in the job, and what the hover label says.
// Node names come from the CAD worker's assemblies (cad/cad_worker/robot.py, arm.py, stretch.py).

import type { CadRobot } from './events'
import { isMotorLine } from './onboarding/bomCsv'

export type PartRole = 'deep' | 'build'

/** One BOM line, whichever shape it came in (onboarding BomRow or a project's BomLine). */
export interface PartLine {
  /** The project's BOM line id, when the line came from a job's project. */
  id?: string
  part: string
  category?: string
  qty: number
  price: number | null
  origin: string | null
}

const ROLES: Record<CadRobot, { deep: RegExp; build: RegExp }> = {
  wheeled: { deep: /^motor_/, build: /^(bracket|hub_adapter)_/ },
  ar4: { deep: /^j2_motor$/, build: /^(mount_plate|bore_sleeve)$/ },
  stretch: { deep: /^shoulder_motor$/, build: /^(mount_plate|bore_sleeve)$/ },
}
const SIDES = new Set(['left', 'right', 'front', 'back', 'l', 'r', 'f', 'b'])

/** The part's role: the deep line once a job runs, the regenerated mount once the redesign is shown. */
export function partRole(robot: CadRobot, node: string, show: { deep: boolean; build: boolean }): PartRole | null {
  const r = ROLES[robot]
  if (show.build && r.build.test(node)) return 'build'
  if (show.deep && r.deep.test(node)) return 'deep'
  return null
}

/**
 * The BOM lines a node could stand for. Motors are the lines the backend reads as motors, other
 * parts the lines naming a word of the node. A joint in the node (j2_motor) narrows to lines
 * naming that joint, and a line that is exactly the word (Wheel, not Wheel encoder) wins. More
 * than one result means the BOM does not say which line it is.
 */
export function matchLines(node: string, lines: PartLine[]): PartLine[] {
  const words = node.toLowerCase().split('_').filter((w) => w && !SIDES.has(w) && !/^\d+$/.test(w))
  if (words.includes('shaft')) return []
  // The AR4's link_N meshes are joint N's machined housings, not a part named "link".
  const link = /^link_(\d)$/i.exec(node)
  if (link) {
    const named = lines.filter(
      (l) => new RegExp(`\\bj${link[1]}\\b`, 'i').test(l.part) && !isMotorLine({ part: l.part, category: l.category ?? '' }),
    )
    const machined = named.filter((l) => /machined/i.test(l.part))
    return machined.length ? machined : named
  }
  const joint = words.find((w) => /^j\d$/.test(w))
  const inJoint = (ls: PartLine[]) => {
    const named = ls.filter((l) => joint && new RegExp(`\\b${joint}\\b`, 'i').test(l.part))
    return named.length ? named : ls
  }
  // A gearbox node is the gear head of its joint's motor line ("J2 gear head motor").
  if (words.includes('motor') || words.includes('gearbox')) {
    const motors = inJoint(lines.filter((l) => isMotorLine({ part: l.part, category: l.category ?? '' })))
    return motors.slice(0, 1)
  }
  const hits = inJoint(lines.filter((l) => words.some((w) => w.length > 3 && new RegExp(`\\b${w}`, 'i').test(l.part))))
  const exact = hits.filter((l) => words.includes(l.part.toLowerCase()))
  return exact.length ? exact.slice(0, 1) : hits
}

/** The one BOM line a node stands for, or null when none or several match. */
export function matchLine(node: string, lines: PartLine[]): PartLine | null {
  const hits = matchLines(node, lines)
  return hits.length === 1 ? hits[0] : null
}

const ROLE_TEXT: Record<PartRole, string> = {
  deep: 'Deep line: agents are finding replacements',
  build: 'Regenerated to fit the new motor',
}

/** Hover text: the BOM name and its qty, price and origin; the node name and the candidate lines
 * when several match; or that the part is not in the BOM. */
export function partInfo(node: string, lines: PartLine[], role: PartRole | null): { title: string; detail: string } {
  const hits = matchLines(node, lines)
  const line = hits.length === 1 ? hits[0] : null
  const title = line?.part ?? node.replaceAll('_', ' ').replace(/^\w/, (c) => c.toUpperCase())
  const short = hits.slice(0, 3).map((l) => l.part.split(' (')[0])
  const facts = line
    ? [`x${line.qty}`, line.price === null ? 'price unknown' : `$${line.price}`, line.origin && line.origin !== 'unknown' ? line.origin : 'origin unknown'].join(' / ')
    : hits.length > 1
      ? `In ${hits.length} BOM lines: ${short.join(', ')}${hits.length > 3 ? ', ...' : ''}`
      : 'Not in your BOM'
  return { title, detail: role ? ROLE_TEXT[role] : facts }
}
