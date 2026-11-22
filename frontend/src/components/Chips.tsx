import { levelAccuracy } from '../accuracy'
import type { Level, Priority } from '../events'

export function LevelChip({ level, title, children }: { level: Level; title?: string; children?: string }) {
  return (
    <span className={`chip level-${level}`} title={title}>
      <span className={`dot ${levelAccuracy(level)}`} />
      {children ?? level}
    </span>
  )
}

/** The 0-9 priority as a chip; a range means some evidence is missing. */
export function PriorityChip({ priority }: { priority: Priority }) {
  const range = priority.hi > priority.lo ? `${priority.lo}–${priority.hi}` : `${priority.lo}`
  return <LevelChip level={priority.level}>{`${priority.level} ${range}/9`}</LevelChip>
}
