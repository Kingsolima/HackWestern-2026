import { useEffect, useState, type DragEvent, type ReactNode } from 'react'
import { bomCriteria, bomToCsv, costPerRobot, parseBomCsv, type BomParse, type CriterionId } from '../onboarding/bomCsv'
import type { CadMeasure } from '../onboarding/intake'
import { PROJECTS, type ProjectId } from '../projects'
import type { BomRow } from '../types'
import { CadUpload } from './CadUpload'

const CRITERIA_TEXT: Record<CriterionId, ReactNode> = {
  csv: 'A CSV file with a header row',
  columns: (
    <>
      Columns <code>part</code>, <code>category</code>, <code>qty</code>, <code>unit_cost_usd</code>,{' '}
      <code>origin</code> (<code>supply_risk</code> optional)
    </>
  ),
  lines: (
    <>
      One part per line, <code>qty</code> a whole number above 0
    </>
  ),
  cost: (
    <>
      <code>unit_cost_usd</code> a number in US dollars, or <code>unknown</code>
    </>
  ),
  origin: (
    <>
      <code>origin</code> a 2-letter country code, or <code>unknown</code>
    </>
  ),
  motor: (
    <>
      At least one motor, servo or stepper line, the part we redesign
    </>
  ),
}
const MARK = { pass: 'hi', fail: 'lo', pending: '' } as const

interface Props {
  /** The demo robot's BOM, offered as a sample; null while it loads. */
  sample: BomRow[] | null
  leaving: boolean
  onContinue: (bom: BomRow[], cad: CadMeasure | null) => void
  /** Open one of the prepared demo projects instead of onboarding. */
  onProject: (id: ProjectId) => void
}

function downloadTemplate(sample: BomRow[]) {
  const url = URL.createObjectURL(new Blob([bomToCsv(sample.slice(0, 2))], { type: 'text/csv' }))
  const a = document.createElement('a')
  a.href = url
  a.download = 'bom-template.csv'
  a.click()
  URL.revokeObjectURL(url)
}

/** First screen: the title fades in, then a BOM drop zone with a live checklist of what the file
 * needs. Nothing else is asked until the file passes. */
export function Welcome({ sample, leaving, onContinue, onProject }: Props) {
  const [file, setFile] = useState<{ name: string; parse: BomParse } | null>(null)
  const [cad, setCad] = useState<CadMeasure | null>(null)
  const [over, setOver] = useState(false)

  const status = bomCriteria(file?.name ?? null, file?.parse ?? null)
  const ok = file !== null && Object.values(status).every((s) => s === 'pass')

  const read = async (f: File | undefined) => {
    if (f) setFile({ name: f.name, parse: parseBomCsv(await f.text()) })
  }
  const drop = (e: DragEvent) => {
    e.preventDefault()
    setOver(false)
    void read(e.dataTransfer.files[0])
  }
  const go = () => {
    if (ok) onContinue(file.parse.rows, cad)
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement
      if (e.key !== 'Enter' || ['BUTTON', 'A', 'INPUT'].includes(el.tagName)) return
      e.preventDefault()
      go()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  return (
    <section className={`intro-screen${leaving ? ' out' : ''}`}>
      <div className="intro">
        <h1 aria-label="Welcome to BOMbot">
          <span>Welcome</span> <span style={{ animationDelay: '.25s' }}>to</span>{' '}
          <span style={{ animationDelay: '.5s' }}>
            <b>BOMbot</b>
          </span>
        </h1>
        <p className="lead later" style={{ animationDelay: '1.3s' }}>
          Start with your robot's bill of materials. We map where every part comes from, then send agents to find
          better sources for the part that matters most.
        </p>
        <div className="later intro-body" style={{ animationDelay: '1.9s' }}>
          <label
            className={`dropzone${over ? ' over' : ''}${file ? (ok ? ' ok' : ' bad') : ''}`}
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
              hidden
              onChange={(e) => {
                void read(e.target.files?.[0])
                e.target.value = ''
              }}
            />
            <div className="what">
              <div className="name">{file?.name ?? 'Drop your BOM here'}</div>
              <div className="meta">
                {!file
                  ? 'CSV, one part per line'
                  : ok
                    ? `${file.parse.rows.length} lines / ${costPerRobot(file.parse.rows)}`
                    : 'Fix the lines below and drop it again'}
              </div>
            </div>
            <span className="btn">Choose file</span>
          </label>
          <ul className="criteria">
            {Object.entries(CRITERIA_TEXT).map(([id, text]) => (
              <li key={id}>
                <span className={`dot ${MARK[status[id as CriterionId]]}`} />
                <span>{text}</span>
              </li>
            ))}
          </ul>
          {file && file.parse.errors.length > 0 && (
            <ul className="errors" role="alert">
              {file.parse.errors.slice(0, 6).map((e) => (
                <li key={e}>{e}</li>
              ))}
              {file.parse.errors.length > 6 && <li>and {file.parse.errors.length - 6} more</li>}
            </ul>
          )}
          <CadUpload cad={cad} onChange={setCad} />
          <div className="nav">
            <button type="button" className="btn go" disabled={!ok} onClick={go}>
              Continue
            </button>
            {sample && (
              <>
                <button
                  type="button"
                  className="link"
                  onClick={() => setFile({ name: 'sample_bom.csv', parse: parseBomCsv(bomToCsv(sample)) })}
                >
                  Use the sample BOM
                </button>
                <button type="button" className="link" onClick={() => downloadTemplate(sample)}>
                  Download template
                </button>
              </>
            )}
          </div>
          <p className="demo-projects label">
            Or open a demo project:{' '}
            {PROJECTS.map((p) => (
              <button key={p.id} type="button" className="linkbtn" onClick={() => onProject(p.id)}>
                {p.label}
              </button>
            ))}
          </p>
        </div>
      </div>
    </section>
  )
}
