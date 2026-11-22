import { STAGE_ORDER, stageLabel, type Stage } from '../events'
import { isTerminal, type JobState } from '../job'
import { deepLineComparison, reportSummary } from '../report'

const pad2 = (n: number) => String(n).padStart(2, '0')

interface Props {
  job: JobState
  onRunAgain: () => void
  onRunLive?: () => void
  onOpenReport: () => void
}

const END: Partial<Record<Stage, [string, string]>> = {
  DONE: ['hi', 'Done'],
  DEGRADED: ['mid', 'Degraded: some agents came back empty'],
  FAILED: ['lo', 'Failed'],
}

/** The 3D tab's console after launch: the job's stages while it runs, then the report's opening
 * lines and a way to the full report. */
export function JobConsole({ job, onRunAgain, onRunLive, onOpenReport }: Props) {
  const done = isTerminal(job)
  const current = job.stage ? STAGE_ORDER.indexOf(job.stage) : -1
  const running = job.connection === 'starting' || job.connection === 'streaming'
  const end = job.stage ? END[job.stage] : undefined

  return (
    <div className="job">
      <div className="job-head">
        <span className="label">
          Job / {job.mode ?? 'starting'}
          {job.jobId && <span className="jid"> {job.jobId.slice(0, 8)}</span>}
        </span>
        {end && (
          <span className="label">
            <span className={`dot ${end[0]}`} />
            {end[1]}
          </span>
        )}
      </div>

      {!done ? (
        <ul className="stages">
          {STAGE_ORDER.map((s, i) => {
            const state = i < current ? 'done' : i === current ? 'now' : ''
            return (
              <li key={s} className={state}>
                <span>{pad2(i + 1)}</span>
                <span>{stageLabel(s)}</span>
                <span className="r">{state === 'done' ? 'OK' : state === 'now' ? '…' : ''}</span>
              </li>
            )
          })}
        </ul>
      ) : (
        reportSummary(job, deepLineComparison(job)).verdict.map((p) => (
          <p key={p} className="help">
            {p}
          </p>
        ))
      )}

      {job.errors.map((e) => (
        <p key={e} className="err">
          {e}
        </p>
      ))}
      {(done || job.connection === 'failed') && (
        <div className="nav">
          {done && (
            <button type="button" className="btn go" onClick={onOpenReport}>
              Open the report
            </button>
          )}
          <button type="button" className="btn" onClick={onRunAgain} disabled={running}>
            Run again
          </button>
          {onRunLive && (
            <button type="button" className="btn" onClick={onRunLive} disabled={running}>
              Run live
            </button>
          )}
        </div>
      )}
    </div>
  )
}
