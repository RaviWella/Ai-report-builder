/**
 * Heuristic chart suggestions from tabular result + post_process_config.
 * Deterministic (no LLM): maps real columns/rows to chart bindings the user can apply in one click.
 */
import { v4 as uuidv4 } from 'uuid'
import type { DatamartChartConfigV1, DatamartChartDataSource, DatamartChartType } from './chartConfig'
import { isDatamartChartConfigV1 } from './chartConfig'
import { chartBindingKey } from './chartTypeAlternatives'
import {
  buildAggregationMetricLabels,
  lastAppendStep,
  splitAppendSummaryFromFinal,
} from '../components/datamartResultSplit'

export type ChartRowScope = 'all' | 'sql_detail_only' | 'append_summaries_only'

export interface ChartSuggestionInput {
  result_block_id: string | null
  dataset_label: string
  columns: string[]
  rows: unknown[][]
  raw_columns?: string[] | null
  raw_rows?: unknown[][] | null
  post_process_config?: Array<Record<string, unknown>> | null
}

export interface ChartSuggestion {
  id: string
  /** Short chip label */
  label: string
  /** Tooltip / helper text */
  tooltip: string
  chart_type: DatamartChartType
  category_column: string
  value_column: string
  data_source: DatamartChartDataSource
  result_block_id: string | null
  row_scope: ChartRowScope
  title: string
  /** 0–100 ranking */
  score: number
}

const CATEGORY_HINTS = [
  'company', 'branch', 'department', 'team', 'group', 'name', 'title', 'role',
  'location', 'region', 'country', 'status', 'type', 'category', 'month', 'year',
]

const VALUE_HINTS = [
  'count', 'total', 'sum', 'amount', 'salary', 'pay', 'basic', 'gross', 'net',
  'avg', 'average', 'revenue', 'cost', 'hours', 'days', 'percent', 'pct', 'rate',
]

function colIndex(columns: string[], name: string): number {
  const i = columns.indexOf(name)
  if (i >= 0) return i
  const low = name.toLowerCase()
  return columns.findIndex((c) => c.toLowerCase() === low)
}

function toNum(v: unknown): number | null {
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
    if (toNum(v) !== null) numeric++
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

function pickChartType(categoryCardinality: number, rowCount: number): DatamartChartType {
  if (categoryCardinality <= 8 && rowCount <= 12) return 'pie'
  if (categoryCardinality > 14) return 'bar'
  return 'column'
}

/** Canonical block id: null/empty = primary scenario. */
export function normalizeResultBlockId(id: string | null | undefined): string | null {
  if (id == null) return null
  const t = String(id).trim()
  return t.length > 0 ? t : null
}

export function panelIdToResultBlockId(panelId: string): string | null {
  return panelId === 'primary' ? null : panelId
}

function suggestionKey(s: Pick<ChartSuggestion, 'result_block_id' | 'category_column' | 'value_column' | 'row_scope' | 'chart_type'>): string {
  return [
    normalizeResultBlockId(s.result_block_id) ?? 'primary',
    s.row_scope,
    s.chart_type,
    s.category_column,
    s.value_column,
  ].join('|')
}

function resolveLabelColumn(step: Record<string, unknown> | null, columns: string[]): string | undefined {
  const raw = step?.label_column
  if (typeof raw !== 'string' || !raw.trim()) return undefined
  const i = colIndex(columns, raw.trim())
  return i >= 0 ? columns[i] : undefined
}

function primaryAggValueColumn(
  step: Record<string, unknown> | null,
  columns: string[],
): string | undefined {
  const aggs = step?.aggregations
  if (!aggs || typeof aggs !== 'object' || Array.isArray(aggs)) return undefined
  const keys = Object.keys(aggs as Record<string, unknown>)
  if (!keys.length) return undefined
  const col = colIndex(columns, keys[0])
  return col >= 0 ? columns[col] : undefined
}

function suggestionsFromSummaries(
  input: ChartSuggestionInput,
  summaryRows: unknown[][],
  step: Record<string, unknown>,
): ChartSuggestion[] {
  const { columns, result_block_id, dataset_label } = input
  const labelCol = resolveLabelColumn(step, columns)
  const valueCol = primaryAggValueColumn(step, columns)
  if (!labelCol || !valueCol || labelCol === valueCol) return []

  const metricLabels = buildAggregationMetricLabels(step, columns)
  const valueLabel = metricLabels.get(valueCol) ?? 'Value'
  const n = summaryRows.length
  const chartType = pickChartType(n, n)
  const typeLabel = chartType === 'pie' ? 'Pie' : chartType === 'bar' ? 'Bar' : 'Column'

  return [{
    id: uuidv4(),
    label: `${typeLabel}: ${valueLabel} by group`,
    tooltip:
      `Uses ${n} post-process summary row${n === 1 ? '' : 's'} from "${dataset_label}". ` +
      `Category: ${labelCol}. Values: ${valueCol} (${valueLabel}). ` +
      'Best match for per-company / per-group totals under your table.',
    chart_type: chartType,
    category_column: labelCol,
    value_column: valueCol,
    data_source: 'final',
    result_block_id,
    row_scope: 'append_summaries_only',
    title: `${valueLabel} by group`,
    score: 95,
  }]
}

function suggestionsFromDetailGrid(
  input: ChartSuggestionInput,
  detailRows: unknown[][],
): ChartSuggestion[] {
  const { columns, result_block_id, dataset_label } = input
  if (detailRows.length < 2 || columns.length < 2) return []

  const numericCols = columns.filter((_, i) => isMostlyNumeric(detailRows, i))
  const textCols = columns.filter((c, i) => !numericCols.includes(c) && distinctCount(detailRows, i) > 1)

  if (!numericCols.length || !textCols.length) return []

  const out: ChartSuggestion[] = []

  const rankedPairs: Array<{ cat: string; val: string; score: number }> = []
  for (const cat of textCols) {
    const catIdx = colIndex(columns, cat)
    const card = distinctCount(detailRows, catIdx)
    if (card < 2 || card > 40) continue
    for (const val of numericCols) {
      if (cat === val) continue
      let score = nameScore(cat, CATEGORY_HINTS) + nameScore(val, VALUE_HINTS)
      if (card <= 12) score += 4
      if (detailRows.length >= 5) score += 2
      rankedPairs.push({ cat, val, score })
    }
  }

  rankedPairs.sort((a, b) => b.score - a.score)

  const seen = new Set<string>()
  for (const { cat, val, score } of rankedPairs.slice(0, 6)) {
    const catIdx = colIndex(columns, cat)
    const card = distinctCount(detailRows, catIdx)
    const chartType = pickChartType(card, detailRows.length)
    const typeLabel = chartType === 'pie' ? 'Pie' : chartType === 'bar' ? 'Bar' : 'Column'
    const key = `${cat}|${val}|detail`
    if (seen.has(key)) continue
    seen.add(key)

    out.push({
      id: uuidv4(),
      label: `${typeLabel}: ${val} by ${cat}`,
      tooltip:
        `Uses ${detailRows.length} detail rows from "${dataset_label}". ` +
        `Category axis: ${cat} (${card} distinct values). Values: ${val}.`,
      chart_type: chartType,
      category_column: cat,
      value_column: val,
      data_source: 'final',
      result_block_id,
      row_scope: 'sql_detail_only',
      title: `${val} by ${cat}`,
      score: Math.min(88, score + 40),
    })
    if (out.length >= 2) break
  }

  return out
}

function suggestionsFromRawSql(input: ChartSuggestionInput): ChartSuggestion[] {
  const rawCols = input.raw_columns
  const rawRows = input.raw_rows
  if (!rawCols?.length || !rawRows?.length) return []
  return suggestionsFromDetailGrid(
    { ...input, columns: rawCols, rows: rawRows },
    rawRows,
  ).map((s) => ({
    ...s,
    data_source: 'sql_raw' as const,
    row_scope: 'all' as ChartRowScope,
    score: s.score - 15,
    tooltip: s.tooltip.replace('detail rows', 'raw SQL rows (before post-processing)'),
  }))
}

/**
 * Build ranked chart suggestions for one dataset (primary or extra block).
 */
export function buildChartSuggestionsForDataset(input: ChartSuggestionInput): ChartSuggestion[] {
  const { columns, rows, post_process_config } = input
  if (!columns.length || !rows.length) return []

  const step = lastAppendStep(post_process_config ?? null)
  const split = splitAppendSummaryFromFinal(rows, input.raw_rows ?? null, post_process_config ?? null)

  const candidates: ChartSuggestion[] = []

  if (split && split.summaryRows.length > 0 && step) {
    candidates.push(...suggestionsFromSummaries(input, split.summaryRows, step))
  }

  const detailRows = split?.detailRows ?? rows
  candidates.push(...suggestionsFromDetailGrid(input, detailRows))
  candidates.push(...suggestionsFromRawSql(input))

  candidates.sort((a, b) => b.score - a.score)

  const deduped: ChartSuggestion[] = []
  const seen = new Set<string>()
  for (const s of candidates) {
    const k = suggestionKey(s)
    if (seen.has(k)) continue
    seen.add(k)
    deduped.push(s)
    if (deduped.length >= 4) break
  }

  const blockId = normalizeResultBlockId(input.result_block_id)
  return deduped.map((s) => ({ ...s, result_block_id: blockId }))
}

const MAX_SUGGESTIONS_PER_SCENARIO = 4

function existingBindingsForScenario(
  existingCharts: unknown[] | null | undefined,
  resultBlockId: string | null,
): Set<string> {
  const want = normalizeResultBlockId(resultBlockId)
  const bindings = new Set<string>()
  for (const c of existingCharts ?? []) {
    if (!isDatamartChartConfigV1(c)) continue
    if (normalizeResultBlockId(c.result_block_id) !== want) continue
    bindings.add(chartBindingKey(c))
  }
  return bindings
}

function pickSuggestionsForDataset(
  ds: ChartSuggestionInput,
  existingCharts: unknown[] | null | undefined,
): ChartSuggestion[] {
  const blockId = normalizeResultBlockId(ds.result_block_id)
  const existingBindings = existingBindingsForScenario(existingCharts, blockId)
  const candidates = buildChartSuggestionsForDataset(ds)
  candidates.sort((a, b) => b.score - a.score)

  const seen = new Set<string>()
  const out: ChartSuggestion[] = []
  for (const s of candidates) {
    const k = suggestionKey(s)
    if (seen.has(k)) continue
    const draft = suggestionToChartConfig(s)
    if (existingBindings.has(chartBindingKey(draft))) continue
    seen.add(k)
    out.push(s)
    if (out.length >= MAX_SUGGESTIONS_PER_SCENARIO) break
  }
  return out
}

/** Suggestions for one scenario only — built from that scenario's dataset, never mixed. */
export function buildChartSuggestionsForPanel(
  panelId: string,
  datasets: ChartSuggestionInput[],
  existingCharts: unknown[] | null | undefined,
): ChartSuggestion[] {
  const want = panelIdToResultBlockId(panelId)
  const ds = datasets.find((d) => normalizeResultBlockId(d.result_block_id) === want)
  if (!ds) return []
  return pickSuggestionsForDataset(ds, existingCharts)
}

/** Keep suggestions that belong to one report scenario panel (`primary` or extra block id). */
export function chartSuggestionsForPanel(
  suggestions: ChartSuggestion[],
  panelId: string,
): ChartSuggestion[] {
  const want = panelIdToResultBlockId(panelId)
  return suggestions.filter((s) => normalizeResultBlockId(s.result_block_id) === want)
}

export function suggestionBelongsToPanel(s: ChartSuggestion, panelId: string): boolean {
  return normalizeResultBlockId(s.result_block_id) === panelIdToResultBlockId(panelId)
}

/**
 * Build chart suggestions for every scenario dataset independently so one
 * high-scoring scenario does not crowd out another.
 */
export function buildAllChartSuggestions(
  datasets: ChartSuggestionInput[],
  existingCharts: unknown[] | null | undefined,
): ChartSuggestion[] {
  const all: ChartSuggestion[] = []
  for (const ds of datasets) {
    all.push(...pickSuggestionsForDataset(ds, existingCharts))
  }
  return all
}

export function suggestionToChartConfig(s: ChartSuggestion): DatamartChartConfigV1 {
  return {
    schema_version: 1,
    id: uuidv4(),
    chart_type: s.chart_type,
    title: s.title,
    data_source: s.data_source,
    result_block_id: s.result_block_id ?? undefined,
    row_scope: s.row_scope,
    category_column: s.category_column,
    value_column: s.value_column,
    show_legend: true,
  }
}

/** Filter rows for chart rendering per optional row_scope + raw snapshot. */
export function filterRowsForChartScope(
  _finalColumns: string[],
  finalRows: unknown[][],
  rawRows: unknown[][] | null | undefined,
  rowScope: ChartRowScope | undefined | null,
): unknown[][] {
  const scope = rowScope ?? 'all'
  if (scope === 'all') return finalRows

  const n = rawRows?.length ?? 0
  if (n <= 0 || finalRows.length <= n) {
    if (scope === 'append_summaries_only') {
      return finalRows.filter((row) =>
        row.some((v) => v !== null && v !== undefined && v !== ''),
      )
    }
    return finalRows
  }

  if (scope === 'sql_detail_only') return finalRows.slice(0, n)
  if (scope === 'append_summaries_only') return finalRows.slice(n)
  return finalRows
}
