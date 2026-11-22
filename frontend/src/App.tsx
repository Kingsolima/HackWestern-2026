import { useEffect, useState } from 'react'
import { api } from './api'
import { AgentTiles } from './components/AgentTiles'
import { BeforeAfterViewer } from './components/BeforeAfterViewer'
import { ChecksTable } from './components/ChecksTable'
import { ClaimsList } from './components/ClaimsList'
import { CompanyCard } from './components/CompanyCard'
import { ComplianceCard } from './components/ComplianceCard'
import { DesignTabs } from './components/DesignTabs'
import { JobBar } from './components/JobBar'
import { ModelViewer } from './components/ModelViewer'
import { Onboarding } from './components/Onboarding'
import { ProjectCard } from './components/ProjectCard'
import type { ProjectId } from './projects'
import { Recommendations } from './components/Recommendations'
import { RiskTable } from './components/RiskTable'
import { useJob, type CreateJobOptions } from './job'
import { askLiveToken } from './liveToken'
import {
  loadSaved,
  matchesDemo,
  needsLiveAgents,
  saveOnboarded,
  toRobot,
  type Onboarded,
} from './onboarding/answers'
import type { OpenAnswers } from './onboarding/questions'
import type { CheckResult, ComplianceCard as Card, DesignVariant, Robot } from './types'

// ?live=1 shows a "Run live" button. The token is asked once per tab and kept in sessionStorage.
const params = new URLSearchParams(window.location.search)
const LIVE_ENABLED = params.get('live') === '1'
// ?v4=1 shows the project switcher. Hidden until the backend handles project_id.
const V4_ENABLED = params.get('v4') === '1'

/** Start a job that makes real calls ('mixed' replays what is recorded and runs the rest). */
function startWithToken(
  mode: 'live' | 'mixed',
  start: (mode: 'live' | 'mixed', opts: CreateJobOptions) => void,
  opts: CreateJobOptions,
) {
  const token = askLiveToken('Live jobs spend TinyFish credit. Enter the live token:')
  if (token) start(mode, { ...opts, liveToken: token })
}

/** What the robot panel shows before a job: the CAD worker's starter design for the project. */
function starterRobot(project: ProjectId) {
  return project === 'ar4_club'
    ? { src: '/cad/designs/starter_ar4/glb', title: 'Robot: AR4 arm, NEMA 23 J2 motor' }
    : { src: '/cad/designs/starter/glb', title: 'Robot: NEMA 23 stepper baseline' }
}

export default function App() {
  const [health, setHealth] = useState<string>('checking…')
  const [baselineCard, setBaselineCard] = useState<Card | null>(null)
  // Checks and designs stay on the pre-v3 endpoints until the coordinated shape switch.
  const [results, setResults] = useState<CheckResult[]>([])
  const [designs, setDesigns] = useState<DesignVariant[]>([])
  const { state: job, start } = useJob()
  const [project, setProject] = useState<ProjectId>('')
  const projectId = project || undefined
  // Onboarding: the demo robot gives the defaults; `saved` is what the user confirmed before
  // (onboarded: null = they skipped to the demo robot).
  const [demo, setDemo] = useState<Robot | null>(null)
  const [example, setExample] = useState<OpenAnswers | null>(null)
  const [saved, setSaved] = useState(loadSaved)
  const [view, setView] = useState<'onboarding' | 'dashboard'>(saved ? 'dashboard' : 'onboarding')
  const onboarded = saved?.onboarded ?? null

  useEffect(() => {
    api.health().then((h) => setHealth(h.status), () => setHealth('backend unreachable'))
    api.robot().then(setDemo, console.error)
    api.example().then(setExample, console.error)
    api.compliance().then(setBaselineCard, console.error)
    api.designs().then(setDesigns, console.error)
    api
      .seedCandidates()
      .then((cs) => Promise.all(cs.map(api.checks)))
      .then(setResults, console.error)
  }, [])

  const jobOptions = (o: Onboarded | null): CreateJobOptions => ({
    projectId,
    robot: o && demo && !projectId ? toRobot(o, demo) : undefined,
  })
  /** Replay when the recordings fit this robot; otherwise a mixed job, which needs the token. */
  const run = (o: Onboarded | null) => {
    if (o && !projectId && needsLiveAgents(o.specs)) startWithToken('mixed', start, jobOptions(o))
    else start('replay', jobOptions(o))
  }
  const finishOnboarding = (o: Onboarded | null) => {
    saveOnboarded(o)
    setSaved({ onboarded: o })
    setView('dashboard')
    if (o) run(o)
  }

  if (view === 'onboarding') {
    return (
      <main className="ob-page">
        {demo ? (
          <Onboarding
            demo={demo}
            example={example}
            initial={onboarded}
            onDone={finishOnboarding}
            onSkip={() => finishOnboarding(null)}
          />
        ) : (
          <p className="muted">
            {health === 'backend unreachable' ? 'The backend is unreachable, so the questions cannot load.' : 'Loading…'}
          </p>
        )}
      </main>
    )
  }

  const runs = job.runOrder.map((id) => job.runs[id])
  // These panels come from endpoints that always use the demo robot, so they are only right
  // when the user's robot gives the same numbers.
  const demoPanels = !onboarded || (demo != null && matchesDemo(onboarded, demo))
  const card = job.compliance ?? (demoPanels ? baselineCard : null)

  return (
    <main>
      <header>
        <h1>AI Robot Redesign Engine</h1>
        <span className="muted">
          API: {health} ·{' '}
          <button type="button" className="ob-link" onClick={() => setView('onboarding')}>
            {onboarded ? 'Edit answers' : 'Describe your robot'}
          </button>
        </span>
      </header>
      <JobBar
        state={job}
        onStart={() => run(onboarded)}
        onStartLive={LIVE_ENABLED ? () => startWithToken('live', start, jobOptions(onboarded)) : undefined}
        project={project}
        onProjectChange={V4_ENABLED ? setProject : undefined}
      />
      {onboarded && !job.project && <CompanyCard company={onboarded.company} />}
      {job.project && <ProjectCard project={job.project} criteria={job.criteria} claims={job.claims} />}
      {job.riskLines.length > 0 && <RiskTable rows={job.riskLines} alternatives={job.alternatives} />}
      {job.recommendations.length > 0 && (
        <Recommendations
          recommendations={job.recommendations}
          rows={job.riskLines}
          alternatives={job.alternatives}
        />
      )}
      {job.baseline && job.candidates[0] ? (
        <BeforeAfterViewer before={job.baseline} after={job.candidates[0]} />
      ) : (
        <ModelViewer {...starterRobot(project)} />
      )}
      <div className="grid">
        {(card || demoPanels) && <ComplianceCard card={card} />}
        <AgentTiles runs={runs} />
      </div>
      <ClaimsList claims={job.claims} />
      {demoPanels && <ChecksTable results={results} />}
      {demoPanels && <DesignTabs designs={designs} />}
      <footer className="muted">
        Not legal advice. Pass* = passes the checks we implemented, not engineering certification.
      </footer>
    </main>
  )
}
