/**
 * Minimal-diff follow-up prompts for report quick actions.
 */

export function buildRemoveColumnPrompt(columnName: string): string {
  return `Please update the SQL from your previous answer: remove the "${columnName}" column from the result (keep the same filters and joins).`
}

export function buildFilterPrompt(filterDescription: string): string {
  const trimmed = filterDescription.trim()
  return `Please update the SQL from your previous answer: add or tighten the filter so that ${trimmed}.`
}

export function buildSortPrompt(columnName: string, direction: 'asc' | 'desc' = 'asc'): string {
  const dir = direction === 'desc' ? 'descending' : 'ascending'
  return `Please update the SQL from your previous answer: sort the results by "${columnName}" ${dir}.`
}

export function truncateContextLabel(text: string, maxLen = 48): string {
  const t = text.trim()
  if (t.length <= maxLen) return t
  return `${t.slice(0, maxLen - 1)}…`
}
