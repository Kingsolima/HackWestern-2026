// The report's reading of a finished job: what to do, why, and the evidence behind it, as plain
// data. The report components only lay this out.

import type { Accuracy } from './accuracy'
import type { Alternative, BomLine, Claim, Design, Domain, Level, Recommendation, Score, SpecCheck } from './events'
import { checkKey, domesticShare, type ClaimRow, type JobState, type RiskRow, type Run } from './job'

/** Plain names for the engineering checks; generic CAD fit rows are named by their `note`. */
const CHECK_LABEL: Record<string, string> = {
  torque_cont: 'Continuous torque',
  torque_peak: 'Peak torque',
  speed: 'Speed',
  voltage: 'Supply voltage',
  fit_envelope: 'Fits the motor space',
  fit_ground: 'Ground clearance',
  fit_shaft: 'Shaft vs wheel bore',
  'fit_cad:j2_envelope': 'J2 motor length vs turret space',
  'fit_cad:shoulder_envelope': 'Shoulder motor length vs space',
  'fit_cad:shaft_to_gearbox_bore': 'Shaft vs gearbox bore',
  'fit_cad:ground_clearance': 'Ground clearance',
  'fit_cad:inboard_envelope': 'Fits inboard of the wheels',
}
export const checkLabel = (c: Pick<SpecCheck, 'check' | 'note'>) =>
  CHECK_LABEL[checkKey(c)] ?? checkKey(c).replace('fit_cad:', 'fit: ').replaceAll('_', ' ')

/** Claim fields that feed each check, to show the readings behind a value or the rejected
 * readings behind a missing one. CAD fit rows read the motor's shaft and body length. */
const CHECK_FIELDS: Record<string, string[]> = {
  torque_cont: ['continuous_torque', 'rated_torque', 'holding_torque'],
  torque_peak: ['peak_torque'],
  speed: ['max_speed', 'rated_speed'],
  voltage: ['supply_voltage_min', 'supply_voltage_max', 'rated_voltage'],
  fit_envelope: ['body_length'],
  fit_shaft: ['shaft_diameter'],
  'fit_cad:shaft_to_gearbox_bore': ['shaft_diameter'],
  'fit_cad:j2_envelope': ['body_length'],
  'fit_cad:shoulder_envelope': ['body_length'],
  'fit_cad:inboard_envelope': ['body_length'],
}

/** Which way each check's requirement points (spec_checks.py and the CAD fit rows). */
const AT_LEAST = new Set(['torque_cont', 'torque_peak', 'speed', 'fit_ground', 'fit_cad:ground_clearance'])
const AT_MOST = new Set([
  'fit_envelope',
  'fit_cad:j2_envelope',
  'fit_cad:shoulder_envelope',
  'fit_cad:inboard_envelope',
  'fit_cad:shaft_to_gearbox_bore',
])

function requiredText(c: SpecCheck): string {
  const key = checkKey(c)
  if (c.threshold === null) return c.check === 'voltage' ? 'your bus voltage within its range' : '–'
  const value = `${num(c.threshold)} ${c.unit}`.trim()
  return AT_LEAST.has(key) ? `at least ${value}` : AT_MOST.has(key) ? `at most ${value}` : value
}

const TONE: Record<SpecCheck['verdict'], Accuracy> = { pass: 'hi', review: 'mid', fail: 'lo' }
const VERDICT_ORDER = { pass: 0, review: 1, rejected: 2 } as const

export const money = (v: number | null | undefined) =>
  v == null ? 'unknown' : `$${v.toLocaleString('en-US', { maximumFractionDigits: 2 })}`
const num = (v: number) => Number(v.toPrecision(3)).toString()
const host = (url: string) => {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}
const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`

/** The head of a backend reason: up to its first ";" or sentence end outside parentheses, so
 * "Conflict: ... made in CN; likely depends on ... (inferred, not verified: ...). No alternative..."
 * reads "Conflict: ... made in CN." The full reason stays one click away. */
export function firstClause(text: string): string {
  let depth = 0
  for (let i = 0; i < text.length; i++) {
    const ch = text[i]
    if (ch === '(') depth++
    else if (ch === ')') depth = Math.max(0, depth - 1)
    else if (depth === 0 && (ch === ';' || (ch === '.' && (i + 1 === text.length || text[i + 1] === ' ')))) {
      return `${text.slice(0, i).trim()}.`
    }
  }
  return text.trim()
}
/** A part's name without its parenthetical or comma tail: "Arm shoulder motor". */
export const shortPart = (part: string) => part.split(/\s*[,(]/)[0].trim() || part
const rawMoney = (raw: string) => (Number.isFinite(Number(raw)) ? money(Number(raw)) : `$${raw}`)

// ---------- deep line: the part the agents searched for, against what they found ----------

export interface Cell {
  /** "0.84 N·m", or "not verified" when no reading survived. */
  text: string
  tone: Accuracy
  /** value / requirement, when both are known. */
  margin: number | null
  /** The verified readings the value was computed from. */
  evidence: Claim[]
  /** Readings the agents brought back for this check that the verifier could not confirm. */
  rejected: ClaimRow[]
  note: string
}

export interface CheckRow {
  key: string
  label: string
  /** What the robot needs, from the requirement formula. */
  required: string
  cells: Cell[]
}

export interface Option {
  id: string
  name: string
  verdict: Design['verdict'] | null
  fitBadge: Design['fit_badge'] | null
  alternative: Alternative | null
  /** Origin and price: the alternative's research row, else the agent's verified reading. */
  origin: string
  price: string
  availability: string
  /** Where the agents read it, and which runs. */
  sources: string[]
  /** Checks it failed, by label: why it cannot be used as it is. */
  failed: string[]
  /** Checks still open, by label, with why: a reading not verified, or a value to review. */
  open: string[]
  design: Design | null
}

export interface DeepLine {
  part: string
  line: BomLine | null
  risk: RiskRow | null
  recommendation: Recommendation | null
  options: Option[]
  rows: CheckRow[]
  /** One sentence: where the search stands. */
  status: string
}

function claimsFor(job: JobState, candidateId: string): ClaimRow[] {
  return job.claims.filter((c) => c.claim.candidate_id === candidateId)
}

function cellFor(check: SpecCheck | undefined, claims: ClaimRow[]): Cell {
  if (!check) return { text: '–', tone: 'none', margin: null, evidence: [], rejected: [], note: '' }
  const fields = CHECK_FIELDS[checkKey(check)] ?? []
  const byId = new Map(claims.map((c) => [c.claim.id, c.claim]))
  const evidence = check.claim_ids.map((id) => byId.get(id)).filter((c): c is Claim => c !== undefined)
  const rejected = claims.filter((c) => !c.verified && fields.includes(c.claim.field))
  const text = check.value === null ? 'not verified' : `${num(check.value)} ${check.unit}`.trim()
  return { text, tone: TONE[check.verdict], margin: check.margin, evidence, rejected, note: check.note }
}

function originOf(alt: Alternative | null, claims: ClaimRow[]): string {
  if (alt?.origin_country) return `${alt.origin_country}${alt.origin_tier && alt.origin_tier !== 'none' ? ` (${alt.origin_tier})` : ''}`
  const c = claims.find((x) => x.claim.field === 'country_of_origin')
  if (!c) return 'unknown'
  return c.verified ? c.claim.raw_value : `${c.claim.raw_value}, not verified`
}

function priceOf(alt: Alternative | null, claims: ClaimRow[]): string {
  if (alt?.unit_price_usd != null) return money(alt.unit_price_usd)
  const c = claims.find((x) => x.claim.field === 'price')
  if (!c) return 'unknown'
  const value = rawMoney(c.claim.raw_value)
  return c.verified ? value : `${value}, not verified`
}

const AVAILABILITY: Record<Alternative['availability'], string> = {
  in_stock: 'in stock',
  lead_time: 'lead time',
  out_of_stock: 'out of stock',
  unknown: 'unknown',
}
export const availabilityText = (a: Pick<Alternative, 'availability' | 'lead_time_days'>) =>
  a.lead_time_days != null ? `${AVAILABILITY[a.availability]}, ${a.lead_time_days} days` : AVAILABILITY[a.availability]

/**
 * The part the agents went deep on, against every candidate they found: each engineering check
 * per candidate with the readings behind it, the readings the verifier threw out, and what is
 * still open. Candidates are ordered usable first (pass, review, rejected), then by checks passed.
 */
export function deepLineComparison(job: JobState): DeepLine | null {
  if (!job.baseline && job.candidates.length === 0) return null
  const lineId = job.project?.deep_line ?? null
  const line = job.project?.bom.find((l) => l.id === lineId) ?? null
  const risk = job.riskLines.find((r) => r.line.id === lineId) ?? null
  const recommendation = job.recommendations.find((r) => r.line_id === lineId) ?? null
  const alts = lineId ? (job.alternatives[lineId] ?? []) : []

  const keys: { key: string; check: SpecCheck }[] = []
  for (const d of job.candidates) {
    for (const c of job.checks[d.candidate_id ?? ''] ?? []) {
      if (!keys.some((k) => k.key === checkKey(c))) keys.push({ key: checkKey(c), check: c })
    }
  }

  const options: Option[] = job.candidates.map((d) => {
    const id = d.candidate_id ?? d.design_id
    const claims = claimsFor(job, id)
    const checks = job.checks[id] ?? []
    const alt = alts.find((a) => a.id === id) ?? null
    const runIds = new Set(claims.map((c) => c.claim.source.run_id).filter(Boolean))
    return {
      id,
      name: [d.manufacturer ?? alt?.manufacturer, d.part_number ?? id].filter((x) => x && x !== 'unknown').join(' '),
      verdict: d.verdict ?? null,
      fitBadge: d.fit_badge ?? null,
      alternative: alt,
      origin: originOf(alt, claims),
      price: priceOf(alt, claims),
      availability: alt ? availabilityText(alt) : 'unknown',
      sources: [...new Set(claims.map((c) => host(c.claim.source.url)))].concat(
        runIds.size ? [`${plural(runIds.size, 'agent run')}`] : [],
      ),
      failed: checks.filter((c) => c.verdict === 'fail').map(checkLabel),
      open: checks
        .filter((c) => c.verdict === 'review')
        .map((c) => `${checkLabel(c)} (${c.value === null ? 'not verified' : 'to review'})`),
      design: d,
    }
  })
  const passed = (o: Option) => (job.checks[o.id] ?? []).filter((c) => c.verdict === 'pass').length
  options.sort(
    (a, b) => VERDICT_ORDER[a.verdict ?? 'review'] - VERDICT_ORDER[b.verdict ?? 'review'] || passed(b) - passed(a),
  )

  const rows: CheckRow[] = keys.map(({ key, check }) => ({
    key,
    label: checkLabel(check),
    required: requiredText(check),
    cells: options.map((o) =>
      cellFor(
        (job.checks[o.id] ?? []).find((c) => checkKey(c) === key),
        claimsFor(job, o.id),
      ),
    ),
  }))

  const part = shortPart(line?.part ?? job.baseline?.motor ?? 'deep line')
  return { part, line, risk, recommendation, options, rows, status: deepStatus(part, options) }
}

/** Where the search for the deep line stands, in one sentence. */
function deepStatus(part: string, options: Option[]): string {
  if (options.length === 0) return `The agents found no candidate for the ${part}.`
  const usable = options.filter((o) => o.verdict === 'pass')
  if (usable.length > 0) {
    const best = usable[0]
    return `${best.name} passes every check we run for the ${part}${best.fitBadge === 'drop_in' ? ' and is a drop-in fit' : ''}.`
  }
  const open = options.filter((o) => o.verdict === 'review')
  if (open.length > 0) {
    const best = open[0]
    return `No candidate passes every check yet. Closest: ${best.name}, with ${plural(best.open.length, 'open check')}: ${best.open.join(', ').toLowerCase()}.`
  }
  const reasons = new Map<string, number>()
  for (const o of options) for (const f of o.failed) reasons.set(f, (reasons.get(f) ?? 0) + 1)
  const why = [...reasons.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([label, n]) => `${label.toLowerCase()} (${n})`)
    .join(', ')
  return `None of the ${plural(options.length, 'candidate')} fits the ${part} as it is. They fail on ${why}.`
}

// ---------- design changes ----------

const mmText = (v: unknown) => (typeof v === 'number' ? `${Number(v.toFixed(2))} mm` : '–')
const yesNo = (v: unknown) => (typeof v === 'boolean' ? (v ? 'yes' : 'no') : '–')
const at = (d: Design, ...path: string[]): unknown =>
  path.reduce<unknown>((o, k) => (o && typeof o === 'object' ? (o as Record<string, unknown>)[k] : undefined), d.fit)

/** What the CAD worker changed between the baseline and a candidate: the wheeled robot's bracket
 * and hub, or an arm's mount plate, bore and motor space. Rows empty on both sides are left out. */
export function designChanges(before: Design, after: Design) {
  const row = (label: string, fmt: (v: unknown) => string, ...path: string[]) => ({
    label,
    before: fmt(at(before, ...path)),
    after: fmt(at(after, ...path)),
  })
  const size = (d: Design) =>
    d.fit.bracket?.width_mm === undefined ? '–' : `${mmText(d.fit.bracket.width_mm)} × ${mmText(d.fit.bracket.height_mm)}`
  return [
    { label: 'Motor', before: before.motor, after: after.motor },
    { label: 'NEMA frame', before: before.frame, after: after.frame },
    row('Bolt square', mmText, 'bracket', 'bolt_spacing_mm'),
    row('Pilot hole', mmText, 'bracket', 'pilot_hole_mm'),
    { label: 'Bracket (w × h)', before: size(before), after: size(after) },
    row('Bracket foot', mmText, 'bracket', 'foot_len_mm'),
    row('Mount plate', mmText, 'mount', 'size_mm'),
    row('Mount bolt square', mmText, 'mount', 'bolt_spacing_mm'),
    row('Mount pilot hole', mmText, 'mount', 'pilot_hole_mm'),
    row('Motor shaft', mmText, 'shaft_diameter_mm'),
    row('Gearbox bore', mmText, 'gearbox_bore_mm'),
    row('Bore sleeve', yesNo, 'needs_bore_sleeve'),
    row('Motor sticks out', mmText, 'j2_protrusion_mm'),
    row('Space for the motor', mmText, 'j2_space_mm'),
    row('Wheel bore', mmText, 'wheel_bore_mm'),
    row('Hub adapter', yesNo, 'needs_hub_adapter'),
    row('Ground clearance', mmText, 'ground_clearance_mm'),
  ].filter((r) => r.before !== '–' || r.after !== '–')
}

const SCORE_LEVEL: Level[] = ['low', 'medium', 'high', 'high']
/** A 0-3 priority score as a risk level; unknown when the evidence is missing. */
export const scoreLevel = (s: Score): Level => (s.value === null ? 'unknown' : SCORE_LEVEL[s.value])

// ---------- action plan ----------

export const ACTION_LABEL: Record<Recommendation['action'], string> = {
  re_source: 'Re-source',
  dual_source: 'Dual-source',
  investigate: 'Investigate',
  keep: 'Keep',
}
export const ACTION_TONE: Record<Recommendation['action'], Accuracy> = {
  re_source: 'lo',
  dual_source: 'mid',
  investigate: 'none',
  keep: 'hi',
}
const ACTION_ORDER: Recommendation['action'][] = ['re_source', 'dual_source', 'investigate', 'keep']

export interface Action {
  recommendation: Recommendation
  row: RiskRow | null
  alternative: Alternative | null
}

/** Recommendations grouped by what to do, in the backend's rank within each group. */
export function actionPlan(job: JobState): { action: Recommendation['action']; items: Action[] }[] {
  const items = job.recommendations.map((r) => ({
    recommendation: r,
    row: job.riskLines.find((x) => x.line.id === r.line_id) ?? null,
    alternative: r.alternative_id ? (job.alternatives[r.line_id]?.find((a) => a.id === r.alternative_id) ?? null) : null,
  }))
  return ACTION_ORDER.map((action) => ({ action, items: items.filter((i) => i.recommendation.action === action) })).filter(
    (g) => g.items.length > 0,
  )
}

// ---------- supply map ----------

export const DOMAIN_LABEL: Record<Domain, string> = {
  actuation: 'Actuation',
  sensing: 'Sensing',
  compute: 'Compute',
  power: 'Power',
  structure: 'Structure',
  other: 'Other',
}
const DOMAIN_ORDER: Domain[] = ['actuation', 'power', 'compute', 'sensing', 'structure', 'other']
const LEVEL_ORDER: Record<Level, number> = { high: 0, medium: 1, unknown: 2, low: 3 }
const rowLevel = (r: RiskRow) => r.risk.priority?.level ?? r.risk.overall

/** BOM lines by domain, riskiest first within each domain, with a per-domain level count. */
export function supplyMap(job: JobState): { domain: Domain; rows: RiskRow[]; counts: Record<Level, number> }[] {
  return DOMAIN_ORDER.map((domain) => {
    const rows = job.riskLines
      .filter((r) => r.line.domain === domain)
      .sort((a, b) => LEVEL_ORDER[rowLevel(a)] - LEVEL_ORDER[rowLevel(b)])
    const counts = { high: 0, medium: 0, low: 0, unknown: 0 }
    for (const r of rows) counts[rowLevel(r)]++
    return { domain, rows, counts }
  }).filter((g) => g.rows.length > 0)
}

// ---------- evidence ----------

export interface SourceGroup {
  host: string
  verified: ClaimRow[]
  rejected: ClaimRow[]
}

/** Every reading the agents brought back, by the site it came from, most readings first. */
export function evidenceBySource(job: JobState): SourceGroup[] {
  const groups = new Map<string, SourceGroup>()
  for (const c of job.claims) {
    const h = host(c.claim.source.url)
    const g = groups.get(h) ?? { host: h, verified: [], rejected: [] }
    ;(c.verified ? g.verified : g.rejected).push(c)
    groups.set(h, g)
  }
  return [...groups.values()].sort((a, b) => b.verified.length + b.rejected.length - (a.verified.length + a.rejected.length))
}

// ---------- summary ----------

export interface Figure {
  label: string
  value: string
  detail?: string
  tone: Accuracy
}

const RUN_OK = new Set(['success'])

/** The report's opening: one paragraph on what to do, and the numbers behind it. */
export function reportSummary(job: JobState, deep: DeepLine | null): { verdict: string[]; figures: Figure[] } {
  const verdict: string[] = []
  const figures: Figure[] = []
  const plan = actionPlan(job)
  const count = (a: Recommendation['action']) => plan.find((g) => g.action === a)?.items.length ?? 0

  if (job.riskLines.length > 0) {
    const levels = job.riskLines.map(rowLevel)
    const high = levels.filter((l) => l === 'high').length
    const blocked = job.riskLines.filter((r) => r.risk.blocked).length
    figures.push({
      label: 'Parts mapped',
      value: String(job.riskLines.length),
      detail: `${high} high priority${blocked ? `, ${blocked} blocked` : ''}`,
      tone: high > 0 ? 'lo' : 'hi',
    })
    const act = count('re_source') + count('dual_source')
    figures.push({
      label: 'Parts to change',
      value: String(act),
      detail: `${count('re_source')} re-source, ${count('dual_source')} dual-source, ${count('investigate')} to investigate, ${count('keep')} keep`,
      tone: act + count('investigate') > 0 ? 'mid' : 'hi',
    })
    // job.recommendations is in the backend's rank: the first that is not "keep" leads.
    const top = job.recommendations.find((r) => r.action !== 'keep')
    if (top) {
      const part = shortPart(job.riskLines.find((x) => x.line.id === top.line_id)?.line.part ?? top.line_id)
      verdict.push(
        `First: ${ACTION_LABEL[top.action].toLowerCase()} the ${part}${top.blocked ? ', which cannot stay as it is' : ''}. ${firstClause(top.reason)}`,
      )
    }
    const unknown = levels.filter((l) => l === 'unknown').length
    if (unknown > 0) verdict.push(`${plural(unknown, 'part')} could not be scored: the evidence to rate ${unknown === 1 ? 'it' : 'them'} is missing.`)
  }

  if (deep) {
    verdict.push(deep.status)
    const usable = deep.options.filter((o) => o.verdict === 'pass').length
    figures.push({
      label: `Candidates for the ${deep.part}`,
      value: String(deep.options.length),
      detail: `${usable} pass, ${deep.options.filter((o) => o.verdict === 'review').length} open, ${deep.options.filter((o) => o.verdict === 'rejected').length} rejected`,
      tone: usable > 0 ? 'hi' : deep.options.some((o) => o.verdict === 'review') ? 'mid' : 'lo',
    })
  }

  const verified = job.claims.filter((c) => c.verified).length
  if (job.claims.length > 0) {
    figures.push({
      label: 'Readings verified',
      value: `${verified} / ${job.claims.length}`,
      detail: 'quote found on the page the agent read',
      tone: verified / job.claims.length >= 0.7 ? 'hi' : verified > 0 ? 'mid' : 'lo',
    })
  }

  const runs = job.runOrder.map((id) => job.runs[id]).filter((r): r is Run => r !== undefined)
  if (runs.length > 0) {
    const ok = runs.filter((r) => r.outcome && RUN_OK.has(r.outcome)).length
    const blocked = runs.filter((r) => r.outcome === 'blocked' || r.outcome === 'auth_required').length
    figures.push({
      label: 'Agent runs',
      value: `${ok} / ${runs.length}`,
      detail: `${new Set(runs.map((r) => r.site)).size} sites${blocked ? `, ${blocked} blocked` : ''}`,
      tone: ok === runs.length ? 'hi' : 'mid',
    })
  }

  if (job.criteria?.domestic_threshold != null && job.project) {
    const share = domesticShare(job.project.bom)
    const need = Math.round(job.criteria.domestic_threshold * 100)
    figures.push({
      label: 'Domestic content',
      value: share ? `${share.pct}%` : 'unknown',
      detail: `needs ${need}%${share?.unpriced ? `, ${share.unpriced} unpriced parts left out` : ''}`,
      tone: share ? (share.pct >= need ? 'hi' : 'lo') : 'none',
    })
  } else if (job.compliance) {
    figures.push({
      label: 'Domestic content',
      value: `${job.compliance.domestic_pct}%`,
      detail: `thresholds ${job.compliance.thresholds_pct.join(' / ')}%`,
      tone: job.compliance.domestic_pct >= Math.min(...job.compliance.thresholds_pct) ? 'hi' : 'lo',
    })
  }

  if (verdict.length === 0) verdict.push('The job finished without a risk map or candidates to report.')
  return { verdict, figures }
}
