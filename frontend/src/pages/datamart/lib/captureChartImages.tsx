/**
 * Capture Recharts plot areas as PNG for CSV (ZIP) and PDF export.
 */
import { createRoot, type Root } from 'react-dom/client'
import { domToPng } from 'modern-screenshot'
import DatamartCharts from '../charts/DatamartCharts'
import { isDatamartChartConfigV1 } from '../charts/chartConfig'
import type { ExportReportInput } from './exportReportModel'
import { prepareReportExport } from './exportReportModel'

export interface ChartExportImage {
  chartId: string
  title: string
  pngDataUrl: string
}

const CAPTURE_WAIT_MS = 750

function safeChartFilename(title: string, chartId: string): string {
  const slug =
    title
      .replace(/[^\w\-]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 40) || 'chart'
  return `${slug}-${chartId.slice(0, 8)}.png`
}

export function chartImageFilename(img: ChartExportImage): string {
  return safeChartFilename(img.title, img.chartId)
}

async function waitForPaint(ms = CAPTURE_WAIT_MS): Promise<void> {
  await new Promise<void>((resolve) => {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => setTimeout(resolve, ms))
    })
  })
}

async function captureElement(el: HTMLElement): Promise<string> {
  await waitForPaint(120)
  return domToPng(el, {
    scale: 2,
    backgroundColor: '#ffffff',
  })
}

async function captureFromDom(
  chartIds: string[],
  titleById: Map<string, string>,
): Promise<Map<string, ChartExportImage>> {
  const out = new Map<string, ChartExportImage>()
  for (const chartId of chartIds) {
    const el = document.querySelector(
      `[data-chart-export-id="${chartId}"]`,
    ) as HTMLElement | null
    if (!el) continue
    try {
      const pngDataUrl = await captureElement(el)
      out.set(chartId, {
        chartId,
        title: titleById.get(chartId) ?? chartId,
        pngDataUrl,
      })
    } catch {
      /* try off-screen render */
    }
  }
  return out
}

async function captureChartsOffscreen(
  input: ExportReportInput,
  chartIds: string[],
): Promise<Map<string, ChartExportImage>> {
  const charts = input.charts.filter(isDatamartChartConfigV1).filter((c) => chartIds.includes(c.id))
  if (!charts.length) return new Map()

  const host = document.createElement('div')
  host.setAttribute('data-datamart-export-host', 'true')
  host.style.cssText =
    'position:fixed;left:-10000px;top:0;width:720px;pointer-events:none;z-index:-1;background:#fff;'
  document.body.appendChild(host)

  let root: Root | null = null
  const out = new Map<string, ChartExportImage>()
  try {
    root = createRoot(host)
    root.render(
      <DatamartCharts
        chartConfigs={charts}
        primaryDataset={input.primaryDataset}
        blockDatasets={input.blockDatasets}
        exportMode
      />,
    )
    await waitForPaint()

    const prepared = prepareReportExport(input)
    for (const series of prepared.chartSeries) {
      if (!chartIds.includes(series.chart.id)) continue
      const el = host.querySelector(
        `[data-chart-export-id="${series.chart.id}"]`,
      ) as HTMLElement | null
      if (!el) continue
      try {
        const pngDataUrl = await captureElement(el)
        out.set(series.chart.id, {
          chartId: series.chart.id,
          title: series.title,
          pngDataUrl,
        })
      } catch {
        /* skip chart */
      }
    }
  } finally {
    root?.unmount()
    host.remove()
  }
  return out
}

/** PNG data URLs for each chart, in report order. */
export async function captureChartImagesForExport(
  input: ExportReportInput,
): Promise<ChartExportImage[]> {
  const prepared = prepareReportExport(input)
  if (!prepared.chartSeries.length) return []

  const ids = prepared.chartSeries.map((s) => s.chart.id)
  const titleById = new Map(prepared.chartSeries.map((s) => [s.chart.id, s.title]))
  const byId = await captureFromDom(ids, titleById)
  const missing = ids.filter((id) => !byId.has(id))
  if (missing.length) {
    const offscreen = await captureChartsOffscreen(input, missing)
    for (const [id, img] of offscreen) byId.set(id, img)
  }

  return prepared.chartSeries
    .map((s) => byId.get(s.chart.id))
    .filter((img): img is ChartExportImage => Boolean(img))
}
