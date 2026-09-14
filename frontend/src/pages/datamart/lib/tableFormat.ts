/**
 * Shared formatting helpers for datamart result tables.
 */

export const TABLE_ROW_HEIGHT = 37
export const TABLE_MAX_VIEWPORT_HEIGHT = 380
/** Use virtual scrolling when detail rows meet or exceed this count. */
export const TABLE_VIRTUALIZE_THRESHOLD = 40

export const SUMMARY_LABELS = new Set([
  'average',
  'avg',
  'total',
  'sum',
  'summary',
  'subtotal',
  'count',
  'min',
  'max',
  'median',
])

export function isSummaryRow(row: unknown[]): boolean {
  return row.some((v) => {
    if (typeof v !== 'string') return false
    const t = v.toLowerCase().trim()
    if (SUMMARY_LABELS.has(t)) return true
    if (t.includes('average') || t.includes('summary') || t.includes('subtotal')) return true
    return false
  })
}

export function partitionTableRows(rows: unknown[][]): {
  detailRows: unknown[][]
  summaryRows: unknown[][]
} {
  const detailRows: unknown[][] = []
  const summaryRows: unknown[][] = []
  for (const row of rows) {
    if (isSummaryRow(row)) summaryRows.push(row)
    else detailRows.push(row)
  }
  return { detailRows, summaryRows }
}

export function shouldVirtualizeTable(rowCount: number): boolean {
  return rowCount >= TABLE_VIRTUALIZE_THRESHOLD
}

export function tableBodyHeight(rowCount: number): number {
  return Math.min(TABLE_MAX_VIEWPORT_HEIGHT, Math.max(rowCount, 1) * TABLE_ROW_HEIGHT)
}

export function isNumeric(value: unknown): boolean {
  return typeof value === 'number' && !Number.isNaN(value)
}

export function formatCell(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) return '—'
    return Number.isInteger(value)
      ? value.toLocaleString()
      : value.toLocaleString(undefined, { maximumFractionDigits: 4 })
  }
  return String(value)
}

export function formatHeader(col: string): string {
  return col
    .replace(/_/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

const COL_WIDTH_MIN = 96
const COL_WIDTH_MAX = 320
const COL_WIDTH_DEFAULT = 140
const COL_WIDTH_PAD_PX = 28
const COL_WIDTH_CHAR_PX = 7.5

/** Pixel widths shared by table header, virtualized body, and summary footer. */
export function computeColumnWidths(
  columns: string[],
  rows: unknown[][],
  sampleSize = 32,
): number[] {
  if (!columns.length) return []

  return columns.map((col, colIdx) => {
    let maxChars = formatHeader(col).length
    const sample = rows.slice(0, sampleSize)
    for (const row of sample) {
      const cell = row[colIdx]
      const text = formatCell(cell)
      if (text !== '—') maxChars = Math.max(maxChars, text.length)
    }
    const estimated = maxChars * COL_WIDTH_CHAR_PX + COL_WIDTH_PAD_PX
    return Math.round(
      Math.min(COL_WIDTH_MAX, Math.max(COL_WIDTH_MIN, estimated || COL_WIDTH_DEFAULT)),
    )
  })
}

export function tableMinWidth(columnWidths: number[]): number {
  return columnWidths.reduce((sum, w) => sum + w, 0)
}

/** Keep row cells aligned with header columns when the API returns ragged rows. */
export function normalizeTableRow(row: unknown[], columnCount: number): unknown[] {
  if (columnCount <= 0) return row
  if (row.length === columnCount) return row
  if (row.length < columnCount) {
    return [...row, ...Array.from({ length: columnCount - row.length }, () => null)]
  }
  return row.slice(0, columnCount)
}

export function normalizeTableRows(rows: unknown[][], columnCount: number): unknown[][] {
  return rows.map((row) => normalizeTableRow(row, columnCount))
}
