import type { PartDetail } from '../partDetail'
import { ACTION_LABEL, availabilityText, firstClause, money } from '../report'
import { LevelChip, PriorityChip } from './Chips'
import { ScoreLine, Src } from './Report'

interface Props {
  d: PartDetail
  /** Opens this part's line in the report; absent until the report exists. */
  onReport?: () => void
  onClose: () => void
}

const SCORES = [
  ['supply', 'Supply exposure'],
  ['customer', 'Conflict with what you told us'],
  ['impact', 'Impact on the robot'],
] as const

/** A part clicked in the 3D view: its BOM line, each risk factor with its source, the priority
 * breakdown, the recommended action and the alternatives the agents found. */
export function PartCard({ d, onReport, onClose }: Props) {
  const { line, risk, recommendation: r } = d
  const delta = r?.cost_delta_usd
  return (
    <aside className="part-card frame" aria-label={`Part: ${d.title}`}>
      <div className="pc-head">
        <div className="label">Part{line ? ` · ${line.domain}` : ''}</div>
        <button type="button" className="pc-close" onClick={onClose} aria-label="Close">
          ×
        </button>
      </div>
      <h2>{d.title}</h2>
      <p className="pc-facts">{d.facts.join(' · ')}</p>
      {line?.part_number && <p className="fine">Part number {line.part_number}</p>}
      {d.role && <p className="pc-role">{d.role}</p>}
      {d.candidates.length > 0 && (
        <p className="help">The parts list doesn't say which line this is. It could be: {d.candidates.join(', ')}.</p>
      )}

      {risk && (
        <section>
          <h3>
            Supply risk {risk.priority ? <PriorityChip priority={risk.priority} /> : <LevelChip level={risk.overall} />}
            {risk.blocked && <span className="tag lo">blocked</span>}
          </h3>
          <ul className="pc-factors">
            {risk.factors.map((f) => (
              <li key={f.name}>
                <LevelChip level={f.level}>{f.name}</LevelChip>
                <div>
                  <b>{f.value}</b> · {f.reason}
                  {f.source_urls.length > 0 && (
                    <div className="fine">
                      {f.source_urls.map((u) => (
                        <span key={u} className="src-chip">
                          <Src url={u} />
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ul>
          {risk.priority && (
            <div className="pc-scores">
              {SCORES.map(([k, name]) => (
                <ScoreLine key={k} name={name} score={risk.priority![k]} />
              ))}
            </div>
          )}
        </section>
      )}

      {r && (
        <section>
          <h3>
            Recommended: {ACTION_LABEL[r.action]}
            {r.rank && <span className="muted"> · #{r.rank}</span>}
          </h3>
          <p className="help">{firstClause(r.reason)}</p>
          <p className="fine">
            Risk {r.risk_before} → {r.risk_after}
            {delta != null && ` · cost ${delta >= 0 ? '+' : ''}${money(delta)} per unit`}
          </p>
        </section>
      )}

      {d.alternatives.length > 0 && (
        <section>
          <h3>Alternatives found</h3>
          <ul className="pc-alts">
            {d.alternatives.map((a) => (
              <li key={a.id} className={a.id === r?.alternative_id ? 'picked' : ''}>
                <span className="mono">
                  {a.manufacturer} {a.part_number}
                </span>
                <span className="muted">
                  {a.origin_country ?? '?'} · {money(a.unit_price_usd)} · {availabilityText(a)}
                  {a.verdict && ` · checks: ${a.verdict}`}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {!risk && line === null && d.candidates.length === 0 && (
        <p className="fine">Supply risk shows here once a job has mapped the parts list.</p>
      )}
      {onReport && line && (
        <button type="button" className="btn pc-report" onClick={onReport}>
          See in report →
        </button>
      )}
    </aside>
  )
}
