import { specAccuracy } from '../accuracy'
import { parseSpec } from '../onboarding/answers'
import type { Source, SpecRow } from '../onboarding/intake'

const SOURCE_LABEL: Record<Source, string> = {
  answer: 'Your words',
  bom: 'BOM',
  cad: 'CAD',
  default: 'Default',
  edited: 'Edited',
}

interface Props {
  rows: SpecRow[]
  /** Typed values by field; a field not in here still shows the row's own value. */
  drafts: Record<string, string>
  onDraft: (field: string, text: string) => void
}

/** Every number the job will use, grouped, with where it came from on the green/yellow/red scale.
 * Rendered from the rows the backend sends, so a new robot kind needs no change here. */
export function SpecsReview({ rows, drafts, onDraft }: Props) {
  const groups = [...new Set(rows.map((r) => r.group))]
  return (
    <>
      <div className="legend">
        <span>
          <span className="dot hi" />
          Your words / files
        </span>
        <span>
          <span className="dot mid" />
          Estimate
        </span>
        <span>
          <span className="dot lo" />
          Default
        </span>
      </div>
      {groups.map((group) => (
        <table key={group} className="specs">
          <caption>{group}</caption>
          <tbody>
            {rows
              .filter((r) => r.group === group)
              .map((r) => {
                const text = drafts[r.field] ?? String(r.value)
                const parsed = parseSpec(text, r)
                const source: Source = parsed.ok && parsed.value !== r.value ? 'edited' : r.source
                const evidence = source === 'edited' ? null : r.evidence
                const estimate = evidence?.startsWith('estimate') ?? false
                return (
                  <tr key={r.field}>
                    <th scope="row">
                      <label htmlFor={`spec-${r.field}`}>{r.label}</label>
                      {evidence && <span className="ev">{r.source === 'answer' ? `“${evidence}”` : evidence}</span>}
                    </th>
                    <td className="val">
                      <input
                        id={`spec-${r.field}`}
                        inputMode="decimal"
                        value={text}
                        aria-invalid={!parsed.ok}
                        title={parsed.ok ? undefined : `${r.label} ${parsed.error}`}
                        onChange={(e) => onDraft(r.field, e.target.value)}
                      />
                      <span className="u">{r.unit}</span>
                    </td>
                    <td>
                      <span className="src">
                        <span className={`dot ${specAccuracy(source, evidence)}`} />
                        {estimate ? 'Estimate' : SOURCE_LABEL[source]}
                      </span>
                    </td>
                  </tr>
                )
              })}
          </tbody>
        </table>
      ))}
    </>
  )
}
