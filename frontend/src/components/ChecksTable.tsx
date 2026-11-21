import type { CheckResult } from '../types'

// Every number links to its source. "Pass*" = passes the checks we implemented.
export function ChecksTable({ results }: { results: CheckResult[] }) {
  return (
    <section className="panel">
      <h2>Engineering checks</h2>
      {results.length === 0 ? (
        <p className="muted">No verified candidates yet.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Motor</th>
              <th>Verdict</th>
              <th>Fit</th>
              {results[0].rows.map((r) => (
                <th key={r.check}>{r.check}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {results.map((res) => (
              <tr key={res.candidate}>
                <td>{res.candidate}</td>
                <td>{res.verdict === 'pass' ? 'Pass*' : res.verdict}</td>
                <td>{res.fit}</td>
                {res.rows.map((r) => (
                  <td key={r.check}>
                    {r.passed === null ? '?' : r.passed ? '✅' : '❌'} {r.value?.toFixed(2) ?? '–'}{' '}
                    / {r.threshold?.toFixed(2) ?? '–'}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="muted">Pass* = passes the checks we implemented, not engineering certification.</p>
    </section>
  )
}
