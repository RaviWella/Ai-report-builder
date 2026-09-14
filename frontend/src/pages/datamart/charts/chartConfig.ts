/**
 * Datamart chart specification v1 — mirrors backend DatamartChartConfigV1 (JSONB).
 * Serialized per assistant message / template version; rendered with Recharts.
 */
export type DatamartChartType = 'bar' | 'column' | 'pie' | 'line'

export type DatamartChartDataSource = 'final' | 'sql_raw'

/** Which slice of the result set to plot (when post-process appends summary rows). */
export type DatamartChartRowScope = 'all' | 'sql_detail_only' | 'append_summaries_only'

/** Row order for axis charts (column / bar / line). */
export type DatamartChartSortOrder =
  | 'original'
  | 'value_desc'
  | 'value_asc'
  | 'category_asc'
  | 'category_desc'

export interface DatamartChartConfigV1 {
  schema_version: 1
  id: string
  chart_type: DatamartChartType
  title?: string | null
  data_source: DatamartChartDataSource
  /** When set, chart reads from that extra_result_blocks dataset; omit or null for primary SQL. */
  result_block_id?: string | null
  /** Default all — use append_summaries_only for per-group post-process cards. */
  row_scope?: DatamartChartRowScope
  category_column: string
  value_column: string
  show_legend?: boolean
  /** Optional sort applied before render (axis charts). */
  sort_order?: DatamartChartSortOrder
}

export function isDatamartChartConfigV1(v: unknown): v is DatamartChartConfigV1 {
  if (!v || typeof v !== 'object') return false
  const o = v as Record<string, unknown>
  return (
    o.schema_version === 1 &&
    typeof o.id === 'string' &&
    typeof o.chart_type === 'string' &&
    ['bar', 'column', 'pie', 'line'].includes(o.chart_type as string) &&
    typeof o.category_column === 'string' &&
    typeof o.value_column === 'string' &&
    (o.result_block_id == null || typeof o.result_block_id === 'string')
  )
}
