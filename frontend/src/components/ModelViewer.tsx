import '@google/model-viewer'

/** The robot before any job: the CAD worker builds this NEMA 17 baseline when it starts. */
export function ModelViewer({ src }: { src: string | null }) {
  return (
    <section className="panel">
      <h2>Robot: NEMA 17 stepper baseline</h2>
      {src ? (
        <model-viewer src={src} camera-controls auto-rotate style={{ width: '100%', height: 420 }} />
      ) : (
        <p className="muted">No model yet. Build one with the CAD worker.</p>
      )}
    </section>
  )
}
