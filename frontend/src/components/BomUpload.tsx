import { useState, type DragEvent } from 'react'
import { bomToCsv, parseBomCsv } from '../onboarding/bomCsv'
import type { BomRow } from '../types'

interface Props {
  rows: BomRow[]
  /** The demo robot's BOM: offered as a sample and used for the template download. */
  sample: BomRow[]
  onChange: (rows: BomRow[]) => void
}

function downloadTemplate(sample: BomRow[]) {
  const url = URL.createObjectURL(new Blob([bomToCsv(sample)], { type: 'text/csv' }))
  const a = document.createElement('a')
  a.href = url
  a.download = 'bom-template.csv'
  a.click()
  URL.revokeObjectURL(url)
}

/** Pick or drop a BOM CSV. A file with any error is not kept, so the form cannot continue on it. */
export function BomUpload({ rows, sample, onChange }: Props) {
  const [source, setSource] = useState<string | null>(null)
  const [errors, setErrors] = useState<string[]>([])
  const [over, setOver] = useState(false)

  const read = async (file: File | undefined) => {
    if (!file) return
    const parsed = parseBomCsv(await file.text())
    setSource(file.name)
    setErrors(parsed.errors)
    onChange(parsed.rows)
  }
  const drop = (e: DragEvent) => {
    e.preventDefault()
    setOver(false)
    void read(e.dataTransfer.files[0])
  }

  return (
    <div className="ob-bom">
      <label
        className={`ob-drop${over ? ' over' : ''}`}
        onDragOver={(e) => {
          e.preventDefault()
          setOver(true)
        }}
        onDragLeave={() => setOver(false)}
        onDrop={drop}
      >
        <input
          type="file"
          accept=".csv,text/csv"
          onChange={(e) => {
            void read(e.target.files?.[0])
            e.target.value = '' // let the same file be picked again after a fix
          }}
        />
        <strong>Choose a CSV file</strong>
        <span className="muted">or drop it here</span>
      </label>
      <div className="ob-bom-actions">
        <button
          type="button"
          className="secondary"
          onClick={() => {
            setSource('sample BOM')
            setErrors([])
            onChange(sample)
          }}
        >
          Use the sample BOM
        </button>
        <button type="button" className="ob-link" onClick={() => downloadTemplate(sample)}>
          Download a template
        </button>
      </div>

      {errors.length > 0 && (
        <div className="error" role="alert">
          <p>
            {source} was not loaded. Fix {errors.length === 1 ? 'this' : 'these'} and upload it again:
          </p>
          <ul>
            {errors.slice(0, 8).map((e) => (
              <li key={e}>{e}</li>
            ))}
            {errors.length > 8 && <li>and {errors.length - 8} more</li>}
          </ul>
        </div>
      )}

      {rows.length > 0 && (
        <div className="ob-bom-preview">
          <p className="muted">
            {rows.length} parts{source ? ` from ${source}` : ''}
          </p>
          <table>
            <thead>
              <tr>
                <th>Part</th>
                <th>Category</th>
                <th>Qty</th>
                <th>Unit cost</th>
                <th>Origin</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={`${i}:${r.part}`}>
                  <td>{r.part}</td>
                  <td>{r.category}</td>
                  <td>{r.qty}</td>
                  <td>${r.unit_cost_usd}</td>
                  <td>{r.origin}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
