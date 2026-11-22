import type { Outcome } from '../events'
import type { Run } from '../job'

const OUTCOME: Record<Outcome, { icon: string; label: string }> = {
  success: { icon: '✅', label: 'verified source' },
  blocked: { icon: '⚠️', label: 'blocked' },
  auth_required: { icon: '⚠️', label: 'needs login' },
  incomplete: { icon: '⚠️', label: 'incomplete' },
  not_found: { icon: '❌', label: 'not found' },
  error: { icon: '❌', label: 'error' },
}

function Tile({ run }: { run: Run }) {
  // A replayed run's streaming URL points at a browser that no longer exists, so only live
  // runs get the iframe; replays show the recorded steps instead.
  const showStream = run.live && run.streamingUrl && run.outcome === null
  const outcome = run.outcome ? OUTCOME[run.outcome] : null
  return (
    <article className="tile">
      <header className="tile-head">
        <span className={`badge ${run.live ? 'badge-live' : 'badge-replay'}`}>
          {run.live ? 'LIVE' : 'REPLAY'}
        </span>
        <strong>{run.site}</strong>
        <span className="muted">{run.worker}</span>
      </header>
      {showStream ? (
        <iframe
          className="tile-stream"
          src={run.streamingUrl ?? undefined}
          title={`Agent browser for ${run.site}`}
          referrerPolicy="no-referrer"
        />
      ) : (
        <ol className="tile-steps">
          {run.steps.length === 0 ? <li className="muted">starting…</li> : null}
          {run.steps.map((s, i) => (
            <li key={i}>{s}</li>
          ))}
        </ol>
      )}
      <footer className="tile-foot">
        {outcome ? (
          <span title={run.reason ?? ''}>
            {outcome.icon} {outcome.label}
            {run.reason ? <span className="muted"> · {run.reason}</span> : null}
          </span>
        ) : (
          <span className="muted">running…</span>
        )}
        {run.url && (
          <a href={run.url} target="_blank" rel="noreferrer">
            page
          </a>
        )}
      </footer>
    </article>
  )
}

export function AgentTiles({ runs }: { runs: Run[] }) {
  return (
    <section className="panel">
      <h2>Agent swarm</h2>
      {runs.length === 0 ? (
        <p className="muted">Click Find and Redesign to send the agents out.</p>
      ) : (
        <div className="tiles">
          {runs.map((r) => (
            <Tile key={r.runId} run={r} />
          ))}
        </div>
      )}
    </section>
  )
}
