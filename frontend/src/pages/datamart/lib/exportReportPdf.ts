/**
 * Export datamart report as a formatted PDF (jspdf + autotable + chart PNGs).
 */
import { jsPDF } from 'jspdf'
import autoTable from 'jspdf-autotable'
import {
  captureChartImagesForExport,
  type ChartExportImage,
} from './captureChartImages'
import {
  postProcessForScenario,
  type ExportScenarioSlice,
} from './exportReportContext'
import { splitAppendSummaryFromFinal } from '../components/datamartResultSplit'
import type { ExportReportInput, PreparedReportExport } from './exportReportModel'
import { chartSeriesForPanel, prepareReportExport } from './exportReportModel'
import { usesPlannedExport } from './exportReportSections'

const MARGIN = 14
const PAGE_WIDTH = 210
const CONTENT_WIDTH = PAGE_WIDTH - MARGIN * 2
const MAX_CHART_HEIGHT_MM = 95

function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function addHeading(doc: jsPDF, text: string, y: number): number {
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(13)
  doc.setTextColor(15, 118, 110)
  doc.text(text, MARGIN, y)
  doc.setTextColor(30, 41, 59)
  return y + 8
}

function addParagraph(doc: jsPDF, text: string, y: number, fontSize = 10): number {
  doc.setFont('helvetica', 'normal')
  doc.setFontSize(fontSize)
  const lines = doc.splitTextToSize(text, CONTENT_WIDTH) as string[]
  doc.text(lines, MARGIN, y)
  return y + lines.length * (fontSize * 0.45) + 4
}

function tableFromRows(
  columns: string[],
  rows: unknown[][],
): { head: string[][]; body: string[][] } {
  return {
    head: [columns],
    body: rows.map((row) => columns.map((_, i) => {
      const v = row[i]
      if (v === null || v === undefined) return '—'
      return String(v)
    })),
  }
}

function ensureSpace(doc: jsPDF, y: number, needed: number): number {
  if (y + needed > 285) {
    doc.addPage()
    return MARGIN
  }
  return y
}

function addChartImageSection(
  doc: jsPDF,
  y: number,
  title: string,
  caption: string,
  dataUrl: string,
): number {
  const props = doc.getImageProperties(dataUrl)
  let imgWidth = CONTENT_WIDTH
  let imgHeight = (props.height * imgWidth) / props.width
  if (imgHeight > MAX_CHART_HEIGHT_MM) {
    imgHeight = MAX_CHART_HEIGHT_MM
    imgWidth = (props.width * imgHeight) / props.height
  }

  y = ensureSpace(doc, y, imgHeight + 24)
  y = addHeading(doc, `Chart: ${title}`, y)
  y = addParagraph(doc, caption, y, 9)
  const x = MARGIN + (CONTENT_WIDTH - imgWidth) / 2
  doc.addImage(dataUrl, 'PNG', x, y, imgWidth, imgHeight)
  return y + imgHeight + 10
}

function imageByChartId(images: ChartExportImage[]): Map<string, ChartExportImage> {
  return new Map(images.map((img) => [img.chartId, img]))
}

function tableRowsForExport(slice: ExportScenarioSlice): unknown[][] {
  const split = splitAppendSummaryFromFinal(
    slice.tableRows,
    slice.rawRows ?? null,
    slice.postProcessConfig,
  )
  return split?.detailRows ?? slice.tableRows
}

function renderPlannedPdfSections(
  doc: jsPDF,
  y: number,
  prepared: PreparedReportExport,
  imagesById: Map<string, ChartExportImage>,
): number {
  const { input } = prepared
  const widgets = input.exportWidgets ?? []
  const scenarios = input.scenarios ?? []

  for (const w of widgets) {
    const slice = scenarios.find((s) => s.panelId === w.panel_id)
    const label = slice?.label ?? w.panel_id

    switch (w.kind) {
      case 'summary':
        if (input.narrative?.trim()) {
          y = ensureSpace(doc, y, 16)
          y = addHeading(doc, 'Summary', y)
          y = addParagraph(doc, input.narrative.trim(), y)
          y += 4
        }
        break
      case 'sql':
        if (slice?.sql?.trim()) {
          y = ensureSpace(doc, y, 16)
          y = addHeading(doc, `Query — ${label}`, y)
          y = addParagraph(doc, slice.sql.trim(), y, 8)
          y += 4
        }
        break
      case 'transformations': {
        const pp = slice ? postProcessForScenario(slice) : null
        if (!pp) break
        y = ensureSpace(doc, y, 20)
        y = addHeading(doc, `Transformations — ${label}`, y)
        const bullets = pp.humanSteps.map((s) => `• ${s.replace(/^\d+\.\s*/, '')}`)
        y = addParagraph(doc, bullets.join('\n'), y, 10)
        autoTable(doc, {
          startY: y,
          head: [['Step', 'Parameter', 'Value']],
          body: pp.configRows.map((r) => [
            String(r.step),
            r.parameter,
            r.value.length > 80 ? `${r.value.slice(0, 77)}…` : r.value,
          ]),
          margin: { left: MARGIN, right: MARGIN },
          styles: { fontSize: 8, cellPadding: 2 },
          headStyles: { fillColor: [109, 40, 217], textColor: 255 },
          theme: 'grid',
        })
        y = (doc as jsPDF & { lastAutoTable: { finalY: number } }).lastAutoTable.finalY + 10
        break
      }
      case 'table': {
        if (!slice?.tableColumns.length) break
        y = ensureSpace(doc, y, 20)
        y = addHeading(doc, `Results — ${label}`, y)
        const { head, body } = tableFromRows(
          slice.tableColumns,
          tableRowsForExport(slice),
        )
        autoTable(doc, {
          startY: y,
          head,
          body,
          margin: { left: MARGIN, right: MARGIN },
          styles: { fontSize: 7, cellPadding: 2, overflow: 'linebreak' },
          headStyles: { fillColor: [13, 148, 136], textColor: 255 },
          theme: 'striped',
        })
        y = (doc as jsPDF & { lastAutoTable: { finalY: number } }).lastAutoTable.finalY + 10
        break
      }
      case 'charts': {
        const series = chartSeriesForPanel(input, w.panel_id, prepared.chartSeries)
        for (const s of series) {
          const img = imagesById.get(s.chart.id)
          const caption = `Type: ${s.chart.chart_type} · ${s.chart.category_column} · ${s.chart.value_column}`
          if (img) {
            y = addChartImageSection(doc, y, `${label}: ${s.title}`, caption, img.pngDataUrl)
          } else {
            y = ensureSpace(doc, y, 16)
            y = addHeading(doc, `Chart — ${label}: ${s.title}`, y)
            y = addParagraph(doc, `${caption}\n(Image unavailable.)`, y, 9)
          }
        }
        break
      }
      default:
        break
    }
  }
  return y
}

export async function exportReportToPdf(input: ExportReportInput): Promise<void> {
  const prepared = prepareReportExport(input)
  if (!prepared.hasExportableContent) return

  const chartImages =
    prepared.chartSeries.length > 0 ? await captureChartImagesForExport(input) : []
  const imagesById = imageByChartId(chartImages)

  const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' })
  let y = MARGIN

  doc.setFont('helvetica', 'bold')
  doc.setFontSize(16)
  doc.setTextColor(15, 23, 42)
  doc.text(prepared.input.title?.trim() || 'Datamart Report', MARGIN, y)
  y += 8

  doc.setFont('helvetica', 'normal')
  doc.setFontSize(9)
  doc.setTextColor(100, 116, 139)
  doc.text(`Exported ${new Date().toLocaleString()}`, MARGIN, y)
  y += 10
  doc.setTextColor(30, 41, 59)

  const planned = usesPlannedExport(input)

  if (planned) {
    y = renderPlannedPdfSections(doc, y, prepared, imagesById)
  } else if (prepared.input.tableColumns.length) {
    const primary = prepared.input.scenarios?.find((s) => s.panelId === 'primary')
    const rows = primary
      ? tableRowsForExport(primary)
      : prepared.input.tableRows
    y = ensureSpace(doc, y, 20)
    y = addHeading(doc, 'Results', y)
    const { head, body } = tableFromRows(prepared.input.tableColumns, rows)
    autoTable(doc, {
      startY: y,
      head,
      body,
      margin: { left: MARGIN, right: MARGIN },
      styles: { fontSize: 8, cellPadding: 2, overflow: 'linebreak' },
      headStyles: { fillColor: [13, 148, 136], textColor: 255 },
      theme: 'striped',
    })
    y = (doc as jsPDF & { lastAutoTable: { finalY: number } }).lastAutoTable.finalY + 10
  }

  if (planned) {
    const base = input.filenameBase ?? 'datamart-report'
    downloadBlob(doc.output('blob'), `${base}.pdf`)
    return
  }

  for (const series of prepared.chartSeries) {
    const img = imagesById.get(series.chart.id)
    const caption = `Type: ${series.chart.chart_type} · Category: ${series.chart.category_column} · Value: ${series.chart.value_column}`
    if (img) {
      y = addChartImageSection(doc, y, series.title, caption, img.pngDataUrl)
    } else {
      y = ensureSpace(doc, y, 16)
      y = addHeading(doc, `Chart: ${series.title}`, y)
      y = addParagraph(
        doc,
        `${caption}\n(Chart image could not be captured.)`,
        y,
        9,
      )
    }
  }

  const base = input.filenameBase ?? 'datamart-report'
  const blob = doc.output('blob')
  downloadBlob(blob, `${base}.pdf`)
}
