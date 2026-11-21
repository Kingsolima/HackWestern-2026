import '@google/model-viewer'

// TODO(owner 1/4): before/after slider, highlight the changed bracket, STEP download.
export function ModelViewer({ src }: { src: string | null }) {
  return (
    <section className="panel">
      <h2>Robot</h2>
      {src ? (
        <model-viewer src={src} camera-controls auto-rotate style={{ width: '100%', height: 420 }} />
      ) : (
        <p className="muted">No model yet. Build one with the CAD worker.</p>
      )}
    </section>
  )
}
