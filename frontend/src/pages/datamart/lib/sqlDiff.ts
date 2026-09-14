/**
 * Lightweight SQL comparison helpers for template version timeline.
 */

export function normalizeSql(sql: string): string {
  return sql.replace(/\r\n/g, '\n').trim()
}

export function sqlEquals(a: string, b: string): boolean {
  return normalizeSql(a) === normalizeSql(b)
}

export function countSqlLineChanges(baseline: string, candidate: string): {
  changed: boolean
  added: number
  removed: number
} {
  const baseLines = normalizeSql(baseline).split('\n')
  const candLines = normalizeSql(candidate).split('\n')
  const baseSet = new Set(baseLines)
  const candSet = new Set(candLines)
  let added = 0
  let removed = 0
  for (const line of candLines) {
    if (!baseSet.has(line)) added += 1
  }
  for (const line of baseLines) {
    if (!candSet.has(line)) removed += 1
  }
  return {
    changed: added > 0 || removed > 0,
    added,
    removed,
  }
}

export function formatSqlDiffSummary(baseline: string, candidate: string): string {
  const { changed, added, removed } = countSqlLineChanges(baseline, candidate)
  if (!changed) return 'Same SQL as reference'
  const parts: string[] = []
  if (added) parts.push(`+${added} line${added === 1 ? '' : 's'}`)
  if (removed) parts.push(`-${removed} line${removed === 1 ? '' : 's'}`)
  return parts.join(', ')
}
