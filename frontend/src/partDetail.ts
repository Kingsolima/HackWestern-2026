// What the 3D view says about one part: the hover card and the pinned card. A node is matched
// to its BOM line (modelParts.matchLines), then to what the job learned about that line: its
// supply risk, the recommended action and the alternatives the agents found.

import type { Alternative, BomLine, Level, LineRisk, Recommendation, RiskFactor } from './events'
import type { JobState } from './job'
import { matchLines, partInfo, type PartLine, type PartRole } from './modelParts'
import { ACTION_LABEL, availabilityText, money, shortPart } from './report'

export interface PartDetail {
  node: string
  title: string
  /** Short facts for the hover card: qty, price, origin, supplier, availability. */
  facts: string[]
  /** What the job is doing to the part (deep line, regenerated mount), if anything. */
  role: string | null
  /** The project's BOM line, once a job has one; null for an uploaded BOM before a job. */
  line: BomLine | null
  risk: LineRisk | null
  /** The level the report shows for the part: its 0-9 priority level, else the worst factor's. */
  level: Level | null
  /** The factor that drives the risk: the highest high or medium one. */
  worst: RiskFactor | null
  recommendation: Recommendation | null
  /** "Re-source → Teknic CPM-SDSK-2331S-RLN" and the like, for the hover card. */
  action: string | null
  alternatives: Alternative[]
  /** The BOM lines a node could be when it matches several. */
  candidates: string[]
}

const WORST_ORDER: Record<Level, number> = { high: 0, medium: 1, unknown: 2, low: 3 }

export function worstFactor(risk: LineRisk | null): RiskFactor | null {
  if (!risk) return null
  const sorted = [...risk.factors].sort((a, b) => WORST_ORDER[a.level] - WORST_ORDER[b.level])
  const top = sorted[0]
  return top && (top.level === 'high' || top.level === 'medium') ? top : null
}

const ROLE_TEXT: Record<PartRole, string> = {
  deep: 'Deep line: agents are finding replacements',
  build: 'Regenerated to fit the new motor',
}

function lineFacts(l: BomLine): string[] {
  const origin = l.origin_country && l.origin_country !== 'unknown' ? l.origin_country : 'origin unknown'
  return [
    `x${l.qty}`,
    l.unit_price_usd === null ? 'price unknown' : money(l.unit_price_usd),
    l.origin_tier && l.origin_tier !== 'none' ? `${origin} ${l.origin_tier}` : origin,
    ...(l.manufacturer ? [l.manufacturer] : []),
    availabilityText(l),
  ]
}

/** The parts of the job state a part's detail reads. */
export type PartJob = Pick<JobState, 'project' | 'riskLines' | 'recommendations' | 'alternatives'>

/** Everything the 3D view can say about `node`, given the BOM it shows and the job so far. */
export function partDetail(node: string, lines: PartLine[], job: PartJob, role: PartRole | null): PartDetail {
  const hits = matchLines(node, lines)
  const hit = hits.length === 1 ? hits[0] : null
  const line = hit?.id ? (job.project?.bom.find((l) => l.id === hit.id) ?? null) : null
  const risk = line ? (job.riskLines.find((r) => r.line.id === line.id)?.risk ?? null) : null
  const recommendation = line ? (job.recommendations.find((r) => r.line_id === line.id) ?? null) : null
  const alternatives = line ? (job.alternatives[line.id] ?? []) : []
  const alt = recommendation?.alternative_id ? alternatives.find((a) => a.id === recommendation.alternative_id) : undefined
  const info = partInfo(node, lines, null)
  return {
    node,
    title: line ? shortPart(line.part) : info.title,
    facts: line ? lineFacts(line) : [info.detail],
    role: role ? ROLE_TEXT[role] : null,
    line,
    risk,
    level: risk ? (risk.priority?.level ?? risk.overall) : null,
    worst: worstFactor(risk),
    recommendation,
    action: recommendation
      ? `${ACTION_LABEL[recommendation.action]}${alt ? ` → ${alt.manufacturer} ${alt.part_number}` : ''}`
      : null,
    alternatives,
    candidates: hits.length > 1 ? hits.map((l) => shortPart(l.part)) : [],
  }
}
