import { Suspense, lazy, useEffect, useRef, useState } from 'react'
import { api } from './api'
import { AgentBays } from './components/AgentBays'
import { Brief } from './components/Brief'
import { JobConsole } from './components/JobConsole'
import { Onboarding, type Progress } from './components/Onboarding'
import { Report } from './components/Report'
import { Welcome } from './components/Welcome'
import { STAGE_ORDER, stageLabel } from './events'
import { isTerminal, useJob, type CreateJobOptions } from './job'
import { askLiveToken } from './liveToken'
import { genericModelNotes } from './modelNotes'
import type { PartLine } from './modelParts'
import { loadSaved, matchesDemo, needsLiveAgents, saveOnboarded, toRobot, type Onboarded } from './onboarding/answers'
import type { CadMeasure } from './onboarding/intake'
import { stepsFor, type OpenAnswers } from './onboarding/questions'
import { PROJECTS, PROJECT_ROBOT, cadUrl, starterModel, type ProjectId } from './projects'
import { useFreeArea } from './stageArea'
import type { BomRow, ComplianceCard as Card, Robot } from './types'

// ?live=1 shows a "Run live" button. The token is asked once per tab and kept in sessionStorage.
const LIVE_ENABLED = new URLSearchParams(window.location.search).get('live') === '1'
// three.js is most of the bundle: load it beside the welcome screen instead of before it.
const CadViewer = lazy(() => import('./components/CadViewer').then((m) => ({ default: m.CadViewer })))

/** Start a job that makes real calls ('mixed' replays what is recorded and runs the rest). */
async function startWithToken(
  mode: 'live' | 'mixed',
  start: (mode: 'live' | 'mixed', opts: CreateJobOptions) => void,
  opts: CreateJobOptions,
) {
  const token = await askLiveToken('Live jobs spend TinyFish credit. Enter the live token:')
  if (token) start(mode, { ...opts, liveToken: token })
}

function Clock() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(t)
  }, [])
  return <span className="label">{now.toLocaleTimeString('en-CA', { hour12: false })}</span>
}

/** Console content: the onboarding questions, a demo project waiting to launch, or the job. */
type Mode = 'onboarding' | 'ready' | 'job'
/** The top-level tab. */
type View = 'model' | 'agents' | 'report'
type ModelStatus = { parts: number; size_mm: [number, number, number] } | 'error' | null

export default function App() {
  const [health, setHealth] = useState<'checking' | 'ok' | 'down'>('checking')
  const [demo, setDemo] = useState<Robot | null>(null)
  const [example, setExample] = useState<OpenAnswers | null>(null)
  const [baselineCard, setBaselineCard] = useState<Card | null>(null)
  const { state: job, start } = useJob()

  const [onboarded, setOnboarded] = useState(() => loadSaved()?.onboarded ?? null)
  const [welcome, setWelcome] = useState<'on' | 'leaving' | 'off'>(onboarded ? 'off' : 'on')
  const [mode, setMode] = useState<Mode>('onboarding')
  const [project, setProject] = useState<ProjectId | null>(null)
  const [bom, setBom] = useState<BomRow[]>(onboarded?.bom ?? [])
  const [cad, setCad] = useState<CadMeasure | null>(null)
  const [progress, setProgress] = useState<Progress>({
    steps: stepsFor(Boolean(onboarded?.arm)),
    index: 0,
    company: onboarded?.company ?? [],
    arm: onboarded?.arm ?? null,
  })
  const [showAfter, setShowAfter] = useState(true)
  const [model, setModel] = useState<ModelStatus>(null)
  const [view, setView] = useState<View>('model')

  useEffect(() => {
    api.health().then(() => setHealth('ok'), () => setHealth('down'))
    api.robot().then(setDemo, console.error)
    api.example().then(setExample, console.error)
    api.compliance().then(setBaselineCard, console.error)
  }, [])

  const leaveWelcome = () => {
    setWelcome('leaving')
    setTimeout(() => setWelcome('off'), 900)
  }

  const jobOptions = (o: Onboarded | null): CreateJobOptions =>
    project ? { projectId: project } : { robot: o && demo ? toRobot(o, demo) : undefined, company: o?.company }
  /** Replay when the recordings fit this robot; otherwise a mixed job, which needs the token. */
  const run = (o: Onboarded | null) => {
    setMode('job')
    setShowAfter(true)
    if (o && !project && needsLiveAgents(o.specs)) void startWithToken('mixed', start, jobOptions(o))
    else start('replay', jobOptions(o))
  }
  const restart = () => {
    saveOnboarded(null)
    window.location.reload()
  }

  const launched = mode === 'job'
  const done = isTerminal(job)
  const runs = job.runOrder.map((id) => job.runs[id])
  const candidate = job.candidates[0]
  const designs = job.baseline && candidate ? { before: job.baseline, after: candidate } : null
  const shown = designs ? (showAfter ? designs.after : designs.before) : null
  const robot = job.project?.cad_robot ?? (project ? PROJECT_ROBOT[project] : (progress.arm?.cad_robot ?? 'wheeled'))
  const starter = starterModel(robot)
  const src = welcome === 'on' ? null : shown ? cadUrl(shown.glb_url) : starter.src
  const deep = launched && job.stage !== null && job.stage !== 'CREATED'

  const lines: PartLine[] = job.project
    ? job.project.bom.map((l) => ({ part: l.part, category: l.domain, qty: l.qty, price: l.unit_price_usd, origin: l.origin_country }))
    : bom.map((r) => ({ part: r.part, category: r.category, qty: r.qty, price: r.unit_cost_usd === null ? null : Number(r.unit_cost_usd), origin: r.origin }))
  const modelNotes =
    job.project?.id === 'onboarded' && job.project.robot_kind === 'wheeled' ? genericModelNotes(job.project) : []
  // The baseline compliance card comes from an endpoint that always uses the demo robot, so it
  // is only right when the user's robot gives the same numbers.
  const demoPanels = project === null && (!onboarded || (demo != null && matchesDemo(onboarded, demo)))
  const card = job.compliance ?? (demoPanels ? baselineCard : null)

  const review = mode === 'onboarding' && progress.steps[progress.index] === 'review'
  const area = useFreeArea([welcome, mode, review, done, designs !== null, view].join('|'))

  // The demo flow: the agents take over the screen when a job starts, the report when it ends.
  // Each switch happens once per job; after that the tabs are the user's.
  const switched = useRef({ job: null as string | null, done: false })
  useEffect(() => {
    if (!job.jobId || job.jobId === switched.current.job) return
    switched.current = { job: job.jobId, done: false }
    setView('agents')
  }, [job.jobId])
  useEffect(() => {
    if (!done || switched.current.done) return
    switched.current.done = true
    setView('report')
  }, [done])

  const stageIndex = job.stage ? STAGE_ORDER.indexOf(job.stage) : -1
  const fraction = launched
    ? done
      ? 1
      : (stageIndex + 1) / STAGE_ORDER.length
    : mode === 'onboarding'
      ? (progress.index + 1) / (progress.steps.length + 1)
      : 0
  const running = job.connection === 'starting' || job.connection === 'streaming'
  const tabs: { id: View; title: string; on: boolean; badge?: string }[] = [
    { id: 'model', title: '3D model', on: true },
    { id: 'agents', title: 'Agents', on: launched, badge: running && job.stage ? stageLabel(job.stage) : undefined },
    { id: 'report', title: 'Report', on: done },
  ]
  const projectLabel = PROJECTS.find((p) => p.id === project)?.label

  return (
    <>
      <Suspense fallback={null}>
        <CadViewer src={src} robot={robot} deep={deep} build={designs !== null && showAfter} lines={lines} area={area} onStatus={setModel} />
      </Suspense>

      {welcome !== 'off' && (
        <Welcome
          sample={demo?.bom ?? null}
          leaving={welcome === 'leaving'}
          onContinue={(rows, c) => {
            setBom(rows)
            setCad(c)
            setProject(null)
            setOnboarded(null)
            setMode('onboarding')
            leaveWelcome()
          }}
          onProject={(id) => {
            setProject(id)
            setMode('ready')
            leaveWelcome()
          }}
        />
      )}

      <div className={`shell${welcome === 'on' ? '' : ' on'}${launched ? ' launched' : ''}`}>
        <header className="topbar">
          <div className="brand">BOMbot</div>
          <nav className="views" role="tablist" aria-label="Views">
            {tabs.map((t) => (
              <button
                key={t.id}
                type="button"
                role="tab"
                aria-selected={view === t.id}
                className={view === t.id ? 'on' : ''}
                disabled={!t.on}
                onClick={() => setView(t.id)}
              >
                {t.title}
                {t.badge && (
                  <span className="badge-run">
                    <span className="dot acc blink" />
                    {t.badge}
                  </span>
                )}
              </button>
            ))}
          </nav>
          <div className="status">
            <span className="label">
              <span className={`dot ${health === 'ok' ? 'hi' : health === 'down' ? 'lo' : ''}`} />
              {health === 'down' ? 'API offline' : 'API online'}
            </span>
            {job.mode && (
              <span className="label">
                <span className={`dot ${running ? 'acc blink' : ''}`} />
                {job.mode}
                {running ? ' / running' : ''}
              </span>
            )}
            <Clock />
            {launched && project === null && (
              <button type="button" className="linkbtn" onClick={() => setMode('onboarding')} disabled={running}>
                Edit answers
              </button>
            )}
            <button type="button" className="linkbtn" onClick={restart}>
              Restart
            </button>
          </div>
          <div className="progress" aria-hidden="true">
            <i style={{ width: `${fraction * 100}%` }} />
          </div>
        </header>

        {view === 'model' && (
          <>
        <div className="hud">
          <div>
            Model <b>{shown?.label ?? starter.title}</b>
          </div>
          {model === 'error' ? (
            <div className="lo-text">Model unavailable: is the CAD worker running?</div>
          ) : (
            model && (
              <div>
                <b>{model.parts}</b> parts / {model.size_mm.join(' x ')} mm
              </div>
            )
          )}
          <div>Hover a part / drag to orbit</div>
          {designs && (
            <div className="toggle" role="radiogroup" aria-label="Before or after the redesign">
              <button type="button" role="radio" aria-checked={!showAfter} className={showAfter ? '' : 'on'} onClick={() => setShowAfter(false)}>
                Before
              </button>
              <button type="button" role="radio" aria-checked={showAfter} className={showAfter ? 'on' : ''} onClick={() => setShowAfter(true)}>
                After
              </button>
            </div>
          )}
        </div>

        <aside className={`console frame${review ? ' wide' : ''}${launched && done ? ' report-wide' : ''}`}>
          {mode === 'job' ? (
            <JobConsole
              job={job}
              onRunAgain={() => run(onboarded)}
              onRunLive={LIVE_ENABLED ? () => void startWithToken('live', start, jobOptions(onboarded)) : undefined}
              onOpenReport={() => setView('report')}
            />
          ) : mode === 'ready' ? (
            <div className="q">
              <div className="label">Demo project</div>
              <h1>{projectLabel}</h1>
              <p className="help">
                A prepared project with its own parts list and facts. Agents replay recorded runs to find a better
                source for its deep line, then the CAD worker regenerates the mount.
              </p>
              <div className="nav">
                <button type="button" className="btn go" onClick={() => run(null)}>
                  Find and Redesign
                </button>
                <button type="button" className="link" onClick={restart}>
                  Back
                </button>
              </div>
            </div>
          ) : demo ? (
            <Onboarding
              key={onboarded ? 'edit' : 'new'}
              demo={demo}
              example={example}
              bom={bom}
              cad={cad}
              initial={onboarded}
              onProgress={setProgress}
              onChangeBom={restart}
              onDone={(o) => {
                saveOnboarded(o)
                setOnboarded(o)
                run(o)
              }}
            />
          ) : (
            <p className="help">{health === 'down' ? 'The backend is unreachable, so the questions cannot load.' : 'Loading…'}</p>
          )}
        </aside>

        {mode === 'onboarding' && bom.length > 0 && (
          <aside className="dossier frame">
            <Brief bom={bom} company={progress.company} />
          </aside>
        )}
          </>
        )}

        {view === 'agents' && (
          <div className="page agents-page">
            <AgentBays runs={runs} />
          </div>
        )}
        {view === 'report' && done && (
          <Report job={job} onboarded={project ? null : onboarded} card={card} modelNotes={modelNotes} />
        )}
      </div>
    </>
  )
}
