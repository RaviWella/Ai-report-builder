import { describe, expect, it } from 'vitest'
import { buildPostProcessExportBlock } from './formatPostProcessExport'

describe('buildPostProcessExportBlock', () => {
  it('builds human steps and config rows', () => {
    const block = buildPostProcessExportBlock(
      [{ type: 'append_aggregate_row', label: 'Total' }],
      ['a', 'b'],
      [['x', 1]],
      null,
    )
    expect(block?.humanSteps.length).toBe(1)
    expect(block?.configRows.some((r) => r.parameter === 'label')).toBe(true)
  })
})
