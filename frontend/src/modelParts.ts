// What each part of a CAD-worker model is: its role in the job, and what the hover label says.
// Node names come from the CAD worker's assemblies (cad/cad_worker/robot.py, arm.py, stretch.py).

export type PartRole = 'deep' | 'build'

/** One BOM line, whichever shape it came in (onboarding BomRow or a project's BomLine). */
export interface PartLine {
  part: string
  category?: string
  qty: number
  price: number | null
  origin: string | null
}

const ROLES: Record<string, { deep: RegExp; build: RegExp }> = {
  robot: { deep: /^motor_/, build: /^(bracket|hub_adapter)_/ },
  ar4: { deep: /^j2_motor$/, build: /^(mount_plate|bore_sleeve)$/ },
  stretch: { deep: /^shoulder_motor$/, build: /^(mount_plate|bore_sleeve)$/ },
}
const SIDES = new Set(['left', 'right', 'front', 'back', 'l', 'r', 'f', 'b'])

/** The part's role: the deep line once a job runs, the regenerated mount once the redesign is shown. */
export function partRole(root: string, node: string, show: { deep: boolean; build: boolean }): PartRole | null {
  const r = ROLES[root]
  if (!r) return null
  if (show.build && r.build.test(node)) return 'build'
  if (show.deep && r.deep.test(node)) return 'deep'
  return null
}

/** The BOM line a node stands for: motors by category, anything else by a word of its name. */
export function matchLine(node: string, lines: PartLine[]): PartLine | null {
  const words = node.toLowerCase().split('_').filter((w) => w && !SIDES.has(w) && !/^\d+$/.test(w))
  if (words.includes('shaft')) return null
  if (words.includes('motor')) {
    return lines.find((l) => l.category?.toLowerCase() === 'motor') ?? lines.find((l) => /motor/i.test(l.part)) ?? null
  }
  const hits = lines.filter((l) => words.some((w) => w.length > 3 && new RegExp(`\\b${w}`, 'i').test(l.part)))
  return hits.sort((a, b) => a.part.length - b.part.length)[0] ?? null
}

const ROLE_TEXT: Record<PartRole, string> = {
  deep: 'Deep line: agents are finding replacements',
  build: 'Regenerated to fit the new motor',
}

/** Hover text: the BOM name and its qty, price and origin, or the node name when no line matches. */
export function partInfo(node: string, lines: PartLine[], role: PartRole | null): { title: string; detail: string } {
  const line = matchLine(node, lines)
  const title = line?.part ?? node.replaceAll('_', ' ').replace(/^\w/, (c) => c.toUpperCase())
  const facts = line
    ? [`x${line.qty}`, line.price === null ? 'price unknown' : `$${line.price}`, line.origin && line.origin !== 'unknown' ? line.origin : 'origin unknown'].join(' / ')
    : 'Not in your BOM'
  return { title, detail: role ? ROLE_TEXT[role] : facts }
}
