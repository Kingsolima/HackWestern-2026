import '@google/model-viewer'
import type { ModelViewerElement } from '@google/model-viewer'
import { useEffect, useState } from 'react'
import type { Design } from '../events'

/** CAD-worker paths (/designs/{id}/glb) are served to the browser through the /cad proxy. */
const cadUrl = (path: string) => `/cad${path}`

const START_ORBIT = '-35deg 65deg auto'

/** Keep the two viewers looking from the same place: copy the moved camera to the other one. */
function useSyncedCameras(a: ModelViewerElement | null, b: ModelViewerElement | null) {
  useEffect(() => {
    if (!a || !b) return
    const link = (from: ModelViewerElement, to: ModelViewerElement) => (e: Event) => {
      const source = (e as CustomEvent<{ source: string }>).detail?.source
      if (source !== 'user-interaction') return // ignore changes we caused ourselves
      to.cameraOrbit = from.getCameraOrbit().toString()
      to.cameraTarget = from.getCameraTarget().toString()
      to.fieldOfView = `${from.getFieldOfView()}deg`
      to.jumpCameraToGoal()
    }
    const ab = link(a, b)
    const ba = link(b, a)
    a.addEventListener('camera-change', ab)
    b.addEventListener('camera-change', ba)
    return () => {
      a.removeEventListener('camera-change', ab)
      b.removeEventListener('camera-change', ba)
    }
  }, [a, b])
}

type Row = { label: string; before: string; after: string }

const mm = (v: number | undefined) => (v === undefined ? '–' : `${Number(v.toFixed(2))} mm`)
const yesNo = (v: boolean | undefined) => (v === undefined ? '–' : v ? 'yes' : 'no')

function changes(before: Design, after: Design): Row[] {
  const b = before.fit
  const a = after.fit
  const size = (d: Design) =>
    d.fit.bracket?.width_mm === undefined
      ? '–'
      : `${mm(d.fit.bracket.width_mm)} × ${mm(d.fit.bracket.height_mm)}`
  return [
    { label: 'Motor', before: before.motor, after: after.motor },
    { label: 'NEMA frame', before: before.frame, after: after.frame },
    { label: 'Bolt square', before: mm(b.bracket?.bolt_spacing_mm), after: mm(a.bracket?.bolt_spacing_mm) },
    { label: 'Pilot hole', before: mm(b.bracket?.pilot_hole_mm), after: mm(a.bracket?.pilot_hole_mm) },
    { label: 'Bracket (w × h)', before: size(before), after: size(after) },
    { label: 'Bracket foot', before: mm(b.bracket?.foot_len_mm), after: mm(a.bracket?.foot_len_mm) },
    { label: 'Shaft / wheel bore', before: `${mm(b.shaft_diameter_mm)} / ${mm(b.wheel_bore_mm)}`, after: `${mm(a.shaft_diameter_mm)} / ${mm(a.wheel_bore_mm)}` },
    { label: 'Hub adapter', before: yesNo(b.needs_hub_adapter), after: yesNo(a.needs_hub_adapter) },
    { label: 'Ground clearance', before: mm(b.ground_clearance_mm), after: mm(a.ground_clearance_mm) },
  ]
}

export function BeforeAfterViewer({
  before,
  after,
  title = 'Redesign',
  notes = [],
}: {
  before: Design
  after: Design
  title?: string
  /** Shown under the title: what the model is and is not built from. */
  notes?: string[]
}) {
  const [split, setSplit] = useState(50)
  const [beforeEl, setBeforeEl] = useState<ModelViewerElement | null>(null)
  const [afterEl, setAfterEl] = useState<ModelViewerElement | null>(null)
  useSyncedCameras(beforeEl, afterEl)

  return (
    <section className="panel">
      <h2>{title}</h2>
      {notes.map((note) => (
        <p key={note} className="muted">
          {note}
        </p>
      ))}
      <div className="compare">
        <model-viewer
          ref={setBeforeEl}
          className="compare-layer"
          src={cadUrl(before.glb_url)}
          camera-controls
          camera-orbit={START_ORBIT}
          interaction-prompt="none"
          // Both layers are transparent: clip each to its own side so neither robot shows
          // through the other (and each side only takes its own pointer input).
          style={{ clipPath: `inset(0 ${100 - split}% 0 0)` }}
        />
        <model-viewer
          ref={setAfterEl}
          className="compare-layer"
          src={cadUrl(after.glb_url)}
          camera-controls
          camera-orbit={START_ORBIT}
          interaction-prompt="none"
          style={{ clipPath: `inset(0 0 0 ${split}%)` }}
        />
        <div className="compare-line" style={{ left: `${split}%` }} />
        <span className="compare-tag compare-tag-left">{before.label}</span>
        <span className="compare-tag compare-tag-right">{after.label}</span>
      </div>
      <input
        className="compare-slider"
        type="range"
        min={0}
        max={100}
        value={split}
        onChange={(e) => setSplit(Number(e.target.value))}
        aria-label="Before / after split"
      />
      <p className="legend">
        <span className="swatch swatch-highlight" /> regenerated bracket
        <span className="swatch swatch-adapter" /> hub adapter
        <span className="muted"> · drag the slider, rotate either side</span>
      </p>
      <table>
        <thead>
          <tr>
            <th>What changed</th>
            <th>Before</th>
            <th>After</th>
          </tr>
        </thead>
        <tbody>
          {changes(before, after).map((r) => (
            <tr key={r.label} className={r.before !== r.after ? 'changed' : ''}>
              <td>{r.label}</td>
              <td>{r.before}</td>
              <td>{r.after}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p>
        STEP:{' '}
        <a href={cadUrl(before.step_url)} download>
          before
        </a>{' '}
        ·{' '}
        <a href={cadUrl(after.step_url)} download>
          after
        </a>
      </p>
    </section>
  )
}
