/**
 * Infer category vs value columns from tabular result data for custom chart binding.
 */
import type { DatamartChartType } from '../charts/chartConfig'
import { splitAppendSummaryFromFinal } from '../components/datamartResultSplit'
import type { DatamartChartRowScope } from '../charts/chartConfig'

export interface ColumnAnalysis {
  name: string
  isNumeric: boolean
  distinctCount: number
  isCategoryCandidate: boolean
  isValueCandidate: boolean
}

export interface DatasetColumnRoles {
  categoryColumns: string[]
  valueColumns: string[]
  analyses: ColumnAnalysis[]
}

export interface AxisFieldLabels {
  categoryLabel: string
  categoryHint: string
  valueLabel: string
  valueHint: string
}

const CATEGORY_HINTS = [
  'company', 'branch', 'department', 'team', 'group', 'name', 'title', 'role',
  'location', 'region', 'country', 'status', 'type', 'category', 'month', 'year',
  'employee', 'id',
]

const VALUE_HINTS = [
  'count', 'total', 'sum', 'amount', 'salary', 'pay', 'basic', 'gross', 'net',
  'avg', 'average', 'revenue', 'cost', 'hours', 'days', 'leave', 'percent', 'pct', 'rate',
]

function colIndex(columns: string[], name: string): number {
  const i = columns.indexOf(name)
  if (i >= 0) return i
  const low = name.toLowerCase()
  return columns.findIndex((c) => c.toLowerCase() === low)
}

export function toChartNumber(v: unknown): number | null {
  if (v === null || v === undefined || v === '') return null
  if (typeof v === 'number' && Number.isFinite(v)) return v
  const n = Number(String(v).replace(/,/g, ''))
  return Number.isFinite(n) ? n : null
}

function isMostlyNumeric(rows: unknown[][], colIdx: number, sample = 40): boolean {
  if (colIdx < 0) return false
  let numeric = 0
  let seen = 0
  for (let r = 0; r < Math.min(rows.length, sample); r++) {
    const v = rows[r]?.[colIdx]
    if (v === null || v === undefined || v === '') continue
    seen++
    if (toChartNumber(v) !== null) numeric++
  }
  return seen > 0 && numeric / seen >= 0.85
}

function distinctCount(rows: unknown[][], colIdx: number, cap = 500): number {
  if (colIdx < 0) return 0
  const s = new Set<string>()
  for (let r = 0; r < Math.min(rows.length, cap); r++) {
    const v = rows[r]?.[colIdx]
    if (v === null || v === undefined || v === '') continue
    s.add(String(v))
  }
  return s.size
}

function nameScore(col: string, hints: string[]): number {
  const low = col.toLowerCase()
  let best = 0
  for (const h of hints) {
    if (low === h) best = Math.max(best, 10)
    else if (low.includes(h)) best = Math.max(best, 6)
  }
  return best
}

function isCategoryColumn(rows: unknown[][], colIdx: number): boolean {
  const card = distinctCount(rows, colIdx)
  if (card < 2 || card > 40) return false
  if (isMostlyNumeric(rows, colIdx) && card > 12) return false
  return true
}

/** Classify columns using a sample of rows from the active dataset. */
export function analyzeDatasetColumns(
  columns: string[],
  rows: unknown[][],
): DatasetColumnRoles {
  if (!columns.length || !rows.length) {
    return { categoryColumns: [], valueColumns: [], analyses: [] }
  }

  const analyses: ColumnAnalysis[] = columns.map((name, i) => {
    const isNumeric = isMostlyNumeric(rows, i)
    const distinct = distinctCount(rows, i)
    const isCategoryCandidate = isCategoryColumn(rows, i)
    const isValueCandidate = isNumeric && distinct >= 1
    return {
      name,
      isNumeric,
      distinctCount: distinct,
      isCategoryCandidate,
      isValueCandidate,
    }
  })

  const categoryColumns = analyses.filter((a) => a.isCategoryCandidate).map((a) => a.name)
  const valueColumns = analyses.filter((a) => a.isValueCandidate).map((a) => a.name)

  // Fallbacks when heuristics are strict
  if (!categoryColumns.length) {
    const textFallback = analyses
      .filter((a) => !a.isNumeric && a.distinctCount >= 2)
      .map((a) => a.name)
    if (textFallback.length) categoryColumns.push(...textFallback)
  }
  if (!valueColumns.length) {
    const numFallback = analyses.filter((a) => a.isNumeric).map((a) => a.name)
    if (numFallback.length) valueColumns.push(...numFallback)
  }

  return { categoryColumns, valueColumns, analyses }
}

export function getAxisFieldLabels(chartType: DatamartChartType): AxisFieldLabels {
  switch (chartType) {
    case 'pie':
      return {
        categoryLabel: 'Slice labels',
        categoryHint: 'Text or date column that names each slice',
        valueLabel: 'Values',
        valueHint: 'Numeric column to size each slice',
      }
    case 'bar':
      return {
        categoryLabel: 'Y-axis — categories',
        categoryHint: 'Labels along the vertical axis (e.g. branch, name)',
        valueLabel: 'X-axis — values',
        valueHint: 'Numeric measure along the horizontal axis',
      }
    case 'line':
      return {
        categoryLabel: 'X-axis — categories',
        categoryHint: 'Labels along the horizontal axis (e.g. month, branch)',
        valueLabel: 'Y-axis — values',
        valueHint: 'Numeric measure along the vertical axis',
      }
    case 'column':
    default:
      return {
        categoryLabel: 'X-axis — categories',
        categoryHint: 'Labels along the horizontal axis (e.g. branch, department)',
        valueLabel: 'Y-axis — values',
        valueHint: 'Numeric measure along the vertical axis',
      }
  }
}

export function pickDefaultAxisColumns(
  roles: DatasetColumnRoles,
  columns: string[],
  rows: unknown[][],
): { categoryColumn: string; valueColumn: string } | null {
  const { categoryColumns, valueColumns } = roles
  if (!categoryColumns.length || !valueColumns.length) return null

  let best: { cat: string; val: string; score: number } | null = null
  for (const cat of categoryColumns) {
    const catIdx = colIndex(columns, cat)
    const card = distinctCount(rows, catIdx)
    for (const val of valueColumns) {
      if (cat === val) continue
      let score = nameScore(cat, CATEGORY_HINTS) + nameScore(val, VALUE_HINTS)
      if (card <= 12) score += 4
      if (rows.length >= 5) score += 2
      if (!best || score > best.score) best = { cat, val, score }
    }
  }
  if (!best) return null
  return { categoryColumn: best.cat, valueColumn: best.val }
}

export function isValidAxisPair(
  categoryColumn: string,
  valueColumn: string,
  roles: DatasetColumnRoles,
): boolean {
  if (!categoryColumn || !valueColumn || categoryColumn === valueColumn) return false
  return (
    roles.categoryColumns.includes(categoryColumn) &&
    roles.valueColumns.includes(valueColumn)
  )
}

export interface RowScopeOption {
  id: DatamartChartRowScope
  label: string
  description: string
}

export function getRowScopeOptions(
  _columns: string[],
  rows: unknown[][],
  rawRows: unknown[][] | null | undefined,
  postProcessConfig: Array<Record<string, unknown>> | null | undefined,
): RowScopeOption[] {
  const split = splitAppendSummaryFromFinal(rows, rawRows ?? null, postProcessConfig ?? null)
  if (!split || split.summaryRows.length === 0) {
    return [{ id: 'all', label: 'All rows', description: 'Use every row in the selected dataset.' }]
  }
  return [
    {
      id: 'all',
      label: 'All rows',
      description: `${rows.length} rows including detail and summary.`,
    },
    {
      id: 'sql_detail_only',
      label: 'Detail rows only',
      description: `${split.detailRows.length} SQL detail rows (excludes appended summaries).`,
    },
    {
      id: 'append_summaries_only',
      label: 'Summary rows only',
      description: `${split.summaryRows.length} post-process summary row${split.summaryRows.length === 1 ? '' : 's'}.`,
    },
  ]
}
