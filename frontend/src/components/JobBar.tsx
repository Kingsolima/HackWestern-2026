import { STAGE_ORDER } from '../events'
import type { JobState } from '../job'
import type { ProjectId } from '../projects'
import { ProjectSwitcher } from './ProjectSwitcher'

interface Props {
  state: JobState
  onStart: () => void
  /** Shown only with ?live=1 in the URL: starts a real (credit-spending) TinyFish job. */
  onStartLive?: () => void
  project: ProjectId
  /** Omit to hide the project switcher (v4, behind ?v4=1 until the backend sends projects). */
  onProjectChange?: (id: ProjectId) => void
}

export function JobBar({ state, onStart, onStartLive, project, onProjectChange }: Props) {
  const running = state.connection === 'starting' || state.connection === 'streaming'
  const current = state.stage ? STAGE_ORDER.indexOf(state.stage) : -1
  const failed = state.stage === 'FAILED' || state.stage === 'DEGRADED'

  return (
    <section className="panel jobbar">
      <div className="jobbar-row">
        {onProjectChange && (
          <ProjectSwitcher value={project} onChange={onProjectChange} disabled={running} />
        )}
        <button className="primary" onClick={onStart} disabled={running}>
          {running ? 'Running…' : state.jobId ? 'Run again' : 'Find and Redesign'}
        </button>
        {onStartLive && (
          <button className="secondary" onClick={onStartLive} disabled={running}>
            Run live
          </button>
        )}
        {state.mode && (
          <span className={`badge badge-${state.mode}`}>{state.mode.toUpperCase()}</span>
        )}
        {state.jobId && <span className="muted">job {state.jobId}</span>}
        {failed && <span className="badge badge-bad">{state.stage}</span>}
      </div>
      {state.jobId && (
        <ol className="stepper">
          {STAGE_ORDER.map((stage, i) => (
            <li
              key={stage}
              className={i < current ? 'done' : i === current ? 'current' : ''}
              title={stage}
            >
              {stage.replace('_', ' ').toLowerCase()}
            </li>
          ))}
        </ol>
      )}
      {state.errors.map((e) => (
        <p key={e} className="error">
          {e}
        </p>
      ))}
    </section>
  )
}
