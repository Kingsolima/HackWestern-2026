import type { Design } from '../events'
import { cadUrl } from '../projects'
import { designChanges } from '../report'

export function DesignChanges({ before, after, notes }: { before: Design; after: Design; notes: string[] }) {
  return (
    <>
      {notes.map((n) => (
        <p key={n} className="note">
          {n}
        </p>
      ))}
      <table className="grid">
        <thead>
          <tr>
            <th>What changed</th>
            <th>{before.label}</th>
            <th>{after.label}</th>
          </tr>
        </thead>
        <tbody>
          {designChanges(before, after).map((r) => (
            <tr key={r.label} className={r.before !== r.after ? 'changed' : ''}>
              <td>{r.label}</td>
              <td>{r.before}</td>
              <td>{r.after}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="fine">
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
