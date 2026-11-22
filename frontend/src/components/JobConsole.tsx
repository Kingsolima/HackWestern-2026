import { useState, type ReactNode } from 'react'
import { STAGE_ORDER, stageLabel, type Design, type Stage } from '../events'
import { isTerminal, type JobState } from '../job'
import type { Onboarded } from '../onboarding/answers'
import { cadUrl } from '../projects'
import type { ComplianceCard as Card } from '../types'
import { ChecksTable } from './ChecksTable'
import { ClaimsList } from './ClaimsList'
import { CompanyCard } from './CompanyCard'
import { ComplianceCard } from './ComplianceCard'
import { ProjectCard } from './ProjectCard'
import { Recommendations } from './Recommendations'
import { RiskTable } from './RiskTable'

const pad2 = (n: number) => String(n).padStart(2, '0')

const mm = (v: number | undefined) => (v === undefined ? '–' : `${Number(v.toFixed(2))} mm`)
const yesNo = (v: boolean | undefined) => (v === undefined ? '–' : v ? 'yes' : 'no')

function changes(before: Design, after: Design) {
  const b = before.fit
  const a = after.fit
  const size = (d: Design) =>
    d.fit.bracket?.width_mm === undefined ? '–' : `${mm(d.fit.bracket.width_mm)} × ${mm(d.fit.bracket.height_mm)}`
  return [
    { label: 'Motor', before: before.motor, after: after.motor },
    { label: 'NEMA frame', before: before.frame, after: after.frame },
    { label: 'Bolt square', before: mm(b.bracket?.bolt_spacing_mm), after: mm(a.bracket?.bolt_spacing_mm) },
    { label: 'Pilot hole', before: mm(b.bracket?.pilot_hole_mm), after: mm(a.bracket?.pilot_hole_mm) },
    { label: 'Bracket (w × h)', before: size(before), after: size(after) },
    { label: 'Bracket foot', before: mm(b.bracket?.foot_len_mm), after: mm(a.bracket?.foot_len_mm) },
    { label: 'Motor shaft', before: mm(b.shaft_diameter_mm), after: mm(a.shaft_diameter_mm) },
    { label: 'Wheel bore', before: mm(b.wheel_bore_mm), after: mm(a.wheel_bore_mm) },
    { label: 'Hub adapter', before: yesNo(b.needs_hub_adapter), after: yesNo(a.needs_hub_adapter) },
    { label: 'Ground clearance', before: mm(b.ground_clearance_mm), after: mm(a.ground_clearance_mm) },
  ].filter((r) => r.before !== '–' || r.after !== '–') // an arm's design has no wheel or bracket numbers
}

function DesignChanges({ before, after, notes }: { before: Design; after: Design; notes: string[] }) {
  return (
    <>
      {notes.map((n) => (
        <p key={n} className="help">
          {n}
        </p>
      ))}
      <table>
        <thead>
          <tr>
            <th>What changed</th>
            <th>{before.label}</th>
            <th>{after.label}</th>
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
      <p className="label">
        STEP files:{' '}
        <a href={cadUrl(before.step_url)} download>
          before
        </a>{' '}
        /{' '}
        <a href={cadUrl(after.step_url)} download>
          after
        </a>
      </p>
    </>
  )
}

interface Props {
  job: JobState
  onboarded: Onboarded | null
  /** The baseline compliance card, when it is right for this robot. */
  card: Card | null
  /** What the 3D model is and is not built from, for the Changes tab. */
  modelNotes: string[]
  onRunAgain: () => void
  onRunLive?: () => void
}

const END: Partial<Record<Stage, [string, string]>> = {
  DONE: ['hi', 'Done'],
  DEGRADED: ['mid', 'Degraded: some agents came back empty'],
  FAILED: ['lo', 'Failed'],
}

/** The bottom-left console after launch: the job's stages while it runs, then the report. */
export function JobConsole({ job, onboarded, card, modelNotes, onRunAgain, onRunLive }: Props) {
  const [tab, setTab] = useState('project')
  const done = isTerminal(job)
  const current = job.stage ? STAGE_ORDER.indexOf(job.stage) : -1
  const running = job.connection === 'starting' || job.connection === 'streaming'

  const tabs: { id: string; label: string; body: () => ReactNode }[] = [
    {
      id: 'project',
      label: 'Project',
      body: () => (
        <>
          {job.project ? (
            <ProjectCard project={job.project} criteria={job.criteria} claims={job.claims} />
          ) : (
            onboarded && <CompanyCard company={onboarded.company} />
          )}
          {card && <ComplianceCard card={card} />}
        </>
      ),
    },
  ]
  if (job.riskLines.length > 0)
    tabs.push({ id: 'risk', label: 'Risk', body: () => <RiskTable rows={job.riskLines} alternatives={job.alternatives} /> })
  if (job.recommendations.length > 0)
    tabs.push({
      id: 'actions',
      label: 'Actions',
      body: () => (
        <Recommendations recommendations={job.recommendations} rows={job.riskLines} alternatives={job.alternatives} />
      ),
    })
  tabs.push({ id: 'checks', label: 'Checks', body: () => <ChecksTable checks={job.checks} candidates={job.candidates} /> })
  tabs.push({ id: 'claims', label: 'Claims', body: () => <ClaimsList claims={job.claims} /> })
  const [before, after] = [job.baseline, job.candidates[0]]
  if (before && after)
    tabs.push({
      id: 'changes',
      label: 'Changes',
      body: () => <DesignChanges before={before} after={after} notes={modelNotes} />,
    })
  const shown = tabs.find((t) => t.id === tab) ?? tabs[0]
  const end = job.stage ? END[job.stage] : undefined

  return (
    <div className="job">
      <div className="job-head">
        <span className="label">
          Job / {job.mode ?? 'starting'}
          {job.jobId && <span className="jid"> {job.jobId.slice(0, 8)}</span>}
        </span>
        {end && (
          <span className="label">
            <span className={`dot ${end[0]}`} />
            {end[1]}
          </span>
        )}
      </div>

      {!done ? (
        <ul className="stages">
          {STAGE_ORDER.map((s, i) => {
            const state = i < current ? 'done' : i === current ? 'now' : ''
            return (
              <li key={s} className={state}>
                <span>{pad2(i + 1)}</span>
                <span>{stageLabel(s)}</span>
                <span className="r">{state === 'done' ? 'OK' : state === 'now' ? '…' : ''}</span>
              </li>
            )
          })}
        </ul>
      ) : (
        <div className="report">
          <div className="tabs" role="tablist">
            {tabs.map((t) => (
              <button
                key={t.id}
                type="button"
                role="tab"
                aria-selected={shown.id === t.id}
                className={shown.id === t.id ? 'on' : ''}
                onClick={() => setTab(t.id)}
              >
                {t.label}
              </button>
            ))}
          </div>
          <div className="tab-body" role="tabpanel">
            {shown.body()}
          </div>
        </div>
      )}

      {job.errors.map((e) => (
        <p key={e} className="err">
          {e}
        </p>
      ))}
      {(done || job.connection === 'failed') && (
        <div className="nav">
          <button type="button" className="btn" onClick={onRunAgain} disabled={running}>
            Run again
          </button>
          {onRunLive && (
            <button type="button" className="btn" onClick={onRunLive} disabled={running}>
              Run live
            </button>
          )}
        </div>
      )}
      <p className="fine">Not legal advice. Pass* = passes the checks we implemented, not engineering certification.</p>
    </div>
  )
}
