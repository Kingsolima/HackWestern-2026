import { Fragment } from 'react'
import { levelAccuracy } from '../accuracy'
import { RISK_FACTORS, type Alternative, type Level } from '../events'
import type { RiskRow } from '../job'

const money = (v: number | null) => (v === null ? '–' : `$${v.toLocaleString()}`)

export function LevelChip({ level, title, children }: { level: Level; title?: string; children?: string }) {
  return (
    <span className={`chip level-${level}`} title={title}>
      <span className={`dot ${levelAccuracy(level)}`} />
      {children ?? level}
    </span>
  )
}

const SCORE_LEVEL: Level[] = ['low', 'medium', 'high', 'high']

/** One 0-3 score. "?" = unknown; "inferred" = from the part's class, not verified. Hover for
 * the evidence and for what is missing. */
function ScoreChip({ name, score }: { name: string; score: Score }) {
  const lines = [
    ...score.reasons,
    ...(score.missing.length ? ['Missing: ' + score.missing.join('; ')] : []),
  ]
  const shown = score.value === null ? '?' : String(score.value)
  return (
    <LevelChip
      level={score.value === null ? 'unknown' : SCORE_LEVEL[score.value]}
      title={lines.join('\n') || undefined}
    >
      {`${name} ${shown}${score.basis === 'inferred' && score.value ? ' inferred' : ''}`}
    </LevelChip>
  )
}

export function PriorityChips({ priority }: { priority: Priority }) {
  return (
    <>
      <ScoreChip name="supply" score={priority.supply} />
      <ScoreChip name="customer" score={priority.customer} />
      <ScoreChip name="impact" score={priority.impact} />
    </>
  )
}

const priorityRange = (p: Priority) => (p.hi > p.lo ? `${p.lo}–${p.hi}` : `${p.lo}`)

function Alternatives({ alts }: { alts: Alternative[] }) {
  return (
    <details>
      <summary>
        {alts.length} alternative{alts.length === 1 ? '' : 's'}
      </summary>
      <table className="nested">
        <thead>
          <tr>
            <th>Part</th>
            <th>Origin</th>
            <th>Price</th>
            <th>Availability</th>
            <th>Checks</th>
            <th>Risk</th>
          </tr>
        </thead>
        <tbody>
          {alts.map((a) => (
            <tr key={a.id}>
              <td>
                {a.manufacturer} {a.part_number}{' '}
                {a.live && <span className="badge badge-live">LIVE FIND</span>}
              </td>
              <td>
                {a.origin_country ?? '?'} {a.origin_tier && <span className="muted">{a.origin_tier}</span>}
              </td>
              <td>{money(a.unit_price_usd)}</td>
              <td>
                {a.availability.replace('_', ' ')}
                {a.lead_time_days != null && ` (${a.lead_time_days} d)`}
              </td>
              <td>{a.verdict ?? <span className="muted">–</span>}</td>
              <td className="chips">
                {a.risk.priority ? (
                  <PriorityChips priority={a.risk.priority} />
                ) : (
                  <LevelChip level={a.risk.overall} />
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  )
}

/** One row per BOM line: three scores (supply exposure, conflict with what this customer said,
 * impact on the robot), their sum as the priority, and the alternatives found. */
export function RiskTable({ rows, alternatives }: { rows: RiskRow[]; alternatives: Record<string, Alternative[]> }) {
  return (
    <section className="panel">
      <h2>Supply risk by part</h2>
      <p className="muted">
        Priority = supply exposure + conflict with what you told us + impact on the robot. “?”
        means the evidence is missing: it widens the range and is never counted as safe.
        “inferred” comes from the kind of part, not from a verified source. Hover a score for
        its evidence.
      </p>
      <table>
        <thead>
          <tr>
            <th>Part</th>
            <th>Domain</th>
            <th>Qty</th>
            <th>Scores (0–3, ? = unknown)</th>
            <th>Priority (0–9)</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ line, risk }) => {
            const alts = alternatives[line.id] ?? []
            return (
              <Fragment key={line.id}>
                <tr>
                  <td>
                    {line.part}
                    {line.manufacturer && <span className="muted"> · {line.manufacturer}</span>}{' '}
                    {line.illustrative && (
                      <span className="badge badge-illustrative" title="real part of the right class, not the company's actual BOM">
                        ILLUSTRATIVE
                      </span>
                    )}
                    {line.sources.length > 0 && (
                      <span className="muted">
                        {' '}
                        {line.sources.map((url, i) => (
                          <a key={url} href={url} target="_blank" rel="noreferrer" title={url}>
                            [{i + 1}]
                          </a>
                        ))}
                      </span>
                    )}
                  </td>
                  <td>{line.domain}</td>
                  <td>{line.qty}</td>
                  <td className="chips">
                    {risk.priority && <PriorityChips priority={risk.priority} />}
                    {!risk.priority && RISK_FACTORS.map((name) => {
                      const f = risk.factors.find((x) => x.name === name)
                      return (
                        <LevelChip
                          key={name}
                          level={f?.level ?? 'unknown'}
                          title={f ? [`${f.value} · ${f.reason}`, ...f.source_urls].join('\n') : 'not assessed'}
                        >
                          {name}
                        </LevelChip>
                      )
                    })}
                  </td>
                  <td>
                    {risk.priority ? (
                      <LevelChip level={risk.priority.level}>
                        {`${risk.priority.level} ${priorityRange(risk.priority)}`}
                      </LevelChip>
                    ) : (
                      <LevelChip level={risk.overall} />
                    )}
                  </td>
                </tr>
                {alts.length > 0 && (
                  <tr className="subrow">
                    <td colSpan={5}>
                      <Alternatives alts={alts} />
                    </td>
                  </tr>
                )}
              </Fragment>
            )
          })}
        </tbody>
      </table>
    </section>
  )
}
