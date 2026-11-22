import { useCallback, useLayoutEffect, useRef, useState } from 'react'
import { COLUMN_TITLES, agentGraph, type GraphNode } from '../agentGraph'
import type { JobState } from '../job'
import { Bay, BayZoom } from './AgentBays'

const STATUS_DOT: Record<GraphNode['status'], string> = {
  idle: '',
  running: 'acc blink',
  hi: 'hi',
  mid: 'mid',
  lo: 'lo',
}

const KIND_NOTE: Partial<Record<GraphNode['kind'], string>> = {
  query: 'search',
  triage: 'fetch',
}

/** A curve from the right edge of one node to the left edge of the next, or from the top of a
 * node to the bottom of the one above it when both sit in the same column. */
function curve(from: DOMRect, to: DOMRect, origin: DOMRect): string {
  const x = (v: number) => v - origin.left
  const y = (v: number) => v - origin.top
  if (Math.abs(from.left - to.left) < 4) {
    const cx = x(from.left + from.width / 2)
    const y1 = y(from.top)
    const y2 = y(to.bottom)
    return `M ${cx} ${y1} C ${cx} ${(y1 + y2) / 2}, ${cx} ${(y1 + y2) / 2}, ${cx} ${y2}`
  }
  const x1 = x(from.right)
  const y1 = y(from.top + from.height / 2)
  const x2 = x(to.left)
  const y2 = y(to.top + to.height / 2)
  const mid = (x1 + x2) / 2
  return `M ${x1} ${y1} C ${mid} ${y1}, ${mid} ${y2}, ${x2} ${y2}`
}

/** The Agents tab: the job as a pipeline, from the answers to the checks, with every agent's
 * browser in its own bay. Edges carry flow while the run they feed is working, then settle to
 * how it went. Click a run to see it large. */
export function AgentGraph({ job }: { job: JobState }) {
  const { nodes, edges } = agentGraph(job)
  const box = useRef<HTMLDivElement>(null)
  const els = useRef(new Map<string, HTMLElement>())
  const [paths, setPaths] = useState<Record<string, string>>({})
  const [size, setSize] = useState({ w: 0, h: 0 })
  const [hover, setHover] = useState<string | null>(null)
  const [zoom, setZoom] = useState<string | null>(null)
  const closeZoom = useCallback(() => setZoom(null), [])

  // Edge geometry depends on where the nodes landed: re-measure when the set of edges changes
  // (a node appearing moves its column) or the page resizes. A status change only recolours.
  const edgeKey = edges.map((e) => `${e.from}>${e.to}`).join('|')
  useLayoutEffect(() => {
    const el = box.current
    if (!el) return
    const measure = () => {
      const origin = el.getBoundingClientRect()
      const next: Record<string, string> = {}
      for (const key of edgeKey ? edgeKey.split('|') : []) {
        const [from, to] = key.split('>')
        const a = els.current.get(from)
        const b = els.current.get(to)
        if (a && b) next[key] = curve(a.getBoundingClientRect(), b.getBoundingClientRect(), origin)
      }
      setPaths(next)
      setSize({ w: el.scrollWidth, h: el.scrollHeight })
    }
    measure()
    const ro = new ResizeObserver(measure)
    ro.observe(el)
    return () => ro.disconnect()
  }, [edgeKey])

  const agents = nodes.filter((n) => n.runId && job.runs[n.runId]?.product === 'agent')
  const bayNumber = (runId: string) => agents.findIndex((n) => n.runId === runId) + 1
  const lit = (from: string, to: string) => hover !== null && (from === hover || to === hover)
  const zoomed = zoom ? job.runs[zoom] : undefined
  const ref = (id: string) => (el: HTMLElement | null) => {
    if (el) els.current.set(id, el)
    else els.current.delete(id)
  }

  const runs = job.runOrder.map((id) => job.runs[id])
  const working = runs.filter((r) => r && r.outcome === null).length

  return (
    <div className="graph-wrap">
      <div className="graph-legend">
        <span>
          {agents.length} browser agent{agents.length === 1 ? '' : 's'} · {runs.length} runs
          {working > 0 && ` · ${working} working`}
        </span>
        <span>
          <span className="dot acc" />
          working
        </span>
        <span>
          <span className="dot hi" />
          verified / passes
        </span>
        <span>
          <span className="dot mid" />
          partial / open
        </span>
        <span>
          <span className="dot lo" />
          blocked / ruled out
        </span>
      </div>
      <div className="graph" ref={box} onMouseLeave={() => setHover(null)}>
        <svg className="edges" width={size.w} height={size.h} aria-hidden="true">
          {edges.map((e) => {
            const d = paths[`${e.from}>${e.to}`]
            if (!d) return null
            const cls = `edge ${e.state}${lit(e.from, e.to) ? ' lit' : hover ? ' dim' : ''}`
            return <path key={`${e.from}>${e.to}`} d={d} className={cls} />
          })}
        </svg>
        {COLUMN_TITLES.map((title, col) => {
          const here = nodes.filter((n) => n.column === col)
          return (
            <div key={title} className={`graph-col col-${col}`}>
              <div className="col-title">{title}</div>
              <div className="col-body">
                {here.length === 0 && <div className="node ghost">waiting</div>}
                {here.map((n) => {
                  const run = n.runId ? job.runs[n.runId] : undefined
                  if (run?.product === 'agent') {
                    return (
                      <div key={n.id} ref={ref(n.id)} className="node-bay" onMouseEnter={() => setHover(n.id)}>
                        <Bay n={bayNumber(run.runId)} run={run} onZoom={() => setZoom(run.runId)} />
                      </div>
                    )
                  }
                  const body = (
                    <>
                      <span className="node-head">
                        <span className={`dot ${STATUS_DOT[n.status]}`} />
                        <span className="node-label">{n.label}</span>
                        {(KIND_NOTE[n.kind] ?? (run?.product === 'gemini' ? 'text read' : null)) && (
                          <span className="node-kind">{KIND_NOTE[n.kind] ?? 'text read'}</span>
                        )}
                      </span>
                      <span className="node-detail" title={n.detail}>
                        {n.detail}
                      </span>
                    </>
                  )
                  return run ? (
                    <button
                      key={n.id}
                      type="button"
                      ref={ref(n.id)}
                      className={`node ${n.kind} ${n.status}`}
                      onMouseEnter={() => setHover(n.id)}
                      onClick={() => setZoom(run.runId)}
                    >
                      {body}
                    </button>
                  ) : (
                    <div key={n.id} ref={ref(n.id)} className={`node ${n.kind} ${n.status}`} onMouseEnter={() => setHover(n.id)}>
                      {body}
                    </div>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>
      {zoomed && <BayZoom n={bayNumber(zoomed.runId) || 0} run={zoomed} onClose={closeZoom} />}
    </div>
  )
}
