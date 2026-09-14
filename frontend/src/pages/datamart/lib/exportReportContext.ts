/**
 * Full report payload for export composer + CSV/PDF (all scenarios).
 */
import { isDatamartChartConfigV1 } from '../charts/chartConfig'
import { buildGroupedResultMetricsView } from './groupedResultMetrics'
import type { ChartExportDataset, ExportReportInput } from './exportReportModel'
import {
  buildDefaultReportLayout,
  chartsForPanel,
  type DatamartReportLayoutV1,
  type ReportLayoutWidget,
  type ReportPanelId,
  type ScenarioDescriptor,
} from './reportLayout'
import { buildPostProcessExportBlock } from './formatPostProcessExport'

export interface ExportScenarioSlice {
  panelId: ReportPanelId
  label: string
  sql: string | null
  postProcessConfig: Array<Record<string, unknown>> | null
  tableColumns: string[]
  tableRows: unknown[][]
  rawColumns?: string[] | null
  rawRows?: unknown[][] | null
}

/** `quick` = table + user charts only; `composer` = respects layout include_in_export toggles. */
export type ExportWidgetScope = 'quick' | 'composer'

export interface BuildExportReportInputParams {
  title?: string
  narrative?: string
  primarySql?: string | null
  scenarios: ExportScenarioSlice[]
  charts: unknown[]
  layout: DatamartReportLayoutV1
  filenameBase?: string
  widgetScope?: ExportWidgetScope
}

export function scenarioDataset(slice: ExportScenarioSlice): ChartExportDataset {
  return {
    finalColumns: slice.tableColumns,
    finalRows: slice.tableRows,
    rawColumns: slice.rawColumns,
    rawRows: slice.rawRows,
  }
}

/** Widgets included in export, in canvas order (top-to-bottom, left-to-right). */
export function exportWidgetsInOrder(layout: DatamartReportLayoutV1): ReportLayoutWidget[] {
  return [...layout.widgets]
    .filter((w) => w.include_in_export)
    .sort((a, b) => a.y - b.y || a.x - b.x || a.id.localeCompare(b.id))
}

const QUICK_EXPORT_KINDS = new Set<ReportLayoutWidget['kind']>(['table', 'charts'])

/** Quick CSV/PDF: result tables and user-added charts only (no SQL, narrative, metrics). */
export function exportWidgetsForQuickExport(
  layout: DatamartReportLayoutV1,
  charts: unknown[] = [],
): ReportLayoutWidget[] {
  return exportWidgetsInOrder(layout).filter((w) => {
    if (!QUICK_EXPORT_KINDS.has(w.kind)) return false
    if (w.kind === 'charts') {
      return chartsForPanel(charts, w.panel_id).length > 0
    }
    return true
  })
}

export function buildExportReportInput(
  params: BuildExportReportInputParams,
): ExportReportInput | null {
  const { scenarios, layout } = params
  const charts = params.charts.filter(isDatamartChartConfigV1)
  const primary = scenarios.find((s) => s.panelId === 'primary') ?? scenarios[0]
  if (!primary) return null

  const blockDatasets: Record<string, ChartExportDataset> = {}
  for (const s of scenarios) {
    if (s.panelId !== 'primary' && s.tableColumns.length > 0) {
      blockDatasets[s.panelId] = scenarioDataset(s)
    }
  }

  const widgetScope = params.widgetScope ?? 'quick'
  const pickExportWidgets =
    widgetScope === 'composer'
      ? () => exportWidgetsInOrder(layout)
      : () => exportWidgetsForQuickExport(layout, charts)

  let exportWidgets = pickExportWidgets()
  if (!exportWidgets.length && scenarios.length > 0) {
    const scenarioDescriptors: ScenarioDescriptor[] = scenarios.map((s) => ({
      panelId: s.panelId,
      label: s.label,
      isPrimary: s.panelId === 'primary',
    }))
    const fallbackLayout = buildDefaultReportLayout(
      scenarioDescriptors,
      !!params.narrative?.trim(),
    )
    exportWidgets =
      widgetScope === 'composer'
        ? exportWidgetsInOrder(fallbackLayout)
        : exportWidgetsForQuickExport(fallbackLayout, charts)
  }

  const hasWidgetContent = exportWidgets.some((w) => {
    if (w.kind === 'summary') return !!params.narrative?.trim()
    if (w.kind === 'charts') {
      return chartsForPanel(charts, w.panel_id).length > 0
    }
    const slice = scenarios.find((s) => s.panelId === w.panel_id)
    if (!slice) return false
    if (w.kind === 'table') return slice.tableColumns.length > 0
    if (w.kind === 'sql') return !!slice.sql?.trim()
    if (w.kind === 'transformations') {
      return (slice.postProcessConfig?.length ?? 0) > 0
    }
    return false
  })

  const hasAnyTable = scenarios.some((s) => s.tableColumns.length > 0)
  const hasCharts = charts.length > 0
  const hasPp = scenarios.some((s) => (s.postProcessConfig?.length ?? 0) > 0)

  if (!hasWidgetContent && !hasAnyTable && !hasCharts && !hasPp) return null

  return {
    title: params.title?.trim() || 'Datamart report',
    narrative: params.narrative,
    sql: params.primarySql ?? primary.sql,
    postProcessConfig: primary.postProcessConfig,
    tableColumns: primary.tableColumns,
    tableRows: primary.tableRows,
    rawRows: primary.rawRows ?? null,
    charts,
    primaryDataset: scenarioDataset(primary),
    blockDatasets: blockDatasets,
    scenarios,
    exportWidgets,
    layout,
    filenameBase: params.filenameBase ?? 'datamart-report',
  }
}

export function widgetLabel(
  w: ReportLayoutWidget,
  scenarios: ScenarioDescriptor[],
): string {
  const scenario =
    w.kind === 'summary'
      ? 'Report'
      : scenarios.find((s) => s.panelId === w.panel_id)?.label ?? w.panel_id
  const kindLabels: Record<ReportLayoutWidget['kind'], string> = {
    summary: 'Summary',
    sql: 'SQL query',
    transformations: 'Transformations',
    table: 'Results table',
    charts: 'Charts',
  }
  return `${scenario} · ${kindLabels[w.kind]}`
}

export function groupedMetricsForScenario(slice: ExportScenarioSlice) {
  return buildGroupedResultMetricsView(
    slice.tableColumns,
    slice.tableRows,
    slice.postProcessConfig,
  )
}

export function postProcessForScenario(slice: ExportScenarioSlice) {
  return buildPostProcessExportBlock(
    slice.postProcessConfig,
    slice.tableColumns,
    slice.tableRows,
    slice.rawRows ?? null,
  )
}
