// The Agents tab as a pipeline: what the job asked, the searches it ran, the pages it read,
// the sites its agents worked, the parts they found and the checks those parts went through.
// Fixed columns, not a physics layout, so nodes never move under the user's cursor and the
// agents' embedded pages stay put.

import { STAGE_ORDER } from './events'
import { isTerminal, type JobState, type Run } from './job'

export type NodeKind = 'answers' | 'query' | 'triage' | 'site' | 'finding' | 'design'
export type NodeStatus = 'idle' | 'running' | 'hi' | 'mid' | 'lo'

export interface GraphNode {
  id: string
  /** 0 answers, 1 searches, 2 page reads, 3 site runs, 4 parts found, 5 checks and CAD. */
  column: 0 | 1 | 2 | 3 | 4 | 5
  kind: NodeKind
  label: string
  /** One line under the label: an outcome, a count, a verdict. */
  detail: string
  runId?: string
  status: NodeStatus
}

export interface GraphEdge {
  from: string
  to: string
  state: 'flowing' | 'done' | 'failed'
}

export const COLUMN_TITLES = ['Your answers', 'Searches', 'Pages read', 'Sites', 'Parts found', 'Checks and CAD'] as const

const RUN_STATUS: Record<NonNullable<Run['outcome']>, NodeStatus> = {
  success: 'hi',
  incomplete: 'mid',
  blocked: 'lo',
  auth_required: 'lo',
  not_found: 'lo',
  error: 'lo',
}
const runStatus = (r: Run): NodeStatus => (r.outcome === null ? 'running' : RUN_STATUS[r.outcome])
const runDetail = (r: Run) =>
  r.outcome === null
    ? (r.steps[r.steps.length - 1] ?? 'starting')
    : r.reason || r.outcome.replace('_', ' ')

const host = (url: string | null) => {
  if (!url) return ''
  try {
    return new URL(url.includes('://') ? url : `https://${url}`).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}

const VERDICT_STATUS = { pass: 'hi', review: 'mid', rejected: 'lo' } as const

/** A part's standing: the CAD worker's verdict when there is one, else the worst check so far. */
function findingStatus(job: JobState, id: string): NodeStatus {
  const design = job.candidates.find((d) => (d.candidate_id ?? d.design_id) === id)
  if (design?.verdict) return VERDICT_STATUS[design.verdict]
  const checks = job.checks[id] ?? []
  if (checks.length === 0) return 'idle'
  if (checks.some((c) => c.verdict === 'fail')) return 'lo'
  return checks.some((c) => c.verdict === 'review') ? 'mid' : 'hi'
}

function edgeState(target: GraphNode): GraphEdge['state'] {
  return target.status === 'running' ? 'flowing' : target.status === 'lo' ? 'failed' : 'done'
}

export function agentGraph(job: JobState): { nodes: GraphNode[]; edges: GraphEdge[] } {
  const nodes: GraphNode[] = []
  const edges: [string, string][] = []
  if (!job.stage && job.runOrder.length === 0) return { nodes, edges: [] }
  const runs = job.runOrder.map((id) => job.runs[id]).filter((r): r is Run => r !== undefined)
  const stage = job.stage ? STAGE_ORDER.indexOf(job.stage) : -1
  const done = isTerminal(job)

  // 0: what the job starts from, plus any run that read the company's own pages.
  nodes.push({
    id: 'answers',
    column: 0,
    kind: 'answers',
    label: job.project?.name ?? 'Your answers',
    detail: job.project
      ? `${job.project.robot}: ${job.project.bom.length} parts, ${job.project.fact_basis.length} facts`
      : 'parts list and answers',
    status: stage > STAGE_ORDER.indexOf('INTAKE') || done ? 'hi' : 'running',
  })
  const intake = runs.filter((r) => r.worker === 'intake')
  for (const r of intake) {
    nodes.push({ id: r.runId, column: 0, kind: 'answers', label: 'Read your pages', detail: runDetail(r), runId: r.runId, status: runStatus(r) })
    edges.push([r.runId, 'answers'])
  }

  // 1: searches, fed by the answers.
  const searches = runs.filter((r) => r.product === 'search')
  for (const r of searches) {
    nodes.push({ id: r.runId, column: 1, kind: 'query', label: r.goal ?? 'search', detail: runDetail(r), runId: r.runId, status: runStatus(r) })
    edges.push(['answers', r.runId])
  }

  // 2: page reads triaging the search results.
  const triage = runs.filter((r) => r.product === 'fetch' && r.worker !== 'intake')
  for (const r of triage) {
    nodes.push({ id: r.runId, column: 2, kind: 'triage', label: 'Read the results', detail: runDetail(r), runId: r.runId, status: runStatus(r) })
    for (const s of searches.length ? searches : [{ runId: 'answers' }]) edges.push([s.runId, r.runId])
  }

  // 3: sites, worked by a browser agent or read from the fetched text.
  const sites = runs.filter((r) => r.product === 'agent' || r.product === 'gemini')
  const feeders = triage.length ? triage : searches.length ? searches : [{ runId: 'answers' }]
  for (const r of sites) {
    nodes.push({ id: r.runId, column: 3, kind: 'site', label: host(r.site), detail: runDetail(r), runId: r.runId, status: runStatus(r) })
    for (const f of feeders) edges.push([f.runId, r.runId])
  }

  // 4: parts found. A reading names its run when an agent made it; a text read names only its
  // page, so it is matched to the run that read that page, or that site.
  const findings = new Map<string, Set<string>>()
  for (const { claim } of job.claims) {
    if (!claim.candidate_id) continue
    const from = findings.get(claim.candidate_id) ?? new Set<string>()
    const byRun = claim.source.run_id && job.runs[claim.source.run_id] ? [claim.source.run_id] : []
    const byUrl = sites.filter((s) => s.url === claim.source.url).map((s) => s.runId)
    const byHost = sites.filter((s) => host(s.site) === host(claim.source.url)).map((s) => s.runId)
    for (const id of byRun.length ? byRun : byUrl.length ? byUrl : byHost) from.add(id)
    findings.set(claim.candidate_id, from)
  }
  for (const d of job.candidates) {
    const id = d.candidate_id ?? d.design_id
    if (!findings.has(id)) findings.set(id, new Set())
  }
  for (const [id, from] of findings) {
    const design = job.candidates.find((d) => (d.candidate_id ?? d.design_id) === id)
    const claims = job.claims.filter((c) => c.claim.candidate_id === id)
    const status = findingStatus(job, id)
    nodes.push({
      id: `part:${id}`,
      column: 4,
      kind: 'finding',
      label: [design?.manufacturer, design?.part_number ?? id].filter((x) => x && x !== 'unknown').join(' '),
      detail:
        status === 'idle'
          ? `${claims.filter((c) => c.verified).length} of ${claims.length} readings verified`
          : { hi: 'passes the checks', mid: 'checks still open', lo: 'ruled out', running: '', idle: '' }[status],
      status,
    })
    for (const r of from) edges.push([r, `part:${id}`])
  }

  // 5: the engineering checks and the CAD build, once the job gets there.
  if (stage >= STAGE_ORDER.indexOf('CHECK') || (done && findings.size > 0)) {
    const parts = nodes.filter((n) => n.kind === 'finding')
    const building = !done && stage <= STAGE_ORDER.indexOf('BUILD')
    const best = parts.some((p) => p.status === 'hi') ? 'hi' : parts.some((p) => p.status === 'mid') ? 'mid' : 'lo'
    nodes.push({
      id: 'design',
      column: 5,
      kind: 'design',
      label: 'Checks and CAD',
      detail: building
        ? 'checking specs, building the model'
        : `${parts.filter((p) => p.status === 'hi').length} pass, ${parts.filter((p) => p.status === 'mid').length} open, ${parts.filter((p) => p.status === 'lo').length} ruled out`,
      status: building ? 'running' : parts.length ? best : 'lo',
    })
    for (const p of parts) edges.push([p.id, 'design'])
  }

  const byId = new Map(nodes.map((n) => [n.id, n]))
  const seen = new Set<string>()
  const out: GraphEdge[] = []
  for (const [from, to] of edges) {
    const target = byId.get(to)
    if (!target || !byId.has(from) || seen.has(`${from}>${to}`)) continue
    seen.add(`${from}>${to}`)
    out.push({ from, to, state: edgeState(target) })
  }
  return { nodes, edges: out }
}
