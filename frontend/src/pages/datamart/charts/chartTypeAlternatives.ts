/**
 * Heuristic chart-type alternatives for the same category/value binding.
 * No LLM — rules mirror chartSuggestions.pickChartType and Recharts limits.
 */
import type { DatamartChartConfigV1, DatamartChartType } from './chartConfig'

export interface ChartTypeOption {
  type: DatamartChartType
  label: string
  hint: string
}

const TYPE_META: Record<DatamartChartType, { label: string; hint: string }> = {
  column: {
    label: 'Column',
    hint: 'Vertical bars — easy to compare values across categories.',
  },
  bar: {
    label: 'Bar',
    hint: 'Horizontal bars — better for long category names.',
  },
  pie: {
    label: 'Pie',
    hint: 'Share of whole — best with a small number of categories.',
  },
  line: {
    label: 'Line',
    hint: 'Trend-style view — works when categories have a natural order.',
  },
}

const TEMPORAL_HINTS = [
  'month', 'year', 'quarter', 'week', 'day', 'date', 'period', 'fy', 'fiscal',
]

function distinctCategoryCount(
  data: Record<string, unknown>[],
  categoryColumn: string,
): number {
  const s = new Set<string>()
  for (const row of data) {
    const v = row[categoryColumn]
    if (v === null || v === undefined || v === '') continue
    s.add(String(v))
  }
  return s.size
}

function categoryLooksTemporal(categoryColumn: string): boolean {
  const low = categoryColumn.toLowerCase()
  return TEMPORAL_HINTS.some((h) => low.includes(h))
}

/** Whether a chart type is a reasonable view for this dataset shape. */
export function isChartTypeViable(
  chartType: DatamartChartType,
  rowCount: number,
  categoryCardinality: number,
  categoryColumn: string,
): boolean {
  if (rowCount < 1 || categoryCardinality < 1) return false

  switch (chartType) {
    case 'pie':
      return categoryCardinality >= 2 && categoryCardinality <= 12 && rowCount <= 24
    case 'bar':
      return categoryCardinality >= 2 && categoryCardinality <= 30
    case 'column':
      return categoryCardinality >= 2 && categoryCardinality <= 40
    case 'line':
      if (categoryCardinality < 3) return false
      if (categoryCardinality > 36) return false
      if (categoryLooksTemporal(categoryColumn)) return true
      return categoryCardinality >= 4 && rowCount >= 4
    default:
      return false
  }
}

/** Other chart types that can represent the same data binding. */
export function getAlternativeChartTypes(
  chart: DatamartChartConfigV1,
  data: Record<string, unknown>[],
): ChartTypeOption[] {
  const rowCount = data.length
  const card = distinctCategoryCount(data, chart.category_column)
  const types: DatamartChartType[] = ['column', 'bar', 'pie', 'line']

  return types
    .filter((t) => t !== chart.chart_type && isChartTypeViable(t, rowCount, card, chart.category_column))
    .map((type) => ({
      type,
      label: TYPE_META[type].label,
      hint: TYPE_META[type].hint,
    }))
}

export function chartTypeLabel(chartType: DatamartChartType): string {
  return TYPE_META[chartType].label
}

/** Same chart id and columns; only type (and optional title tweak) changes. */
export function convertChartType(
  chart: DatamartChartConfigV1,
  newType: DatamartChartType,
): DatamartChartConfigV1 {
  const next = { ...chart, chart_type: newType }
  const title = chart.title?.trim()
  if (title) {
    const oldLabel = chartTypeLabel(chart.chart_type)
    const newLabel = chartTypeLabel(newType)
    if (title.toLowerCase().startsWith(oldLabel.toLowerCase())) {
      next.title = newLabel + title.slice(oldLabel.length)
    }
  }
  return next
}

/** Match saved charts to suggestions regardless of chart_type (convert in place). */
function bindingBlockKey(id: string | null | undefined): string {
  if (id == null) return 'primary'
  const t = String(id).trim()
  return t.length > 0 ? t : 'primary'
}

export function chartBindingKey(c: DatamartChartConfigV1): string {
  return [
    bindingBlockKey(c.result_block_id),
    c.row_scope ?? 'all',
    c.category_column,
    c.value_column,
  ].join('|')
}
