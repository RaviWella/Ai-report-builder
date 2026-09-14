/**
 * Shared export payload for datamart report CSV / PDF.
 */
import type { DatamartChartConfigV1 } from '../charts/chartConfig'
import { isDatamartChartConfigV1 } from '../charts/chartConfig'
import type { ExportScenarioSlice } from './exportReportContext'
import { chartsForPanel } from './reportLayout'
import type { DatamartReportLayoutV1, ReportLayoutWidget } from './reportLayout'
import { chartSeriesRecords, resolveChartDataset } from './chartDataset'
import {
  buildPostProcessExportBlock,
  type PostProcessExportBlock,
} from './formatPostProcessExport'

export interface ChartExportDataset {
  finalColumns: string[]
  finalRows: unknown[][]
  rawColumns?: string[] | null
  rawRows?: unknown[][] | null
}

export interface ChartExportSeries {
  chart: DatamartChartConfigV1
  title: string
  rows: Array<{ category: string; value: number }>
}

export interface ExportReportInput {
  title?: string
  narrative?: string
  sql?: string | null
  postProcessConfig?: Array<Record<string, unknown>> | null
  tableColumns: string[]
  tableRows: unknown[][]
  rawRows?: unknown[][] | null
  charts: unknown[]
  primaryDataset: ChartExportDataset
  blockDatasets?: Record<string, ChartExportDataset>
  /** All scenarios (primary + extras) with full table data. */
  scenarios?: ExportScenarioSlice[]
  /** Widgets to export in layout order; when set, drives multi-section export. */
  exportWidgets?: ReportLayoutWidget[]
  layout?: DatamartReportLayoutV1
  filenameBase?: string
}

export interface PreparedReportExport {
  input: ExportReportInput
  postProcess: PostProcessExportBlock | null
  chartSeries: ChartExportSeries[]
  hasExportableContent: boolean
}

export function prepareReportExport(input: ExportReportInput): PreparedReportExport {
  const postProcess = buildPostProcessExportBlock(
    input.postProcessConfig,
    input.tableColumns,
    input.tableRows,
    input.rawRows ?? null,
  )

  const charts = input.charts.filter(isDatamartChartConfigV1)
  const chartSeries: ChartExportSeries[] = charts.map((chart) => {
    const blockId = chart.result_block_id ?? null
    const ds =
      blockId && input.blockDatasets?.[blockId]
        ? input.blockDatasets[blockId]!
        : input.primaryDataset
    const records = resolveChartDataset(
      chart,
      ds.finalColumns,
      ds.finalRows,
      ds.rawColumns,
      ds.rawRows,
    )
    return {
      chart,
      title: chart.title?.trim() || `${chart.chart_type} chart`,
      rows: chartSeriesRecords(records, chart),
    }
  })

  const multiScenario = (input.scenarios?.length ?? 0) > 1
  const hasScenarioTables =
    multiScenario &&
    (input.scenarios?.some((s) => s.tableColumns.length > 0) ?? false)
  const hasWidgetPlan = (input.exportWidgets?.length ?? 0) > 0

  const hasExportableContent =
    input.tableColumns.length > 0 ||
    hasScenarioTables ||
    hasWidgetPlan ||
    chartSeries.length > 0

  return { input, postProcess, chartSeries, hasExportableContent }
}

/** Chart series for widgets bound to a specific scenario panel. */
export function chartSeriesForPanel(
  input: ExportReportInput,
  panelId: string,
  allSeries: ChartExportSeries[],
): ChartExportSeries[] {
  const panelCharts = chartsForPanel(
    input.charts.filter(isDatamartChartConfigV1),
    panelId as 'primary' | string,
  )
  const ids = new Set(
    panelCharts
      .filter(isDatamartChartConfigV1)
      .map((c) => c.id),
  )
  return allSeries.filter((s) => ids.has(s.chart.id))
}
