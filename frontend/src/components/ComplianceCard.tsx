import type { ComplianceCard as Card } from '../types'

// Two separate tracks: compliance and supply risk. Never mix them.
export function ComplianceCard({ card }: { card: Card | null }) {
  if (!card) return <section className="panel">Loading compliance…</section>
  return (
    <section className="panel">
      <h2>Why this part has to go</h2>
      <p>
        <strong>Compliance:</strong> {card.domestic_pct}% domestic (lines at{' '}
        {card.thresholds_pct.join('% / ')}%)
      </p>
      <p>
        <strong>US final assembly:</strong> {card.us_final_assembly ? 'yes' : 'no, required'}
      </p>
      <p>
        <strong>Supply risk:</strong> {card.supply_risks.join(', ') || 'none flagged'}
      </p>
      <ul className="notes">
        {card.notes.map((n) => (
          <li key={n}>{n}</li>
        ))}
      </ul>
    </section>
  )
}
