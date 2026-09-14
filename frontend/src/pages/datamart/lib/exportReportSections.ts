/**
 * Build export sections from layout widgets (multi-scenario).
 */
import { chartImageFilename, type ChartExportImage } from './captureChartImages'
import { splitAppendSummaryFromFinal } from '../components/datamartResultSplit'
import { postProcessForScenario, type ExportScenarioSlice } from './exportReportContext'
import type { ExportReportInput, PreparedReportExport } from './exportReportModel'
import { chartSeriesForPanel } from './exportReportModel'

function tableRowsForExport(slice: ExportScenarioSlice): unknown[][] {
  const split = splitAppendSummaryFromFinal(
    slice.tableRows,
    slice.rawRows ?? null,
    slice.postProcessConfig,
  )
  return split?.detailRows ?? slice.tableRows
}
function escapeCsv(v: unknown): string {
  if (v === null || v === undefined) return ''
  const s = String(v)
  if (/[",\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`
  return s
}

function tableCsvSection(
  title: string,
  columns: string[],
  rows: unknown[][],
): string[] {
  if (!columns.length) return []
  return [
    '',
    `# ${title}`,
    columns.map(escapeCsv).join(','),
    ...rows.map((row) => columns.map((_, i) => escapeCsv(row[i])).join(',')),
  ]
}

function transformationsCsv(
  title: string,
  pp: ReturnType<typeof postProcessForScenario>,
): string[] {
  if (!pp) return []
  return [
    '',
    `# ${title}`,
    'Step,Description',
    ...pp.humanSteps.map((desc, i) => `${i + 1},${escapeCsv(desc.replace(/^\d+\.\s*/, ''))}`),
    '',
    'Step,Parameter,Value',
    ...pp.configRows.map((r) =>
      [r.step, escapeCsv(r.parameter), escapeCsv(r.value)].join(','),
    ),
  ]
}

export function buildPlannedCsvSections(
  prepared: PreparedReportExport,
  options?: { chartImages?: ChartExportImage[] },
): string[] {
  const { input } = prepared
  const widgets = input.exportWidgets ?? []
  const scenarios = input.scenarios ?? []
  const imagesByChartId = new Map(
    (options?.chartImages ?? []).map((img) => [img.chartId, img]),
  )

  if (!widgets.length) return []

  const lines: string[] = []

  for (const w of widgets) {
    const slice = scenarios.find((s) => s.panelId === w.panel_id)
    const scenarioLabel = slice?.label ?? w.panel_id

    switch (w.kind) {
      case 'summary':
        if (input.narrative?.trim()) {
          lines.push('', '# Summary', escapeCsv(input.narrative.trim()))
        }
        break
      case 'sql':
        if (slice?.sql?.trim()) {
          lines.push('', `# SQL — ${scenarioLabel}`, escapeCsv(slice.sql.trim()))
        }
        break
      case 'transformations':
        lines.push(
          ...transformationsCsv(
            `Transformations — ${scenarioLabel}`,
            slice ? postProcessForScenario(slice) : null,
          ),
        )
        break
      case 'table': {
        if (!slice?.tableColumns.length) break
        lines.push(
          ...tableCsvSection(
            `Results — ${scenarioLabel}`,
            slice.tableColumns,
            tableRowsForExport(slice),
          ),
        )
        break
      }
      case 'charts': {
        const series = chartSeriesForPanel(
          input,
          w.panel_id,
          prepared.chartSeries,
        )
        for (const { chart, title } of series) {
          const img = imagesByChartId.get(chart.id)
          if (img) {
            lines.push(
              '',
              `# Chart — ${scenarioLabel}: ${title}`,
              `Image,charts/${chartImageFilename(img)}`,
            )
          } else {
            lines.push(
              '',
              `# Chart — ${scenarioLabel}: ${title}`,
              `# Type: ${chart.chart_type}`,
            )
          }
        }
        break
      }
      default:
        break
    }
  }

  return lines
}

export function buildLegacyCsvSections(prepared: PreparedReportExport): string[] {
  const { input } = prepared
  if (!input.tableColumns.length) return []
  const primary = input.scenarios?.find((s) => s.panelId === 'primary')
  const rows = primary
    ? tableRowsForExport(primary)
    : input.tableRows
  return tableCsvSection('Results', input.tableColumns, rows)
}

export function usesPlannedExport(input: ExportReportInput): boolean {
  return (
    (input.exportWidgets?.length ?? 0) > 0 &&
    (input.scenarios?.length ?? 0) > 0
  )
}
