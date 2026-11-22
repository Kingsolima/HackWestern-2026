import { describe, expect, it } from 'vitest'
import { agentGraph } from './agentGraph'
import { STAGE_ORDER, TERMINAL_STAGES, type JobEvent } from './events'
import ar4 from './fixtures/ar4-company.json'
import stretch from './fixtures/stretch.json'
import wheeled from './fixtures/wheeled-demo.json'
import { applyEvent, initialJobState } from './job'

const fold = (events: unknown, until?: (e: JobEvent) => boolean) => {
  const all = events as JobEvent[]
  const end = until ? all.findIndex(until) : all.length
  return all.slice(0, end < 0 ? all.length : end + 1).reduce(applyEvent, initialJobState)
}
const columns = (g: ReturnType<typeof agentGraph>) =>
  [0, 1, 2, 3, 4, 5].map((c) => g.nodes.filter((n) => n.column === c).length)

describe('stage contract', () => {
  it('knows every stage the backend sent in the recordings', () => {
    for (const events of [ar4, wheeled, stretch] as unknown as JobEvent[][]) {
      for (const e of events) {
        if (e.type !== 'stage') continue
        expect(STAGE_ORDER.includes(e.data.stage) || TERMINAL_STAGES.has(e.data.stage)).toBe(true)
      }
    }
  })
})

describe('agentGraph', () => {
  it('lays a finished AR4 job out as searches → page read → sites → parts → checks', () => {
    const g = agentGraph(fold(ar4))
    expect(columns(g)).toEqual([1, 3, 1, 7, 3, 1])
    expect(g.nodes.find((n) => n.kind === 'design')).toMatchObject({ status: 'lo', detail: '0 pass, 0 open, 3 ruled out' })
    expect(g.edges.filter((e) => e.state === 'flowing')).toEqual([])
  })

  it('links each part to the runs that read it: by run id for agents, by page for text reads', () => {
    const job = fold(ar4)
    const g = agentGraph(job)
    const into = (part: string) => g.edges.filter((e) => e.to === `part:${part}`).map((e) => job.runs[e.from].site)
    expect(into('CPM-SDSK-2331S-RLN')).toEqual(['teknic.com'])
    expect(into('V0300-211-B-000')).toEqual(['mclennan.co.uk'])
  })

  it('marks a blocked site run and the edge into it as failed', () => {
    const g = agentGraph(fold(ar4))
    const blocked = g.nodes.find((n) => n.kind === 'site' && n.status === 'lo')!
    expect(blocked.label).toBe('scribd.com')
    expect(blocked.detail).toMatch(/CAPTCHA/)
    expect(g.edges.filter((e) => e.to === blocked.id).every((e) => e.state === 'failed')).toBe(true)
  })

  it('shows a run in progress as running, with its edges flowing', () => {
    const job = fold(ar4, (e) => e.type === 'run_started' && e.data.product === 'agent')
    const g = agentGraph(job)
    const site = g.nodes.find((n) => n.kind === 'site')!
    expect(site).toMatchObject({ status: 'running', label: 'teknic.com' })
    expect(g.edges.filter((e) => e.to === site.id).map((e) => e.state)).toEqual(['flowing'])
    expect(g.nodes.some((n) => n.kind === 'finding' || n.kind === 'design')).toBe(false)
  })

  it('puts the run that read the company’s pages beside the answers (Stretch)', () => {
    const g = agentGraph(fold(stretch))
    const first = g.nodes.filter((n) => n.column === 0)
    expect(first.map((n) => [n.label, n.detail])).toEqual([
      ['Boston Dynamics', 'Stretch: 4 parts, 3 facts'],
      ['Read your pages', '4 of 4 pages read, 9 facts verified'],
    ])
    expect(g.edges).toContainEqual({ from: first[1].id, to: 'answers', state: 'done' })
  })

  it('is empty before a job starts', () => {
    expect(agentGraph(initialJobState)).toEqual({ nodes: [], edges: [] })
  })
})
