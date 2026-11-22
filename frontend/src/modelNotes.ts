import type { Project } from './events'

/** How the 3D view describes itself for an onboarded company: the CAD worker draws its generic
 * wheeled template from a few of the user's numbers, never the user's own parts or CAD. */
export function genericModelNotes(project: Project): string[] {
  const notes = [
    "Built from your wheel size, your motor's frame and the new motor's verified shaft and length. Your other parts and your CAD file are not drawn.",
  ]
  if (project.bom.some((l) => /gearbox|gear box|reducer/i.test(l.part)))
    notes.push(
      'Your parts list has a gearbox. This model drives the wheel directly, so the shaft, hub adapter and space rows assume no gearbox: check the gearbox input bore and length yourself.',
    )
  return notes
}
