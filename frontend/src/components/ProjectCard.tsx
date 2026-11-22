import type { Criteria, Project } from '../events'
import { domesticShare, type ClaimRow } from '../job'

const label = (s: string) => s.replaceAll('_', ' ')

/** Who the project is, what we know about it (verified from a quote, or stated by the team), and
 * the requirements the rules derived from those facts. */
export function ProjectCard({
  project,
  criteria,
  claims,
}: {
  project: Project
  criteria: Criteria | null
  claims: ClaimRow[]
}) {
  const claimById = new Map(claims.map((c) => [c.claim.id, c.claim]))
  const domestic = criteria?.domestic_threshold != null ? domesticShare(project.bom) : null

  return (
    <section className="panel">
      <h2>
        {project.name} <span className="muted">· {project.kind}</span>
      </h2>
      <p>
        <strong>Robot:</strong> {project.robot} · <strong>Use:</strong> {project.use_case}
      </p>

      <h3>Facts</h3>
      <ul className="facts">
        {project.fact_basis.map((f) => {
          const claim = f.claim_id ? claimById.get(f.claim_id) : undefined
          return (
            <li key={f.field}>
              {f.basis === 'verified' ? (
                claim ? (
                  <a
                    className="badge badge-verified"
                    href={claim.source.url}
                    target="_blank"
                    rel="noreferrer"
                    title={`“${claim.quote}”`}
                  >
                    verified
                  </a>
                ) : (
                  <span className="badge badge-verified">verified</span>
                )
              ) : (
                <span className="badge badge-stated" title="stated by the team, not checked">
                  stated
                </span>
              )}{' '}
              {label(f.field)}: <strong>{f.value}</strong>
            </li>
          )
        })}
      </ul>

      {criteria && (
        <>
          <h3>Requirements</h3>
          <p>
            <strong>Objectives:</strong> {criteria.objectives.map(label).join(', ') || 'none'}
          </p>
          {criteria.max_lead_time_days != null && (
            <p>
              <strong>Max lead time:</strong> {criteria.max_lead_time_days} days
            </p>
          )}
          {criteria.blocking_lists.length > 0 && (
            <p>
              <strong>Blocking lists:</strong> {criteria.blocking_lists.map(label).join(', ')}
            </p>
          )}
          {criteria.domestic_threshold != null && (
            <p>
              <strong>Domestic content:</strong>{' '}
              {domestic ? `${domestic.pct}%` : 'not known'} (needs{' '}
              {Math.round(criteria.domestic_threshold * 100)}%)
              {domestic && domestic.unpriced > 0 && (
                <span className="muted"> · {domestic.unpriced} unpriced lines left out</span>
              )}
            </p>
          )}
          <ul className="notes">
            {criteria.reasons.map((r) => (
              <li key={`${r.rule_id}:${r.text}`}>
                <code>{r.rule_id}</code> {r.text}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}
