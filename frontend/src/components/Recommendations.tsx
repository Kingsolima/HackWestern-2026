import type { Alternative, Recommendation } from '../events'
import type { RiskRow } from '../job'
import { LevelChip } from './RiskTable'

const ACTION: Record<Recommendation['action'], string> = {
  keep: 'Keep',
  dual_source: 'Dual-source',
  re_source: 'Re-source',
}

const delta = (v: number | null) =>
  v === null ? '–' : `${v > 0 ? '+' : v < 0 ? '−' : ''}$${Math.abs(v).toLocaleString()}`

/** The team's decision per part, already ranked by the backend's rule (most risk removed first,
 * then cheapest). */
export function Recommendations({
  recommendations,
  rows,
  alternatives,
}: {
  recommendations: Recommendation[]
  rows: RiskRow[]
  alternatives: Record<string, Alternative[]>
}) {
  const part = (lineId: string) => rows.find((r) => r.line.id === lineId)?.line.part ?? lineId
  const alt = (r: Recommendation) =>
    r.alternative_id ? alternatives[r.line_id]?.find((a) => a.id === r.alternative_id) : undefined

  return (
    <section className="panel">
      <h2>Recommendations</h2>
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Part</th>
            <th>Action</th>
            <th>With</th>
            <th>Cost Δ</th>
            <th>Risk</th>
            <th>Why</th>
          </tr>
        </thead>
        <tbody>
          {recommendations.map((r, i) => {
            const a = alt(r)
            return (
              <tr key={r.line_id}>
                <td>{i + 1}</td>
                <td>{part(r.line_id)}</td>
                <td>
                  <span className={`action action-${r.action}`}>{ACTION[r.action]}</span>
                </td>
                <td>{a ? `${a.manufacturer} ${a.part_number}` : (r.alternative_id ?? '–')}</td>
                <td>{delta(r.cost_delta_usd)}</td>
                <td className="chips">
                  <LevelChip level={r.risk_before} /> → <LevelChip level={r.risk_after} />
                </td>
                <td>{r.reason}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </section>
  )
}
