/**
 * Export datamart report as sectioned CSV (transformations, results, summaries, charts).
 * When charts are present, downloads a ZIP with CSV + PNG images in charts/.
 */
import JSZip from 'jszip'
import {
  captureChartImagesForExport,
  chartImageFilename,
  type ChartExportImage,
} from './captureChartImages'
import type { ExportReportInput, PreparedReportExport } from './exportReportModel'
import { prepareReportExport } from './exportReportModel'
import {
  buildLegacyCsvSections,
  buildPlannedCsvSections,
  usesPlannedExport,
} from './exportReportSections'

function escapeCsv(v: unknown): string {
  if (v === null || v === undefined) return ''
  const s = String(v)
  if (/[",\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`
  return s
}

function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function buildMetadataSection(prepared: PreparedReportExport): string[] {
  const lines: string[] = ['# Datamart Report Export', `# Exported at,${escapeCsv(new Date().toISOString())}`]
  if (prepared.input.title?.trim()) {
    lines.push(`# Report,${escapeCsv(prepared.input.title.trim())}`)
  }
  return lines
}

function buildResultsSection(prepared: PreparedReportExport): string[] {
  const legacy = buildLegacyCsvSections(prepared)
  return legacy.length ? ['', ...legacy] : []
}

function buildChartsSection(
  prepared: PreparedReportExport,
  chartImages?: ChartExportImage[],
): string[] {
  if (!prepared.chartSeries.length) return []

  if (chartImages?.length) {
    return [
      '',
      '# Charts',
      '# Chart visuals are PNG files in the charts/ folder of this export.',
      'Chart title,Image file',
      ...chartImages.map((img) => {
        const file = `charts/${chartImageFilename(img)}`
        return [escapeCsv(img.title), escapeCsv(file)].join(',')
      }),
    ]
  }

  return prepared.chartSeries.flatMap(({ chart, title }) => [
    '',
    `# Chart: ${title}`,
    `# Type: ${chart.chart_type} · Category: ${chart.category_column} · Value: ${chart.value_column}`,
    '# (Chart image could not be captured — open the report in Datamart to view the chart.)',
  ])
}

export function buildReportCsvContent(
  input: ExportReportInput,
  options?: { chartImages?: ChartExportImage[] },
): string {
  const prepared = prepareReportExport(input)
  const planned = usesPlannedExport(input)
  const parts = [
    ...buildMetadataSection(prepared),
    ...(planned
      ? buildPlannedCsvSections(prepared, options)
      : [
          ...buildResultsSection(prepared),
          ...buildChartsSection(prepared, options?.chartImages),
        ]),
  ]
  return parts.join('\r\n').trim() + '\r\n'
}

export async function exportReportToCsv(input: ExportReportInput): Promise<void> {
  const prepared = prepareReportExport(input)
  if (!prepared.hasExportableContent) return

  const base = input.filenameBase ?? 'datamart-report'
  const chartImages =
    prepared.chartSeries.length > 0 ? await captureChartImagesForExport(input) : []

  if (chartImages.length > 0) {
    const zip = new JSZip()
    zip.file(`${base}.csv`, buildReportCsvContent(input, { chartImages }))
    const folder = zip.folder('charts')
    if (folder) {
      for (const img of chartImages) {
        const b64 = img.pngDataUrl.replace(/^data:image\/\w+;base64,/, '')
        folder.file(chartImageFilename(img), b64, { base64: true })
      }
    }
    const blob = await zip.generateAsync({ type: 'blob' })
    downloadBlob(blob, `${base}.zip`)
    return
  }

  const content = buildReportCsvContent(input)
  downloadBlob(new Blob([content], { type: 'text/csv;charset=utf-8' }), `${base}.csv`)
}
