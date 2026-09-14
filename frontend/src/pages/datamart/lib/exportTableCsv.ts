/**
 * Client-side CSV export for datamart result grids.
 */
export function exportTableToCsv(
  columns: string[],
  rows: unknown[][],
  filename = 'datamart-export.csv',
): void {
  if (!columns.length) return

  const escape = (v: unknown): string => {
    if (v === null || v === undefined) return ''
    const s = String(v)
    if (/[",\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`
    return s
  }

  const lines = [
    columns.map(escape).join(','),
    ...rows.map((row) => columns.map((_, i) => escape(row[i])).join(',')),
  ]
  const blob = new Blob([lines.join('\r\n')], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
