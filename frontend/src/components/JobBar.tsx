import { STAGE_ORDER } from '../events'
import type { JobState } from '../job'

interface Props {
  state: JobState
  onStart: () => void
}

export function JobBar({ state, onStart }: Props) {
  const running = state.connection === 'starting' || state.connection === 'streaming'
  const current = state.stage ? STAGE_ORDER.indexOf(state.stage) : -1
  const failed = state.stage === 'FAILED' || state.stage === 'DEGRADED'

  return (
    <section className="panel jobbar">
      <div className="jobbar-row">
        <button className="primary" onClick={onStart} disabled={running}>
          {running ? 'Running…' : state.jobId ? 'Run again' : 'Find and Redesign'}
        </button>
        {state.mode && (
          <span className={`badge ${state.mode === 'live' ? 'badge-live' : 'badge-replay'}`}>
            {state.mode === 'live' ? 'LIVE' : 'REPLAY'}
          </span>
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
