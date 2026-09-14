/**
 * Axis layout helpers: which column maps to X/Y, swap, and sort order.
 */
import type { DatamartChartConfigV1, DatamartChartSortOrder, DatamartChartType } from './chartConfig'

function toNum(v: unknown): number | null {
  if (v === null || v === undefined || v === '') return null
  if (typeof v === 'number' && Number.isFinite(v)) return v
  const n = Number(String(v).replace(/,/g, ''))
  return Number.isFinite(n) ? n : null
}

function distinctCount(data: Record<string, unknown>[], col: string): number {
  const s = new Set<string>()
  for (const row of data) {
    const v = row[col]
    if (v === null || v === undefined || v === '') continue
    s.add(String(v))
  }
  return s.size
}

function isMostlyNumeric(data: Record<string, unknown>[], col: string, sample = 40): boolean {
  let numeric = 0
  let seen = 0
  for (let i = 0; i < Math.min(data.length, sample); i++) {
    const v = data[i]?.[col]
    if (v === null || v === undefined || v === '') continue
    seen++
    if (toNum(v) !== null) numeric++
  }
  return seen > 0 && numeric / seen >= 0.85
}

function isCategoryColumn(data: Record<string, unknown>[], col: string): boolean {
  const card = distinctCount(data, col)
  if (card < 2 || card > 40) return false
  if (isMostlyNumeric(data, col) && card > 12) return false
  return true
}

export function chartHasCartesianAxes(chartType: DatamartChartType): boolean {
  return chartType === 'column' || chartType === 'bar' || chartType === 'line'
}

/** Recharts mapping: horizontal bar uses X=value, Y=category; column/line use X=category, Y=value. */
export function getAxisLabels(chart: DatamartChartConfigV1): { x: string; y: string } {
  if (chart.chart_type === 'bar') {
    return { x: chart.value_column, y: chart.category_column }
  }
  return { x: chart.category_column, y: chart.value_column }
}

export function canSwapAxes(chart: DatamartChartConfigV1, data: Record<string, unknown>[]): boolean {
  if (!chartHasCartesianAxes(chart.chart_type)) return false
  if (!data.length) return false
  const newCategory = chart.value_column
  const newValue = chart.category_column
  if (newCategory === newValue) return false
  return isCategoryColumn(data, newCategory) && isMostlyNumeric(data, newValue)
}

export function swapChartAxes(chart: DatamartChartConfigV1): DatamartChartConfigV1 {
  const next: DatamartChartConfigV1 = {
    ...chart,
    category_column: chart.value_column,
    value_column: chart.category_column,
    sort_order: 'original',
  }
  const title = chart.title?.trim()
  if (title) {
    const sep = ' by '
    const idx = title.toLowerCase().lastIndexOf(sep)
    if (idx > 0) {
      const left = title.slice(0, idx).trim()
      const right = title.slice(idx + sep.length).trim()
      next.title = `${right} by ${left}`
    }
  }
  return next
}

export function sortChartRecords(
  data: Record<string, unknown>[],
  chart: DatamartChartConfigV1,
): Record<string, unknown>[] {
  const order: DatamartChartSortOrder = chart.sort_order ?? 'original'
  if (order === 'original' || !data.length) return data

  const cat = chart.category_column
  const val = chart.value_column
  const copy = [...data]

  const cmpCat = (a: Record<string, unknown>, b: Record<string, unknown>) =>
    String(a[cat] ?? '').localeCompare(String(b[cat] ?? ''), undefined, { numeric: true })

  const cmpVal = (a: Record<string, unknown>, b: Record<string, unknown>) =>
    (toNum(a[val]) ?? 0) - (toNum(b[val]) ?? 0)

  switch (order) {
    case 'category_asc':
      copy.sort(cmpCat)
      break
    case 'category_desc':
      copy.sort((a, b) => cmpCat(b, a))
      break
    case 'value_asc':
      copy.sort(cmpVal)
      break
    case 'value_desc':
      copy.sort((a, b) => cmpVal(b, a))
      break
    default:
      break
  }
  return copy
}

export const SORT_ORDER_OPTIONS: Array<{ id: DatamartChartSortOrder; label: string }> = [
  { id: 'original', label: 'Original order' },
  { id: 'value_desc', label: 'Value high → low' },
  { id: 'value_asc', label: 'Value low → high' },
  { id: 'category_asc', label: 'Category A → Z' },
  { id: 'category_desc', label: 'Category Z → A' },
]
