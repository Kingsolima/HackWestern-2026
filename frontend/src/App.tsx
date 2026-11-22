import { useEffect, useState } from 'react'
import { api } from './api'
import { AgentTiles } from './components/AgentTiles'
import { ChecksTable } from './components/ChecksTable'
import { ClaimsList } from './components/ClaimsList'
import { ComplianceCard } from './components/ComplianceCard'
import { DesignTabs } from './components/DesignTabs'
import { JobBar } from './components/JobBar'
import { ModelViewer } from './components/ModelViewer'
import { useJob } from './job'
import type { CheckResult, ComplianceCard as Card, DesignVariant } from './types'

export default function App() {
  const [health, setHealth] = useState<string>('checking…')
  const [baselineCard, setBaselineCard] = useState<Card | null>(null)
  // Checks and designs stay on the pre-v3 endpoints until the coordinated shape switch.
  const [results, setResults] = useState<CheckResult[]>([])
  const [designs, setDesigns] = useState<DesignVariant[]>([])
  const { state: job, start } = useJob()

  useEffect(() => {
    api.health().then((h) => setHealth(h.status), () => setHealth('backend unreachable'))
    api.compliance().then(setBaselineCard, console.error)
    api.designs().then(setDesigns, console.error)
    api
      .seedCandidates()
      .then((cs) => Promise.all(cs.map(api.checks)))
      .then(setResults, console.error)
  }, [])

  const runs = job.runOrder.map((id) => job.runs[id])

  return (
    <main>
      <header>
        <h1>AI Robot Redesign Engine</h1>
        <span className="muted">API: {health}</span>
      </header>
      <JobBar state={job} onStart={() => start('replay')} />
      <ModelViewer src="/cad/files/test_23.glb" />
      <div className="grid">
        <ComplianceCard card={job.compliance ?? baselineCard} />
        <AgentTiles runs={runs} />
      </div>
      <ClaimsList claims={job.claims} />
      <ChecksTable results={results} />
      <DesignTabs designs={designs} />
      <footer className="muted">
        Not legal advice. Pass* = passes the checks we implemented, not engineering certification.
      </footer>
    </main>
  )
}
