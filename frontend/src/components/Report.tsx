import { useEffect, useRef, useState } from 'react'
import { outcomeAccuracy, type Accuracy } from '../accuracy'
import { RISK_FACTORS, type Claim, type Recommendation, type Score } from '../events'
import type { JobState, RiskRow } from '../job'
import type { Onboarded } from '../onboarding/answers'
import {
  ACTION_LABEL,
  ACTION_TONE,
  DOMAIN_LABEL,
  actionPlan,
  availabilityText,
  deepLineComparison,
  evidenceBySource,
  firstClause,
  money,
  reportSummary,
  scoreLevel,
  shortPart,
  supplyMap,
  type Action,
  type Cell,
  type DeepLine,
} from '../report'
import type { ComplianceCard } from '../types'
import { LevelChip, PriorityChip } from './Chips'
import { DesignChanges } from './DesignChanges'

interface Props {
  job: JobState
  onboarded: Onboarded | null
  /** The baseline compliance card, when it is right for this robot. */
  card: ComplianceCard | null
  modelNotes: string[]
  /** A BOM line id to open and scroll to (from "See in report" on a 3D part). */
  focus?: string | null
}

const label = (s: string) => s.replaceAll('_', ' ')
const host = (url: string) => {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}
const Dot = ({ tone }: { tone: Accuracy }) => <span className={`dot ${tone}`} />

export function Src({ url }: { url: string }) {
  return url.startsWith('http') ? (
    <a href={url} target="_blank" rel="noreferrer">
      {host(url)}
    </a>
  ) : (
    <span className="mono">{url}</span>
  )
}

// ---------- summary ----------

function Summary({ job, deep }: { job: JobState; deep: DeepLine | null }) {
  const { verdict, figures } = reportSummary(job, deep)
  return (
    <section id="summary">
      <h2>Summary</h2>
      {verdict.map((p) => (
        <p key={p} className="lede">
          {p}
        </p>
      ))}
      <div className="figures">
        {figures.map((f) => (
          <div key={f.label} className="figure">
            <div className="v">
              <Dot tone={f.tone} />
              {f.value}
            </div>
            <div className="k">{f.label}</div>
            {f.detail && <div className="d">{f.detail}</div>}
          </div>
        ))}
      </div>
    </section>
  )
}

// ---------- deep line ----------

/** One reading an agent brought back: the value, the quote, where it was read and whether the
 * verifier found the quote there. */
function Reading({ claim: c, reason }: { claim: Claim; reason: string | null }) {
  const kept = reason === null
  return (
    <li className={kept ? '' : 'rejected'}>
      <span className="mono">
        {label(c.field)} = {c.raw_value} {c.raw_unit ?? ''}
      </span>{' '}
      <q>{c.quote}</q>{' '}
      <span className="src-line">
        <Src url={c.source.url} />
        {c.source.run_id ? ' · read by an agent run' : ' · read from the fetched page'}
        {kept ? ` · verified (${label(c.verify_method)})` : ` · not verified: ${reason}`}
      </span>
    </li>
  )
}

function CellView({ cell }: { cell: Cell }) {
  const head = (
    <>
      <Dot tone={cell.tone} />
      {cell.text}
      {cell.margin !== null && <span className="margin">×{cell.margin.toFixed(2)}</span>}
    </>
  )
  if (cell.evidence.length === 0 && cell.rejected.length === 0) return <span className="cell">{head}</span>
  return (
    <details className="cell">
      <summary>
        {head}
        {cell.rejected.length > 0 && cell.evidence.length === 0 && <span className="muted"> · {cell.rejected.length} unconfirmed</span>}
      </summary>
      <ul className="readings">
        {cell.evidence.map((c) => (
          <Reading key={c.id} claim={c} reason={null} />
        ))}
        {cell.rejected.map((r) => (
          <Reading key={r.claim.id} claim={r.claim} reason={r.reason ?? 'not found on the page'} />
        ))}
      </ul>
    </details>
  )
}

function DeepLineSection({ job, deep, modelNotes }: { job: JobState; deep: DeepLine; modelNotes: string[] }) {
  const { line, risk, recommendation } = deep
  const after = job.candidates[0]
  return (
    <section id="deep">
      <h2>Deep line: {deep.part}</h2>
      <p className="lede">{deep.status}</p>
      {line && (
        <dl className="facts-grid">
          <dt>Today</dt>
          <dd>
            {[line.manufacturer, line.part_number].filter(Boolean).join(' ') || line.part} · x{line.qty}
          </dd>
          <dt>Origin</dt>
          <dd>
            {line.origin_country ?? 'unknown'}
            {line.origin_tier && line.origin_tier !== 'none' ? ` (${line.origin_tier})` : ''}
          </dd>
          <dt>Price</dt>
          <dd>{money(line.unit_price_usd)}</dd>
          <dt>Availability</dt>
          <dd>{availabilityText(line)}</dd>
          {risk?.risk.priority && (
            <>
              <dt>Priority</dt>
              <dd>
                <PriorityChip priority={risk.risk.priority} />
              </dd>
            </>
          )}
        </dl>
      )}
      {recommendation && (
        <p className="note">
          <span className={`tag ${ACTION_TONE[recommendation.action]}`}>{ACTION_LABEL[recommendation.action]}</span>{' '}
          {recommendation.reason}
        </p>
      )}

      {deep.options.length > 0 && (
        <div className="scroll-x">
          <table className="grid compare">
            <thead>
              <tr>
                <th>Check</th>
                <th>Needed</th>
                {deep.options.map((o) => (
                  <th key={o.id}>
                    <div className="opt-name">{o.name}</div>
                    <div className="opt-meta">
                      <span className={`tag ${o.verdict === 'pass' ? 'hi' : o.verdict === 'rejected' ? 'lo' : 'mid'}`}>
                        {o.verdict === 'pass' ? 'Pass*' : (o.verdict ?? 'open')}
                      </span>
                      {o.fitBadge && <span className="tag">{label(o.fitBadge)}</span>}
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr className="meta-row">
                <td>Origin</td>
                <td>–</td>
                {deep.options.map((o) => (
                  <td key={o.id}>{o.origin}</td>
                ))}
              </tr>
              <tr className="meta-row">
                <td>Price</td>
                <td>{line ? money(line.unit_price_usd) : '–'} today</td>
                {deep.options.map((o) => (
                  <td key={o.id}>{o.price}</td>
                ))}
              </tr>
              <tr className="meta-row">
                <td>Read from</td>
                <td />
                {deep.options.map((o) => (
                  <td key={o.id} className="muted">
                    {o.sources.join(' · ') || '–'}
                  </td>
                ))}
              </tr>
              {deep.rows.map((r) => (
                <tr key={r.key}>
                  <td>{r.label}</td>
                  <td className="muted">{r.required}</td>
                  {r.cells.map((c, i) => (
                    <td key={deep.options[i].id}>
                      <CellView cell={c} />
                    </td>
                  ))}
                </tr>
              ))}
              <tr className="sum-row">
                <td>Rules it out</td>
                <td />
                {deep.options.map((o) => (
                  <td key={o.id} className={o.failed.length ? 'lo-text' : 'muted'}>
                    {o.failed.join(', ') || 'nothing'}
                  </td>
                ))}
              </tr>
              <tr className="sum-row">
                <td>Still open</td>
                <td />
                {deep.options.map((o) => (
                  <td key={o.id} className="muted">
                    {o.open.join(', ') || 'nothing'}
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
      )}
      <p className="fine">
        Click a value for the quote it was read from. ×n = value / need. Pass* = passes the checks we implemented, not
        engineering certification.
      </p>

      {job.baseline && after && (
        <>
          <h3>What the CAD worker changed for {after.label.replace(/^After:\s*/, '')}</h3>
          <DesignChanges before={job.baseline} after={after} notes={modelNotes} />
        </>
      )}
    </section>
  )
}

// ---------- action plan ----------

const SCORE_NAME: [keyof Pick<NonNullable<RiskRow['risk']['priority']>, 'supply' | 'customer' | 'impact'>, string][] = [
  ['supply', 'Supply exposure'],
  ['customer', 'Conflict with what you told us'],
  ['impact', 'Impact on the robot'],
]

export function ScoreLine({ name, score }: { name: string; score: Score }) {
  return (
    <div className="score">
      <LevelChip level={scoreLevel(score)}>{score.value === null ? '?' : `${score.value}/3`}</LevelChip>
      <div>
        <b>{name}</b>
        {score.basis === 'inferred' && <span className="muted"> · inferred from the kind of part</span>}
        {score.reasons.map((r) => (
          <div key={r}>{r}</div>
        ))}
        {score.missing.length > 0 && <div className="mid-text">Missing: {score.missing.join('; ')}</div>}
      </div>
    </div>
  )
}

function ActionItem({ item, open }: { item: Action; open: boolean }) {
  const { recommendation: r, row, alternative: a } = item
  const part = row?.line.part ?? r.line_id
  const priority = row?.risk.priority
  return (
    <details className="item" open={open}>
      <summary>
        <span className="rank">#{r.rank ?? '–'}</span>
        <span className="name">{shortPart(part)}</span>
        {r.blocked && <span className="tag lo">blocked</span>}
        {priority ? <PriorityChip priority={priority} /> : <LevelChip level={r.risk_before} />}
        <span className="why">{firstClause(r.reason)}</span>
      </summary>
      <div className="item-body">
        <p>{r.reason}</p>
        {part !== shortPart(part) && <p className="muted">{part}</p>}
        {priority && SCORE_NAME.map(([k, name]) => <ScoreLine key={k} name={name} score={priority[k]} />)}
        {a ? (
          <p>
            <b>With:</b> {a.manufacturer} {a.part_number} · {a.origin_country ?? 'origin unknown'}
            {a.origin_tier && a.origin_tier !== 'none' ? ` (${a.origin_tier})` : ''} · {money(a.unit_price_usd)} ·{' '}
            {availabilityText(a)}
            {a.verdict && ` · checks: ${a.verdict}`}
            {r.cost_delta_usd != null && ` · cost ${r.cost_delta_usd >= 0 ? '+' : '−'}$${Math.abs(r.cost_delta_usd)}`}
            {a.live && <span className="tag hi">found live</span>}
          </p>
        ) : (
          r.action !== 'keep' && <p className="muted">No alternative was checked for this part in this run.</p>
        )}
        {r.risk_after !== r.risk_before && (
          <p>
            Risk <LevelChip level={r.risk_before} /> → <LevelChip level={r.risk_after} />
          </p>
        )}
      </div>
    </details>
  )
}

const ACTION_INTRO: Record<string, string> = {
  re_source: 'Replace the source: the part as bought today conflicts with what you need.',
  dual_source: 'Keep the part, add a second source: supply is exposed.',
  investigate: 'Not enough evidence to decide: what is missing is listed per part.',
  keep: 'Fine as it is for you.',
}

function ActionPlan({ job }: { job: JobState }) {
  return (
    <section id="actions">
      <h2>Action plan</h2>
      <p className="note">
        Ranked by risk priority (0–9) = supply exposure + conflict with what you told us + impact on the robot, each
        0–3. A range means some evidence is missing; it is never counted as safe.
      </p>
      {actionPlan(job).map((g) => (
        <ActionGroup key={g.action} action={g.action} items={g.items} />
      ))}
    </section>
  )
}

/** Parts shown per group before "Show all": a long group (42 parts to investigate on the AR4
 * company) would bury everything below it. */
const GROUP_HEAD = 5

function ActionGroup({ action, items }: { action: Recommendation['action']; items: Action[] }) {
  const [all, setAll] = useState(false)
  const shown = all ? items : items.slice(0, GROUP_HEAD)
  return (
    <div className="group">
      <h3>
        <span className={`tag ${ACTION_TONE[action]}`}>{ACTION_LABEL[action]}</span> {items.length} part
        {items.length === 1 ? '' : 's'}
      </h3>
      <p className="muted">{ACTION_INTRO[action]}</p>
      {shown.map((item, i) => (
        <ActionItem
          key={item.recommendation.line_id}
          item={item}
          open={(action === 're_source' || action === 'dual_source') && i < 3}
        />
      ))}
      {items.length > GROUP_HEAD && (
        <button type="button" className="show-all" onClick={() => setAll(!all)}>
          {all ? `Show the top ${GROUP_HEAD}` : `Show all ${items.length}`}
        </button>
      )}
    </div>
  )
}

// ---------- supply map ----------

function SupplyRow({ row, alts }: { row: RiskRow; alts: JobState['alternatives'][string] }) {
  const { line, risk } = row
  return (
    <details className="item" id={`line-${line.id}`}>
      <summary className="supply-sum">
        <span className="name">
          {shortPart(line.part)}
          {line.illustrative && <span className="tag mid">illustrative</span>}
        </span>
        <span>{line.origin_country ?? '??'}</span>
        <span>{money(line.unit_price_usd)}</span>
        <span className="muted">{availabilityText(line)}</span>
        <span className="heat">
          {RISK_FACTORS.map((name) => {
            const f = risk.factors.find((x) => x.name === name)
            return (
              <span
                key={name}
                className={`heat-cell level-${f?.level ?? 'unknown'}`}
                title={f ? `${name}: ${f.value} (${f.reason})` : `${name}: not assessed`}
              />
            )
          })}
        </span>
        {risk.priority ? <PriorityChip priority={risk.priority} /> : <LevelChip level={risk.overall} />}
      </summary>
      <div className="item-body">
        <p className="muted">
          {line.part}
          {line.manufacturer && ` · ${line.manufacturer}`}
          {line.part_number && ` ${line.part_number}`} · x{line.qty}
          {line.hts_code && ` · HTS ${line.hts_code}`}
        </p>
        <table className="grid factors">
          <tbody>
            {risk.factors.map((f) => (
              <tr key={f.name}>
                <td>
                  <LevelChip level={f.level}>{f.name}</LevelChip>
                </td>
                <td>
                  <b>{f.value}</b> · {f.reason}
                </td>
                <td>
                  {f.source_urls.map((u) => (
                    <span key={u} className="src-chip">
                      <Src url={u} />
                    </span>
                  ))}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {line.notes && <p className="note">{line.notes}</p>}
        {line.sources.length > 0 && (
          <p className="fine">
            Price and origin from:{' '}
            {line.sources.map((u) => (
              <span key={u} className="src-chip">
                <Src url={u} />
              </span>
            ))}
          </p>
        )}
        {alts.length > 0 && (
          <table className="grid">
            <thead>
              <tr>
                <th>Alternative</th>
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
                    {a.manufacturer} {a.part_number} {a.live && <span className="tag hi">found live</span>}
                  </td>
                  <td>
                    {a.origin_country ?? '?'} {a.origin_tier && a.origin_tier !== 'none' ? a.origin_tier : ''}
                  </td>
                  <td>{money(a.unit_price_usd)}</td>
                  <td>{availabilityText(a)}</td>
                  <td>{a.verdict ?? '–'}</td>
                  <td>{a.risk.priority ? <PriorityChip priority={a.risk.priority} /> : <LevelChip level={a.risk.overall} />}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </details>
  )
}

function SupplyMap({ job }: { job: JobState }) {
  return (
    <section id="supply">
      <h2>Supply map</h2>
      <p className="note">
        Every part, riskiest first within its domain. The five squares are the risk factors, in order:{' '}
        {RISK_FACTORS.join(', ')}. Open a part for each factor's reading and source.
      </p>
      {supplyMap(job).map((g) => (
        <div key={g.domain} className="group">
          <h3>
            {DOMAIN_LABEL[g.domain]} <span className="muted">· {g.rows.length} parts</span>{' '}
            {(['high', 'medium', 'low', 'unknown'] as const)
              .filter((l) => g.counts[l] > 0)
              .map((l) => (
                <LevelChip key={l} level={l}>{`${g.counts[l]} ${l}`}</LevelChip>
              ))}
          </h3>
          {g.rows.map((r) => (
            <SupplyRow key={r.line.id} row={r} alts={job.alternatives[r.line.id] ?? []} />
          ))}
        </div>
      ))}
    </section>
  )
}

// ---------- requirements ----------

function Requirements({ job, onboarded, card }: Pick<Props, 'job' | 'onboarded' | 'card'>) {
  const p = job.project
  const claimById = new Map(job.claims.map((c) => [c.claim.id, c.claim]))
  const params = p ? Object.entries(p.robot_params).filter(([, v]) => typeof v === 'number' || typeof v === 'string') : []
  return (
    <section id="requirements">
      <h2>Your requirements</h2>
      {p ? (
        <>
          <p className="lede">
            {p.name} ({p.kind}) builds the {p.robot}: {p.use_case}
          </p>
          <table className="grid">
            <tbody>
              {p.fact_basis.map((f) => {
                const claim = f.claim_id ? claimById.get(f.claim_id) : undefined
                return (
                  <tr key={`${f.field}:${f.value}`}>
                    <td>{label(f.field)}</td>
                    <td>
                      <b>{f.value}</b>
                    </td>
                    <td>
                      {f.basis === 'verified' ? (
                        <span className="tag hi">verified</span>
                      ) : (
                        <span className="tag">stated by you</span>
                      )}{' '}
                      {claim && (
                        <>
                          <q>{claim.quote}</q> <Src url={claim.source.url} />
                        </>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </>
      ) : (
        onboarded && (
          <table className="grid">
            <tbody>
              {onboarded.company.map((c) => (
                <tr key={c.field}>
                  <td>{c.label}</td>
                  <td>
                    <b>{c.value}</b>
                  </td>
                  <td>{c.quote ? <q>{c.quote}</q> : <span className="muted">default</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )
      )}
      {job.criteria && (
        <>
          <h3>What we check against, and why</h3>
          <ul className="reasons">
            {job.criteria.reasons.map((r) => (
              <li key={`${r.rule_id}:${r.text}`}>
                <span className="mono muted">{r.rule_id}</span> {r.text}
              </li>
            ))}
          </ul>
        </>
      )}
      {params.length > 0 && (
        <>
          <h3>{p?.robot_kind === 'arm' ? 'Joint the motor drives' : 'Drivetrain'}</h3>
          <dl className="facts-grid">
            {params.map(([k, v]) => (
              <div key={k} className="contents">
                <dt>{label(k)}</dt>
                <dd>{String(v)}</dd>
              </div>
            ))}
          </dl>
        </>
      )}
      {!p && card && (
        <>
          <h3>Compliance</h3>
          <p>
            {card.domestic_pct}% domestic content (thresholds {card.thresholds_pct.join(' / ')}%) · US final assembly:{' '}
            {card.us_final_assembly ? 'yes' : 'no'} · supply risks: {card.supply_risks.join(', ') || 'none flagged'}
          </p>
          <ul className="reasons">
            {card.notes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}

// ---------- evidence ----------

function Evidence({ job }: { job: JobState }) {
  const runs = job.runOrder.map((id) => job.runs[id]).filter(Boolean)
  return (
    <section id="evidence">
      <h2>Evidence</h2>
      <p className="note">
        Every reading the agents brought back. A reading counts only when its quote is found on the page it came from; the
        rest never reach a check.
      </p>
      {evidenceBySource(job).map((g) => (
        <details key={g.host} className="item">
          <summary>
            <span className="name">{g.host}</span>
            <span>
              <Dot tone="hi" />
              {g.verified.length} verified
            </span>
            <span>
              <Dot tone={g.rejected.length ? 'lo' : 'none'} />
              {g.rejected.length} not verified
            </span>
          </summary>
          <ul className="readings">
            {[...g.verified, ...g.rejected].map((r) => (
              <Reading key={r.claim.id} claim={r.claim} reason={r.verified ? null : (r.reason ?? 'not found on the page')} />
            ))}
          </ul>
        </details>
      ))}
      <h3>Agent runs</h3>
      <table className="grid">
        <thead>
          <tr>
            <th>Site</th>
            <th>Task</th>
            <th>Kind</th>
            <th>Outcome</th>
            <th>Time</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((r) => (
            <tr key={r.runId}>
              <td>{r.site}</td>
              <td>{label(r.worker)}</td>
              <td className="muted">{r.product}</td>
              <td>
                <Dot tone={outcomeAccuracy(r.outcome)} />
                {r.outcome ? label(r.outcome) : 'running'}
                {r.reason && <div className="muted">{r.reason}</div>}
              </td>
              <td className="muted">{r.durationS != null ? `${Math.round(r.durationS)} s` : '–'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}

// ---------- page ----------

/** The report tab: one page from the decision down to the evidence, with a contents list. */
export function Report({ job, onboarded, card, modelNotes, focus }: Props) {
  const page = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!focus) return
    const el = page.current?.querySelector<HTMLDetailsElement>(`#line-${CSS.escape(focus)}`)
    if (!el) return
    el.open = true
    el.classList.add('flash')
    el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    const t = setTimeout(() => el.classList.remove('flash'), 1800)
    return () => clearTimeout(t)
  }, [focus])
  const deep = deepLineComparison(job)
  const sections: [string, string, boolean][] = [
    ['summary', 'Summary', true],
    ['deep', deep ? `Deep line: ${deep.part}` : 'Deep line', deep !== null],
    ['actions', 'Action plan', job.recommendations.length > 0],
    ['supply', 'Supply map', job.riskLines.length > 0],
    ['requirements', 'Your requirements', true],
    ['evidence', 'Evidence', job.claims.length > 0 || job.runOrder.length > 0],
  ]
  const go = (id: string) => page.current?.querySelector(`#${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  return (
    <div className="page report-page" ref={page}>
      <nav className="toc" aria-label="Report sections">
        {sections
          .filter(([, , on]) => on)
          .map(([id, title]) => (
            <button key={id} type="button" onClick={() => go(id)}>
              {title}
            </button>
          ))}
      </nav>
      <article className="report-body">
        <Summary job={job} deep={deep} />
        {deep && <DeepLineSection job={job} deep={deep} modelNotes={modelNotes} />}
        {job.recommendations.length > 0 && <ActionPlan job={job} />}
        {job.riskLines.length > 0 && <SupplyMap job={job} />}
        <Requirements job={job} onboarded={onboarded} card={card} />
        {(job.claims.length > 0 || job.runOrder.length > 0) && <Evidence job={job} />}
      </article>
    </div>
  )
}
