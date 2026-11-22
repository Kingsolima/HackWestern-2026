import type { Design, SpecCheck } from '../events'

const MARK: Record<SpecCheck['verdict'], string> = { pass: '✅', fail: '❌', review: '❔' }
const num = (v: number | null) => (v === null ? '–' : Number(v.toPrecision(3)).toString())

/** The job's engineering checks: one row per candidate motor, one column per check. Each cell is
 * the measured value against the requirement; hover for the rule's note. */
export function ChecksTable({
  checks,
  candidates,
}: {
  checks: Record<string, SpecCheck[]>
  candidates: Design[]
}) {
  const ids = Object.keys(checks)
  const columns = [...new Set(ids.flatMap((id) => checks[id].map((c) => c.check)))]
  return (
    <section className="panel">
      <h2>Engineering checks</h2>
      {ids.length === 0 ? (
        <p className="muted">No candidate has been checked yet.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Motor</th>
              <th>Verdict</th>
              <th>Fit</th>
              {columns.map((name) => (
                <th key={name}>{name.replaceAll('_', ' ')}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ids.map((id) => {
              const design = candidates.find((d) => d.candidate_id === id)
              return (
                <tr key={id}>
                  <td>{design?.motor ?? id}</td>
                  <td>{design?.verdict ? (design.verdict === 'pass' ? 'Pass*' : design.verdict) : '–'}</td>
                  <td>{design?.fit_badge?.replaceAll('_', ' ') ?? '–'}</td>
                  {columns.map((name) => {
                    const c = checks[id].find((x) => x.check === name)
                    return c ? (
                      <td key={name} title={c.note}>
                        {MARK[c.verdict]} {num(c.value)} / {num(c.threshold)} {c.unit}
                      </td>
                    ) : (
                      <td key={name} className="muted">
                        –
                      </td>
                    )
                  })}
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
      <p className="muted">
        Value / requirement. Pass* = passes the checks we implemented, not engineering certification.
      </p>
    </section>
  )
}
