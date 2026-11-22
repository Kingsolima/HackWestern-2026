/** Demo projects (data/projects/<id>.json on the backend). '' = today's wheeled demo robot. */
export const PROJECTS = [
  { id: '', label: 'Wheeled demo' },
  { id: 'stretch', label: 'Stretch' },
  { id: 'ar4_club', label: 'AR4 club' },
] as const

export type ProjectId = (typeof PROJECTS)[number]['id']
