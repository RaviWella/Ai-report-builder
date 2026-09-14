import { describe, expect, it } from 'vitest'
import {
  computeColumnWidths,
  isSummaryRow,
  normalizeTableRow,
  partitionTableRows,
  shouldVirtualizeTable,
  TABLE_VIRTUALIZE_THRESHOLD,
  tableMinWidth,
} from './tableFormat'

describe('tableFormat', () => {
  it('detects summary rows', () => {
    expect(isSummaryRow(['Average', 12])).toBe(true)
    expect(isSummaryRow(['North', 3])).toBe(false)
  })

  it('partitions detail and summary rows', () => {
    const rows = [
      ['a', 1],
      ['Total', 10],
    ]
    const { detailRows, summaryRows } = partitionTableRows(rows)
    expect(detailRows).toHaveLength(1)
    expect(summaryRows).toHaveLength(1)
  })

  it('virtualizes at threshold', () => {
    expect(shouldVirtualizeTable(TABLE_VIRTUALIZE_THRESHOLD - 1)).toBe(false)
    expect(shouldVirtualizeTable(TABLE_VIRTUALIZE_THRESHOLD)).toBe(true)
  })

  it('pads short rows to column count', () => {
    expect(normalizeTableRow(['a', 'b'], 4)).toEqual(['a', 'b', null, null])
    expect(normalizeTableRow(['a', 'b', 'c', 'd', 'e'], 3)).toEqual(['a', 'b', 'c'])
  })

  it('computes stable column widths from headers and sample rows', () => {
    const columns = ['employee_name', 'reporting_manager_employee_id']
    const rows = [['Jane Doe', 'EMP001']]
    const widths = computeColumnWidths(columns, rows)
    expect(widths).toHaveLength(2)
    expect(widths[0]).toBeGreaterThan(0)
    expect(tableMinWidth(widths)).toBe(widths[0] + widths[1])
  })
})
