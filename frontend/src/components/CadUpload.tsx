import { useState } from 'react'
import { ApiError, measureCad, type CadMeasure } from '../onboarding/intake'

interface Props {
  cad: CadMeasure | null
  onChange: (cad: CadMeasure | null) => void
}

/** Optional STEP file. The CAD worker measures it; the numbers it gives show up on the review
 * screen marked "from CAD". */
export function CadUpload({ cad, onChange }: Props) {
  const [name, setName] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const read = async (file: File | undefined) => {
    if (!file) return
    setName(file.name)
    setError(null)
    setBusy(true)
    try {
      onChange(await measureCad(file))
    } catch (e) {
      onChange(null)
      setError(e instanceof ApiError ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }
  const named = cad ? cad.parts.filter((p) => p.name).length : 0

  return (
    <div className="ob-cad">
      <label className="ob-drop ob-drop-small">
        <input
          type="file"
          accept=".step,.stp"
          onChange={(e) => {
            void read(e.target.files?.[0])
            e.target.value = ''
          }}
        />
        <strong>Add a CAD file (STEP), optional</strong>
        <span className="muted">We read wheel size, motor count and an estimated mass from it.</span>
      </label>
      {busy && <p className="muted">Measuring {name}…</p>}
      {error && (
        <p className="error" role="alert">
          {name} was not read: {error}
        </p>
      )}
      {cad && !busy && (
        <p className="muted">
          {name ?? 'CAD file'}: {cad.parts.length} parts{named === 0 ? ', none of them named' : ''}.{' '}
          <button type="button" className="ob-link" onClick={() => onChange(null)}>
            Remove
          </button>
        </p>
      )}
    </div>
  )
}
