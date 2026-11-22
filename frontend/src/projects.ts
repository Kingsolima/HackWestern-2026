/** Prepared demo projects (data/projects/<id>.json on the backend). Without one, the job runs on
 * the user's onboarded robot, drawn as the generic wheeled model. */
export const PROJECTS = [
  { id: 'stretch', label: 'Stretch' },
  { id: 'ar4_club', label: 'AR4 club' },
] as const

export type ProjectId = (typeof PROJECTS)[number]['id']

/** CAD-worker paths (/designs/{id}/glb) are served to the browser through the /cad proxy. */
export const cadUrl = (path: string) => `/cad${path}`

/** The CAD worker's starter design for a project, shown before a job builds the redesign. */
export function starterModel(project: ProjectId | null): { src: string; title: string } {
  if (project === 'ar4_club') return { src: '/cad/designs/starter_ar4/glb', title: 'AR4 arm / NEMA 23 J2 motor' }
  if (project === 'stretch') return { src: '/cad/designs/starter_stretch/glb', title: 'Stretch (illustrative) / NEMA 34 shoulder' }
  return { src: '/cad/designs/starter/glb', title: 'Generic wheeled model / NEMA 23 drive' }
}
