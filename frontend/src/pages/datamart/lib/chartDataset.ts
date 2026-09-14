/**
 * Resolve tabular data for a chart definition (shared by render + CSV export).
 */
import type { DatamartChartConfigV1 } from '../charts/chartConfig'
import { filterRowsForChartScope } from '../charts/chartSuggestions'

export function rowsToNamedRecords(
  columns: string[],
  rows: unknown[][],
): Record<string, unknown>[] {
  return rows.map((row) => {
    const rec: Record<string, unknown> = {}
    columns.forEach((c, i) => {
      rec[c] = row[i]
    })
    return rec
  })
}

export function resolveChartDataset(
  chart: DatamartChartConfigV1,
  finalColumns: string[],
  finalRows: unknown[][],
  rawColumns: string[] | null | undefined,
  rawRows: unknown[][] | null | undefined,
): Record<string, unknown>[] {
  if (chart.data_source === 'sql_raw' && rawColumns?.length && rawRows?.length) {
    const scoped = filterRowsForChartScope(rawColumns, rawRows, rawRows, chart.row_scope)
    return rowsToNamedRecords(rawColumns, scoped)
  }
  if (!finalColumns.length || !finalRows.length) return []
  const scoped = filterRowsForChartScope(finalColumns, finalRows, rawRows, chart.row_scope)
  return rowsToNamedRecords(finalColumns, scoped)
}

export function chartSeriesRecords(
  data: Record<string, unknown>[],
  chart: DatamartChartConfigV1,
): Array<{ category: string; value: number }> {
  const cat = chart.category_column
  const val = chart.value_column
  return data.map((row, idx) => ({
    category: String(row[cat] ?? `Row ${idx + 1}`),
    value: toNumber(row[val]),
  }))
}

function toNumber(v: unknown): number {
  if (v === null || v === undefined) return 0
  if (typeof v === 'number' && !Number.isNaN(v)) return v
  const n = Number(String(v).replace(/,/g, ''))
  return Number.isFinite(n) ? n : 0
}
