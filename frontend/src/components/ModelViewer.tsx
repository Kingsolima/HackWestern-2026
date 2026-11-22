import '@google/model-viewer'

/** The robot before any job: the CAD worker builds these starter designs when it starts. */
export function ModelViewer({ src, title }: { src: string | null; title: string }) {
  return (
    <section className="panel">
      <h2>{title}</h2>
      {src ? (
        <model-viewer src={src} camera-controls auto-rotate style={{ width: '100%', height: 420 }} />
      ) : (
        <p className="muted">No model yet. Build one with the CAD worker.</p>
      )}
    </section>
  )
}
