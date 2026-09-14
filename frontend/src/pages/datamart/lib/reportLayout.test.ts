import { describe, expect, it } from 'vitest'
import {
  buildDefaultReportLayout,
  buildScenarioList,
  ensureReportCanvasLayout,
  visibleCanvasWidgets,
  type DatamartReportLayoutV1,
} from './reportLayout'

describe('buildScenarioList', () => {
  it('shortens long extra scenario titles for the modify picker', () => {
    const long =
      'Prepare a leave utilization report by combining leave transaction, leave type, and employee'
    const scenarios = buildScenarioList(null, 'Primary question', [
      { block_id: 'block-x', title: long },
    ])
    expect(scenarios[1].label.endsWith('…')).toBe(true)
    expect(scenarios[1].label.length).toBeLessThanOrEqual(40)
  })
})

describe('buildDefaultReportLayout', () => {
  it('defaults to stacked (sections) view for new reports', () => {
    const scenarios = buildScenarioList(null, 'Top paid employees', [])
    const layout = buildDefaultReportLayout(scenarios, true)
    expect(layout.view_mode).toBe('stacked')
  })
})

describe('ensureReportCanvasLayout', () => {
  const scenarios = buildScenarioList(null, 'Compare headcount', [
    { block_id: 'block-b', title: 'Scenario B' },
  ])

  it('adds missing charts widgets when layout was empty', () => {
    const empty: DatamartReportLayoutV1 = {
      schema_version: 1,
      view_mode: 'stacked',
      widgets: [],
    }
    const merged = ensureReportCanvasLayout(empty, scenarios, false)
    const chartWidgets = merged.widgets.filter((w) => w.kind === 'charts')
    expect(chartWidgets).toHaveLength(2)
    expect(chartWidgets.map((w) => w.panel_id).sort()).toEqual(['block-b', 'primary'])
  })

  it('shows only the active scenario widgets on the canvas', () => {
    const merged = ensureReportCanvasLayout(
      { schema_version: 1, view_mode: 'canvas', widgets: [] },
      scenarios,
      false,
    )
    const primaryOnly = visibleCanvasWidgets(merged, 'primary')
    const blockOnly = visibleCanvasWidgets(merged, 'block-b')

    expect(primaryOnly.every((w) => w.panel_id === 'primary' || w.id === 'global-summary')).toBe(
      true,
    )
    expect(blockOnly.every((w) => w.panel_id === 'block-b')).toBe(true)
    expect(blockOnly.some((w) => w.kind === 'charts')).toBe(true)
    expect(primaryOnly[0]?.y).toBe(0)
  })

  it('preserves positions but keeps default chart widget height', () => {
    const defaults = buildDefaultReportLayout(scenarios, false)
    const chartsId = 'primary-charts'
    const custom = {
      ...defaults,
      widgets: defaults.widgets.map((w) =>
        w.id === chartsId ? { ...w, y: 99, h: 2 } : w,
      ),
    }
    const merged = ensureReportCanvasLayout(custom, scenarios, false)
    const charts = merged.widgets.find((w) => w.id === chartsId)!
    expect(charts.y).toBe(99)
    expect(charts.h).toBeGreaterThanOrEqual(6)
  })
})
