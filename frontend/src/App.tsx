import { useEffect, useState } from 'react'
import { api } from './api'
import { AgentTiles } from './components/AgentTiles'
import { ChecksTable } from './components/ChecksTable'
import { ComplianceCard } from './components/ComplianceCard'
import { DesignTabs } from './components/DesignTabs'
import { ModelViewer } from './components/ModelViewer'
import type { CheckResult, ComplianceCard as Card, DesignVariant } from './types'

export default function App() {
  const [health, setHealth] = useState<string>('checking…')
  const [card, setCard] = useState<Card | null>(null)
  const [results, setResults] = useState<CheckResult[]>([])
  const [designs, setDesigns] = useState<DesignVariant[]>([])

  useEffect(() => {
    api.health().then((h) => setHealth(h.status), () => setHealth('backend unreachable'))
    api.compliance().then(setCard, console.error)
    api.designs().then(setDesigns, console.error)
    api
      .seedCandidates()
      .then((cs) => Promise.all(cs.map(api.checks)))
      .then(setResults, console.error)
  }, [])

  return (
    <main>
      <header>
        <h1>AI Robot Redesign Engine</h1>
        <span className="muted">API: {health}</span>
      </header>
      <ModelViewer src="/cad/files/test_23.glb" />
      <div className="grid">
        <ComplianceCard card={card} />
        <AgentTiles />
      </div>
      <ChecksTable results={results} />
      <DesignTabs designs={designs} />
      <footer className="muted">Not legal advice. COTS questions: flag for counsel.</footer>
    </main>
  )
}
