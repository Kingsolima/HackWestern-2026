import type { CadRobot } from './events'

/** Prepared demo projects (data/projects/<id>.json on the backend). Without one, the job runs on
 * the user's onboarded robot, drawn as the robot model the backend picks for it. */
export const PROJECTS = [
  { id: 'stretch', label: 'Stretch' },
  { id: 'ar4_club', label: 'AR4 club' },
] as const

export type ProjectId = (typeof PROJECTS)[number]['id']

/** CAD-worker paths (/designs/{id}/glb) are served to the browser through the /cad proxy. */
export const cadUrl = (path: string) => `/cad${path}`

/** The robot model each prepared project is drawn as (cad_robot in its file). */
export const PROJECT_ROBOT: Record<ProjectId, CadRobot> = { stretch: 'stretch', ar4_club: 'ar4' }

const STARTERS: Record<CadRobot, { src: string; title: string }> = {
  wheeled: { src: '/cad/designs/starter/glb', title: 'Generic wheeled model / NEMA 23 drive' },
  ar4: { src: '/cad/designs/starter_ar4/glb', title: 'AR4 arm / NEMA 23 J2 motor' },
  stretch: { src: '/cad/designs/starter_stretch/glb', title: 'Stretch (illustrative) / NEMA 34 shoulder' },
}

/** The CAD worker's starter design for a robot model, shown before a job builds the redesign. */
export const starterModel = (robot: CadRobot) => STARTERS[robot]
