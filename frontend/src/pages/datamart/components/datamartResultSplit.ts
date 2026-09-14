/**
 * Split final datamart rows into SQL detail vs rows appended by post-processing
 * (append_aggregate_row, append_per_group_aggregate_rows), using the raw snapshot
 * row count from the API.
 */

export type AppendSummarySplit = {
  detailRows: unknown[][]
  summaryRows: unknown[][]
  sqlDetailCount: number
}

export function hasAppendRowSteps(
  postProcessConfig: Array<Record<string, unknown>> | null | undefined,
): boolean {
  return !!postProcessConfig?.some((s) => {
    const t = String(s?.type ?? '')
    return t === 'append_aggregate_row' || t === 'append_per_group_aggregate_rows'
  })
}

/** Last append_per_group / append_aggregate step for label hints (search from end). */
export function lastAppendStep(
  postProcessConfig: Array<Record<string, unknown>> | null | undefined,
): Record<string, unknown> | null {
  if (!postProcessConfig?.length) return null
  for (let i = postProcessConfig.length - 1; i >= 0; i--) {
    const t = String(postProcessConfig[i]?.type ?? '')
    if (t === 'append_per_group_aggregate_rows' || t === 'append_aggregate_row') {
      return postProcessConfig[i]
    }
  }
  return null
}

const FUNC_METRIC_LABELS: Record<string, string> = {
  COUNT: 'Count',
  SUM: 'Total',
  AVG: 'Average',
  MIN: 'Minimum',
  MAX: 'Maximum',
}

function resolveColumnName(columns: string[], key: string): string | undefined {
  const exact = columns.find((c) => c === key)
  if (exact) return exact
  const low = key.toLowerCase()
  return columns.find((c) => c.toLowerCase() === low)
}

/**
 * Map result column → human label for post-process summary cards.
 * Uses optional step.aggregation_labels, else aggregation function (COUNT → "Count", not "Employee Id").
 */
export function buildAggregationMetricLabels(
  step: Record<string, unknown> | null,
  columns: string[],
): Map<string, string> {
  const out = new Map<string, string>()
  if (!step) return out

  const aggs = step.aggregations
  if (!aggs || typeof aggs !== 'object' || Array.isArray(aggs)) return out

  const custom =
    step.aggregation_labels && typeof step.aggregation_labels === 'object' && !Array.isArray(step.aggregation_labels)
      ? (step.aggregation_labels as Record<string, unknown>)
      : {}

  for (const [key, func] of Object.entries(aggs as Record<string, unknown>)) {
    const col = resolveColumnName(columns, key)
    if (!col) continue

    const override =
      custom[key] ?? custom[col] ?? custom[col.toLowerCase()]
    if (override != null && String(override).trim()) {
      out.set(col, String(override).trim())
      continue
    }

    const f = String(func ?? '').toUpperCase()
    out.set(col, FUNC_METRIC_LABELS[f] ?? f)
  }

  return out
}

/**
 * When the server returned raw_rows (pre–post-process) and the final row set is longer,
 * trailing rows are treated as appended summaries for separate display.
 */
export function splitAppendSummaryFromFinal(
  rows: unknown[][],
  rawRows: unknown[][] | null | undefined,
  postProcessConfig: Array<Record<string, unknown>> | null | undefined,
): AppendSummarySplit | null {
  if (!hasAppendRowSteps(postProcessConfig)) return null
  const n = rawRows?.length ?? 0
  if (n <= 0 || rows.length <= n) return null
  return {
    detailRows: rows.slice(0, n),
    summaryRows: rows.slice(n),
    sqlDetailCount: n,
  }
}
