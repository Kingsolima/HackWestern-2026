import { PROJECTS, type ProjectId } from '../projects'

interface Props {
  value: ProjectId
  onChange: (id: ProjectId) => void
  disabled?: boolean
}

export function ProjectSwitcher({ value, onChange, disabled }: Props) {
  return (
    <div className="switcher" role="radiogroup" aria-label="Project">
      {PROJECTS.map((p) => (
        <button
          key={p.id}
          role="radio"
          aria-checked={value === p.id}
          className={value === p.id ? 'active' : ''}
          onClick={() => onChange(p.id)}
          disabled={disabled}
        >
          {p.label}
        </button>
      ))}
    </div>
  )
}
