import type { ClaimRow } from '../job'

// Every number links to the page it came from. Only verified claims reach the checks.
export function ClaimsList({ claims }: { claims: ClaimRow[] }) {
  return (
    <section className="panel">
      <h2>Claims</h2>
      {claims.length === 0 ? (
        <p className="muted">Facts the agents bring back appear here once the verifier checks them.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th />
              <th>Field</th>
              <th>Value</th>
              <th>Quote on the page</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody>
            {claims.map(({ claim, verified, reason }) => (
              <tr key={claim.id} className={verified ? '' : 'rejected'}>
                <td title={verified ? `verified (${claim.verify_method})` : (reason ?? 'rejected')}>
                  {verified ? '✅' : '❌'}
                </td>
                <td>{claim.field.replaceAll('_', ' ')}</td>
                <td>
                  {claim.raw_value} {claim.raw_unit ?? ''}
                </td>
                <td>
                  <q>{claim.quote}</q>
                  {!verified && reason ? <div className="error">{reason}</div> : null}
                </td>
                <td>
                  <a href={claim.source.url} target="_blank" rel="noreferrer">
                    {new URL(claim.source.url, window.location.href).hostname}
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}
