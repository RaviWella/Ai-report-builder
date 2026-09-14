/**
 * Detect small GROUP BY / aggregate result sets suitable for key-value cards
 * (when post-process append rows are not used).
 */
import { hasAppendRowSteps } from '../components/datamartResultSplit'

const MAX_GROUPED_ROWS = 24

function toNumber(v: unknown): number | null {
  if (v === null || v === undefined || v === '') return null
  if (typeof v === 'number' && Number.isFinite(v)) return v
  const n = Number(String(v).replace(/,/g, ''))
  return Number.isFinite(n) ? n : null
}

function formatHeader(col: string): string {
  return col
    .replace(/_/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

export interface GroupedMetricRow {
  title: string
  metrics: Array<{ label: string; value: string }>
}

export interface GroupedResultMetricsView {
  sectionTitle: string
  rows: GroupedMetricRow[]
}

/**
 * When the SQL result is a compact breakdown (e.g. count per branch) without
 * append_aggregate post-process, show cards instead of only a sparse table.
 */
export function buildGroupedResultMetricsView(
  columns: string[],
  rows: unknown[][],
  postProcessConfig: Array<Record<string, unknown>> | null | undefined,
): GroupedResultMetricsView | null {
  if (hasAppendRowSteps(postProcessConfig)) return null
  if (!columns.length || !rows.length || rows.length > MAX_GROUPED_ROWS) return null

  const numericIdx: number[] = []
  const labelIdx: number[] = []

  columns.forEach((_col, i) => {
    let numeric = 0
    let seen = 0
    for (let r = 0; r < Math.min(rows.length, 30); r++) {
      const v = rows[r]?.[i]
      if (v === null || v === undefined || v === '') continue
      seen++
      if (toNumber(v) !== null) numeric++
    }
    const mostlyNumeric = seen > 0 && numeric / seen >= 0.85
    if (mostlyNumeric) numericIdx.push(i)
    else labelIdx.push(i)
  })

  if (!numericIdx.length || !labelIdx.length) return null
  if (numericIdx.length > 3) return null

  const primaryLabelIdx = labelIdx[0]
  const primaryLabelCol = columns[primaryLabelIdx]

  const metricRows: GroupedMetricRow[] = rows.map((row, rIdx) => {
    const titleRaw = row[primaryLabelIdx]
    const title =
      titleRaw !== null && titleRaw !== undefined && String(titleRaw).trim() !== ''
        ? String(titleRaw)
        : `Row ${rIdx + 1}`

    const metrics = numericIdx.map((i) => ({
      label: formatHeader(columns[i]),
      value: formatMetricValue(row[i]),
    }))

    return { title, metrics }
  })

  return {
    sectionTitle: `Breakdown by ${formatHeader(primaryLabelCol)}`,
    rows: metricRows,
  }
}

function formatMetricValue(value: unknown): string {
  const n = toNumber(value)
  if (n !== null) {
    const frac = Math.abs(n % 1) > 1e-9
    return n.toLocaleString(undefined, {
      maximumFractionDigits: frac ? 2 : 0,
      minimumFractionDigits: 0,
    })
  }
  if (value === null || value === undefined) return '—'
  return String(value)
}
