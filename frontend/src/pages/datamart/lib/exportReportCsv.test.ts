import { describe, expect, it } from 'vitest'
import { buildReportCsvContent } from './exportReportCsv'
import type { DatamartChartConfigV1 } from '../charts/chartConfig'

const chart: DatamartChartConfigV1 = {
  schema_version: 1,
  id: 'c1',
  chart_type: 'bar',
  title: 'By branch',
  data_source: 'final',
  category_column: 'branch',
  value_column: 'total',
}

describe('buildReportCsvContent', () => {
  it('exports only results table and chart sections (no SQL or transformations)', () => {
    const csv = buildReportCsvContent({
      title: 'Leave report',
      narrative: 'Summary text',
      sql: 'SELECT 1',
      tableColumns: ['branch', 'total'],
      tableRows: [['North', 10]],
      postProcessConfig: [
        { type: 'append_aggregate_row', label: 'Grand total', aggregations: { total: 'SUM' } },
      ],
      charts: [chart],
      primaryDataset: {
        finalColumns: ['branch', 'total'],
        finalRows: [['North', 10]],
      },
      scenarios: [
        {
          panelId: 'primary',
          label: 'Scenario 1',
          sql: 'SELECT 1',
          postProcessConfig: [
            {
              type: 'append_aggregate_row',
              label: 'Grand total',
              aggregations: { total: 'SUM' },
            },
          ],
          tableColumns: ['branch', 'total'],
          tableRows: [['North', 10]],
        },
      ],
      exportWidgets: [
        {
          id: 'primary-table',
          kind: 'table',
          panel_id: 'primary',
          x: 0,
          y: 0,
          w: 12,
          h: 5,
          visible: true,
          include_in_export: true,
        },
        {
          id: 'primary-charts',
          kind: 'charts',
          panel_id: 'primary',
          x: 0,
          y: 5,
          w: 12,
          h: 6,
          visible: true,
          include_in_export: true,
        },
      ],
      layout: {
        schema_version: 1,
        view_mode: 'stacked',
        widgets: [],
      },
    })
    expect(csv).toContain('# Results — Scenario 1')
    expect(csv).toContain('branch,total')
    expect(csv).toContain('North,10')
    expect(csv).toContain('# Chart — Scenario 1: By branch')
    expect(csv).not.toContain('# Query (SQL)')
    expect(csv).not.toContain('# Summary')
    expect(csv).not.toContain('# Transformations')
    expect(csv).not.toContain('key metrics')
  })
})
