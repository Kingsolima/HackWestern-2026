import { fact } from '../onboarding/answers'
import type { CompanyFact } from '../onboarding/intake'

const HEADLINE = new Set(['company_name', 'kind', 'robot_name', 'use_case'])

/** Who the team is, as read from their onboarding answers. Every fact is stated by the user, not
 * checked, so each carries the "stated" badge (same meaning as on the v4 project card); hovering
 * it shows the words it came from. */
export function CompanyCard({ company }: { company: CompanyFact[] }) {
  const kind = fact(company, 'kind')
  const useCase = fact(company, 'use_case')
  return (
    <section className="panel">
      <h2>
        {fact(company, 'company_name') ?? 'Your team'}
        {kind && <span className="muted"> · {kind === 'club' ? 'club or research team' : 'company'}</span>}
      </h2>
      <p>
        <strong>Robot:</strong> {fact(company, 'robot_name') ?? 'not named'}
        {useCase && (
          <>
            {' '}
            · <strong>Use:</strong> {useCase}
          </>
        )}
      </p>
      <ul className="facts">
        {company
          .filter((c) => !HEADLINE.has(c.field))
          .map((c) => (
            <li key={c.field}>
              <span
                className="badge badge-stated"
                title={c.quote ? `“${c.quote}”` : 'not in your answers: the demo value'}
              >
                {c.quote ? 'stated' : 'default'}
              </span>{' '}
              {c.label}: <strong>{c.value}</strong>
            </li>
          ))}
      </ul>
    </section>
  )
}
