import type { CompanyFact } from '../onboarding/intake'
import type { BomRow } from '../types'

/** What we know before launch: where the BOM's parts come from, and the facts read from the
 * user's answers with the words each one came from. */
export function Brief({ bom, company }: { bom: BomRow[]; company: CompanyFact[] }) {
  const origins = new Map<string, number>()
  for (const r of bom) origins.set(r.origin, (origins.get(r.origin) ?? 0) + 1)
  const flags = bom.filter((r) => r.supply_risk)
  const total = bom.reduce((sum, r) => sum + r.qty * Number(r.unit_cost_usd), 0)
  const stated = company.filter((c) => c.quote)

  return (
    <div className="brief">
      <section>
        <div className="label">Bill of materials</div>
        <div className="fact">
          <span className="k">Lines</span>
          <span>
            {bom.length} / ${total.toFixed(0)} per robot
          </span>
        </div>
        <div className="fact">
          <span className="k">Origins</span>
          <span className="chips">
            {[...origins.entries()]
              .sort((a, b) => b[1] - a[1])
              .map(([country, n]) => (
                <span key={country} className="chip">
                  <span className={`dot ${country === 'unknown' ? 'lo' : 'hi'}`} />
                  {country === 'unknown' ? 'Unknown' : country} {n}
                </span>
              ))}
          </span>
        </div>
        {flags.length > 0 && (
          <div className="fact">
            <span className="k">Flags</span>
            <span className="chips">
              {flags.map((r) => (
                <span key={r.part} className="chip">
                  {r.part} / {r.supply_risk!.replaceAll('_', ' ')}
                </span>
              ))}
            </span>
          </div>
        )}
      </section>
      {stated.length > 0 && (
        <section>
          <div className="label">From your words</div>
          {stated.map((c) => (
            <div key={c.field} className="fact">
              <span className="k">{c.label}</span>
              <span>
                {c.value}
                <span className="qt">“{c.quote}”</span>
              </span>
            </div>
          ))}
        </section>
      )}
    </div>
  )
}
