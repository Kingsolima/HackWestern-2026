import { parseSpec } from '../onboarding/answers'
import type { Source, SpecRow } from '../onboarding/intake'

const SOURCE_LABEL: Record<Source, string> = {
  answer: 'from your answer',
  bom: 'from BOM',
  cad: 'from CAD',
  default: 'default',
  edited: 'edited',
}

interface Props {
  rows: SpecRow[]
  /** Typed values by field; a field not in here still shows the row's own value. */
  drafts: Record<string, string>
  onDraft: (field: string, text: string) => void
}

/** Every number the job will use, grouped, with where it came from. Rendered from the rows the
 * backend sends, so a new robot kind needs no change here. */
export function SpecsReview({ rows, drafts, onDraft }: Props) {
  const groups = [...new Set(rows.map((r) => r.group))]
  return (
    <div className="ob-specs">
      {groups.map((group) => (
        <table key={group}>
          <caption>{group}</caption>
          <tbody>
            {rows
              .filter((r) => r.group === group)
              .map((r) => {
                const text = drafts[r.field] ?? String(r.value)
                const parsed = parseSpec(text, r)
                const source: Source = parsed.ok && parsed.value !== r.value ? 'edited' : r.source
                const evidence = source === 'edited' ? null : r.evidence
                return (
                  <tr key={r.field}>
                    <th scope="row">
                      <label htmlFor={`spec-${r.field}`}>{r.label}</label>
                      {evidence && (
                        <span className="muted ob-evidence">
                          {r.source === 'answer' ? `“${evidence}”` : evidence}
                        </span>
                      )}
                    </th>
                    <td className="ob-spec-value">
                      <input
                        id={`spec-${r.field}`}
                        className="ob-input"
                        inputMode="decimal"
                        value={text}
                        aria-invalid={!parsed.ok}
                        title={parsed.ok ? undefined : `${r.label} ${parsed.error}`}
                        onChange={(e) => onDraft(r.field, e.target.value)}
                      />
                      <span className="muted">{r.unit}</span>
                    </td>
                    <td>
                      <span className={`badge source-${source}`}>{SOURCE_LABEL[source]}</span>
                    </td>
                  </tr>
                )
              })}
          </tbody>
        </table>
      ))}
    </div>
  )
}
