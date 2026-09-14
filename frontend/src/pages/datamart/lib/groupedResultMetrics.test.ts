import { describe, expect, it } from 'vitest'
import { buildGroupedResultMetricsView } from './groupedResultMetrics'

describe('buildGroupedResultMetricsView', () => {
  it('builds cards for branch employee counts', () => {
    const view = buildGroupedResultMetricsView(
      ['branch', 'Employee Count'],
      [
        ['North', 42],
        ['South', 18],
      ],
      null,
    )
    expect(view).not.toBeNull()
    expect(view!.rows).toHaveLength(2)
    expect(view!.rows[0].title).toBe('North')
    expect(view!.rows[0].metrics[0].value).toBe('42')
  })

  it('skips when append post-process is configured', () => {
    const view = buildGroupedResultMetricsView(
      ['branch', 'cnt'],
      [['A', 1]],
      [{ type: 'append_aggregate_row', aggregations: { cnt: 'SUM' }, label: 'Total' }],
    )
    expect(view).toBeNull()
  })
})
