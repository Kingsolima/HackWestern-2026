import { useEffect, useRef, useState } from 'react'
import { outcomeAccuracy } from '../accuracy'
import type { Outcome } from '../events'
import type { Run } from '../job'

const BASE = import.meta.env.VITE_API_URL ?? ''
const OUTCOME: Record<Outcome, string> = {
  success: 'Verified',
  incomplete: 'Partial',
  blocked: 'Blocked',
  auth_required: 'Needs login',
  not_found: 'Not found',
  error: 'Error',
}
const MIN_BAYS = 4
/** The desktop viewport a captured page is laid out in before it is scaled into a bay. */
const PAGE_W = 1280
const pad2 = (n: number) => String(n).padStart(2, '0')

// One request per run: the page the agent's browser showed (backend/app/api/runs.py), as a blob
// URL, or null when nothing was recorded for the run.
const pages = new Map<string, Promise<string | null>>()
function pageFor(runId: string): Promise<string | null> {
  let page = pages.get(runId)
  if (!page) {
    page = fetch(`${BASE}/api/runs/${encodeURIComponent(runId)}/view`)
      .then(async (r) => (r.ok ? URL.createObjectURL(await r.blob()) : null))
      .catch(() => null)
    pages.set(runId, page)
  }
  return page
}

function useRecordedPage(runId: string | undefined): string | null {
  const [url, setUrl] = useState<string | null>(null)
  useEffect(() => {
    if (!runId) return
    let on = true
    pageFor(runId).then((u) => on && setUrl(u))
    return () => {
      on = false
    }
  }, [runId])
  return url
}

/** A captured page laid out at desktop width and scaled to the bay, like a browser thumbnail.
 * Sandboxed with no permissions: the page's scripts never run. */
function PageView({ src, title }: { src: string; title: string }) {
  const host = useRef<HTMLDivElement>(null)
  const [scale, setScale] = useState(0.3)
  useEffect(() => {
    const el = host.current
    if (!el) return
    const ro = new ResizeObserver(() => setScale(el.clientWidth / PAGE_W))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  return (
    <div className="bay-page" ref={host}>
      <iframe
        src={src}
        title={title}
        sandbox=""
        referrerPolicy="no-referrer"
        tabIndex={-1}
        style={{ width: PAGE_W, height: `${100 / scale}%`, transform: `scale(${scale})` }}
      />
    </div>
  )
}

function Bay({ n, run, zoomed, onZoom }: { n: number; run: Run | undefined; zoomed?: boolean; onZoom?: () => void }) {
  const page = useRecordedPage(run?.runId)
  if (!run) {
    return (
      <article className="bay frame">
        <div className="bay-head">
          <span className="dot" />
          Bay {pad2(n)}
        </div>
        <div className="bay-url">about:blank</div>
        <div className="bay-body" />
        <div className="bay-foot">Standby</div>
      </article>
    )
  }
  const acc = outcomeAccuracy(run.outcome)
  const end = acc === 'none' ? '' : acc
  // A replayed run's streaming URL points at a browser that no longer exists, so only a running
  // live run gets the stream; otherwise the page the agent's browser captured, if recorded.
  const stream = run.live && run.streamingUrl && run.outcome === null ? run.streamingUrl : null
  const steps = run.steps.slice(-6)
  const current = run.steps[run.steps.length - 1]
  const view = stream ? 'Live view' : page ? 'Recorded page' : null

  return (
    <article className={`bay frame ${end}${zoomed ? ' zoomed' : ''}`}>
      <button type="button" className="bay-head" onClick={onZoom} title={zoomed ? 'Close' : 'Expand'}>
        <span className={`dot ${end || 'acc blink'}`} />
        Bay {pad2(n)} <span className="site">{run.site}</span>
        <span className="mode">
          {view ?? (run.live ? 'Live' : 'Replay')} / {run.worker}
        </span>
      </button>
      <div className="bay-url">
        {run.url ? (
          <a href={run.url} target="_blank" rel="noreferrer">
            {run.url}
          </a>
        ) : (
          run.site
        )}
      </div>
      {stream ? (
        <iframe className="bay-stream" src={stream} title={`Live browser for ${run.site}`} referrerPolicy="no-referrer" />
      ) : page ? (
        <div className="bay-view">
          <PageView src={page} title={`Page the agent saw on ${run.site}`} />
          {current && <div className={`bay-ticker st${end ? '' : ' cur'}`}>{current}</div>}
        </div>
      ) : (
        <div className="bay-body">
          {steps.map((s, i) => (
            <div key={run.steps.length - steps.length + i} className={`st${!end && i === steps.length - 1 ? ' cur' : ''}`}>
              {s}
            </div>
          ))}
        </div>
      )}
      <div className={`bay-foot ${end}`} title={run.reason ?? undefined}>
        {run.outcome ? `${OUTCOME[run.outcome]}${run.reason ? ` / ${run.reason}` : ''}` : `Step ${run.steps.length} / running`}
      </div>
    </article>
  )
}

/** The TinyFish agents, one bay each. Empty bays stand by until the job sends agents out; click
 * a bay to see its browser large. */
export function AgentBays({ runs }: { runs: Run[] }) {
  const [zoom, setZoom] = useState<string | null>(null)
  const count = Math.max(MIN_BAYS, runs.length)
  const zoomed = runs.findIndex((r) => r.runId === zoom)

  useEffect(() => {
    if (zoom === null) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setZoom(null)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [zoom])

  return (
    <>
      <section className="bays" aria-label="Agent bays">
        {Array.from({ length: count }, (_, i) => (
          <Bay
            key={runs[i]?.runId ?? `standby-${i}`}
            n={i + 1}
            run={runs[i]}
            onZoom={runs[i] ? () => setZoom(runs[i].runId) : undefined}
          />
        ))}
      </section>
      {zoomed >= 0 && (
        <div className="bay-zoom" onClick={(e) => e.target === e.currentTarget && setZoom(null)}>
          <Bay n={zoomed + 1} run={runs[zoomed]} zoomed onZoom={() => setZoom(null)} />
        </div>
      )}
    </>
  )
}
