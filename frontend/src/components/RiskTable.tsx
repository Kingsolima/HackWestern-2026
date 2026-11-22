import { Fragment } from 'react'
import { RISK_FACTORS, type Alternative, type Level } from '../events'
import type { RiskRow } from '../job'

const money = (v: number | null) => (v === null ? '–' : `$${v.toLocaleString()}`)

export function LevelChip({ level, title, children }: { level: Level; title?: string; children?: string }) {
  return (
    <span className={`chip level-${level}`} title={title}>
      {children ?? level}
    </span>
  )
}

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
              <td>
                <LevelChip level={a.risk.overall} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  )
}

/** One row per BOM line: five risk factors, the overall level (= worst known factor) and the
 * alternatives found for it. */
export function RiskTable({ rows, alternatives }: { rows: RiskRow[]; alternatives: Record<string, Alternative[]> }) {
  return (
    <section className="panel">
      <h2>Supply risk by part</h2>
      <table>
        <thead>
          <tr>
            <th>Part</th>
            <th>Domain</th>
            <th>Qty</th>
            <th>Risk factors</th>
            <th>Overall</th>
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
                    {RISK_FACTORS.map((name) => {
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
                    <LevelChip level={risk.overall} />
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
