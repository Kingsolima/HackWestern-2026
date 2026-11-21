import type { DesignVariant } from '../types'

const LABEL = { cost: 'Lowest cost', performance: 'Best performance', us_first: 'US-first' }

// TODO(owner 4): tabs that switch the ModelViewer to each design's GLB.
export function DesignTabs({ designs }: { designs: DesignVariant[] }) {
  return (
    <section className="panel">
      <h2>Tournament</h2>
      {designs.length === 0 ? (
        <p className="muted">Designs appear after the tournament runs.</p>
      ) : (
        <ul>
          {designs.map((d) => (
            <li key={d.design_id}>
              {LABEL[d.objective]}: {d.motor}, ${d.cost_usd}, {d.domestic_pct}% domestic
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
