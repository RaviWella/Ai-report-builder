import { describe, expect, it } from 'vitest'
import {
  buildAllChartSuggestions,
  buildChartSuggestionsForPanel,
  chartSuggestionsForPanel,
  normalizeResultBlockId,
  type ChartSuggestionInput,
} from '../charts/chartSuggestions'

function dataset(
  result_block_id: string | null,
  label: string,
): ChartSuggestionInput {
  return {
    result_block_id,
    dataset_label: label,
    columns: ['category', 'value'],
    rows: [
      ['A', 10],
      ['B', 20],
      ['C', 30],
    ],
  }
}

describe('chartSuggestionsForPanel', () => {
  it('filters suggestions to the active scenario panel', () => {
    const all = buildAllChartSuggestions(
      [dataset(null, 'Primary'), dataset('block-b', 'Scenario B')],
      [],
    )
    const primary = chartSuggestionsForPanel(all, 'primary')
    const blockB = chartSuggestionsForPanel(all, 'block-b')

    expect(primary.length).toBeGreaterThan(0)
    expect(blockB.length).toBeGreaterThan(0)
    expect(primary.every((s) => s.result_block_id == null)).toBe(true)
    expect(blockB.every((s) => s.result_block_id === 'block-b')).toBe(true)
  })
})

describe('buildAllChartSuggestions', () => {
  it('returns suggestions for each scenario dataset, not only the top global few', () => {
    const all = buildAllChartSuggestions(
      [dataset(null, 'Primary'), dataset('block-b', 'Scenario B')],
      [],
    )
    expect(chartSuggestionsForPanel(all, 'primary').length).toBeGreaterThan(0)
    expect(chartSuggestionsForPanel(all, 'block-b').length).toBeGreaterThan(0)
  })
})

describe('buildChartSuggestionsForPanel', () => {
  it('uses only the matching scenario dataset (different columns per block)', () => {
    const inputs: ChartSuggestionInput[] = [
      {
        result_block_id: null,
        dataset_label: 'Headcount',
        columns: ['dept', 'headcount'],
        rows: [
          ['Sales', 10],
          ['HR', 5],
        ],
      },
      {
        result_block_id: 'block-pay',
        dataset_label: 'Payroll',
        columns: ['month', 'gross_pay'],
        rows: [
          ['Jan', 100],
          ['Feb', 120],
        ],
      },
    ]
    const primary = buildChartSuggestionsForPanel('primary', inputs, [])
    const payroll = buildChartSuggestionsForPanel('block-pay', inputs, [])

    expect(primary.every((s) => normalizeResultBlockId(s.result_block_id) === null)).toBe(true)
    expect(payroll.every((s) => s.result_block_id === 'block-pay')).toBe(true)
    expect(primary.some((s) => s.category_column === 'dept')).toBe(true)
    expect(payroll.some((s) => s.category_column === 'month')).toBe(true)
    expect(primary.some((s) => s.category_column === 'month')).toBe(false)
    expect(payroll.some((s) => s.category_column === 'dept')).toBe(false)
  })
})
