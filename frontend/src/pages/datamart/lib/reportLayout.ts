/**
 * Report canvas layout (schema v1) — persisted on assistant messages.
 */
import { normalizeResultBlockId } from '../charts/chartSuggestions'
export type ReportWidgetKind =
  | 'summary'
  | 'sql'
  | 'transformations'
  | 'table'
  | 'charts'

/** `primary` = main SQL scenario; otherwise extra_result_blocks block_id */
export type ReportPanelId = 'primary' | string

export interface ReportLayoutWidget {
  id: string
  kind: ReportWidgetKind
  panel_id: ReportPanelId
  x: number
  y: number
  w: number
  h: number
  visible: boolean
  include_in_export: boolean
}

export interface DatamartReportLayoutV1 {
  schema_version: 1
  view_mode: 'stacked' | 'canvas'
  primary_label?: string | null
  /** Summary text for the primary scenario when a later turn adds scenarios. */
  primary_narrative?: string | null
  active_panel_id?: ReportPanelId | null
  widgets: ReportLayoutWidget[]
}

export type ReportLayoutPersistPatch = {
  report_layout?: DatamartReportLayoutV1
  primary_label?: string
  block_labels?: Record<string, string>
}

/** Merge layout/scenario label edits into an in-memory draft (template save payload). */
export function mergeLayoutPatchIntoDraft<T extends { report_layout?: Record<string, unknown> | null; extra_result_blocks?: Array<{ block_id: string; title?: string | null }> | null }>(
  draft: T,
  patch: ReportLayoutPersistPatch,
): T {
  const next = { ...draft }
  if (patch.report_layout) {
    next.report_layout = patch.report_layout as unknown as Record<string, unknown>
  } else if (patch.primary_label !== undefined) {
    const prev = (next.report_layout ?? {}) as unknown as DatamartReportLayoutV1
    next.report_layout = { ...prev, primary_label: patch.primary_label } as unknown as Record<
      string,
      unknown
    >
  }
  if (patch.block_labels && Object.keys(patch.block_labels).length > 0) {
    next.extra_result_blocks = (next.extra_result_blocks ?? []).map((b) => {
      const label = patch.block_labels![b.block_id]
      return label !== undefined ? { ...b, title: label } : b
    })
  }
  return next
}

export interface ScenarioDescriptor {
  panelId: ReportPanelId
  label: string
  isPrimary: boolean
}

const GRID_COLS = 12

function shortenQuestion(q: string | null | undefined, max = 48): string {
  const t = (q ?? '').trim()
  if (!t) return 'Scenario 1'
  return t.length > max ? `${t.slice(0, max).trim()}…` : t
}

export function buildScenarioList(
  primaryLabel: string | null | undefined,
  questionRef: string | null | undefined,
  extraBlocks: Array<{ block_id: string; title?: string | null }> | null | undefined,
): ScenarioDescriptor[] {
  const out: ScenarioDescriptor[] = [
    {
      panelId: 'primary',
      label: primaryLabel?.trim() || shortenQuestion(questionRef),
      isPrimary: true,
    },
  ]
  for (const b of extraBlocks ?? []) {
    if (!b.block_id) continue
    const rawTitle = b.title?.trim()
    out.push({
      panelId: b.block_id,
      label: rawTitle ? shortenQuestion(rawTitle, 36) : `Scenario ${out.length + 1}`,
      isPrimary: false,
    })
  }
  return out
}

function widget(
  kind: ReportWidgetKind,
  panelId: ReportPanelId,
  y: number,
  h: number,
  w = GRID_COLS,
): ReportLayoutWidget {
  const includeInExport = kind === 'table' || kind === 'charts'
  return {
    id: `${panelId}-${kind}`,
    kind,
    panel_id: panelId,
    x: 0,
    y,
    w,
    h,
    visible: true,
    include_in_export: includeInExport,
  }
}

/** Default stacked-friendly layout: one row of widgets per scenario. */
export function buildDefaultReportLayout(
  scenarios: ScenarioDescriptor[],
  hasSummary: boolean,
): DatamartReportLayoutV1 {
  const widgets: ReportLayoutWidget[] = []
  let y = 0

  if (hasSummary) {
    widgets.push({
      id: 'global-summary',
      kind: 'summary',
      panel_id: 'primary',
      x: 0,
      y: 0,
      w: GRID_COLS,
      h: 2,
      visible: true,
      include_in_export: false,
    })
    y = 2
  }

  for (let i = 0; i < scenarios.length; i++) {
    const panel = scenarios[i]!.panelId
    const baseY = y + i * 14
    widgets.push(
      widget('sql', panel, baseY, 2),
      widget('transformations', panel, baseY + 2, 2),
      widget('table', panel, baseY + 4, 5),
      widget('charts', panel, baseY + 9, 6),
    )
  }

  return {
    schema_version: 1,
    view_mode: 'stacked',
    primary_label: scenarios[0]?.label ?? 'Scenario 1',
    active_panel_id: scenarios[0]?.panelId ?? 'primary',
    widgets,
  }
}

/**
 * Merge persisted canvas widgets with the default per-scenario set so charts/sql/table
 * widgets are always present (e.g. after adding charts in stacked mode).
 */
export function ensureReportCanvasLayout(
  layout: DatamartReportLayoutV1,
  scenarios: ScenarioDescriptor[],
  hasSummary: boolean,
): DatamartReportLayoutV1 {
  const defaults = buildDefaultReportLayout(scenarios, hasSummary)
  const byId = new Map(layout.widgets.map((w) => [w.id, w]))
  const widgets = defaults.widgets.map((dw) => {
    const ex = byId.get(dw.id)
    if (!ex) return dw
    return {
      ...dw,
      x: ex.x,
      y: ex.y,
      w: ex.w,
      h: Math.max(ex.h, dw.h),
      visible: ex.visible,
      include_in_export: ex.include_in_export,
    }
  })
  return { ...layout, widgets }
}

export function normalizeReportLayout(
  raw: unknown,
  scenarios: ScenarioDescriptor[],
  hasSummary: boolean,
): DatamartReportLayoutV1 {
  if (raw && typeof raw === 'object' && (raw as DatamartReportLayoutV1).schema_version === 1) {
    const r = raw as DatamartReportLayoutV1
    const base: DatamartReportLayoutV1 = {
      schema_version: 1,
      view_mode: r.view_mode === 'canvas' ? 'canvas' : 'stacked',
      primary_label: r.primary_label ?? scenarios[0]?.label,
      active_panel_id: r.active_panel_id ?? scenarios[0]?.panelId ?? 'primary',
      widgets: Array.isArray(r.widgets) ? r.widgets : [],
    }
    if (base.view_mode === 'canvas' || base.widgets.length === 0) {
      return ensureReportCanvasLayout(
        base.widgets.length === 0
          ? { ...base, view_mode: base.view_mode === 'stacked' ? 'stacked' : 'canvas' }
          : base,
        scenarios,
        hasSummary,
      )
    }
    return base
  }
  return buildDefaultReportLayout(scenarios, hasSummary)
}

/** Repack widget rows top-to-bottom (used when showing one scenario on the canvas). */
export function repackCanvasWidgets(widgets: ReportLayoutWidget[]): ReportLayoutWidget[] {
  const sorted = [...widgets].sort((a, b) => a.y - b.y || a.x - b.x || a.id.localeCompare(b.id))
  let y = 0
  return sorted.map((w) => {
    const next = { ...w, x: 0, w: GRID_COLS, y }
    y += w.h
    return next
  })
}

/**
 * Widgets visible on the canvas for the selected scenario tab (+ optional global summary).
 * Full layout.widgets are unchanged — only the filtered view is repacked for display.
 */
export function visibleCanvasWidgets(
  layout: DatamartReportLayoutV1,
  activePanelId: ReportPanelId,
  options?: { includeSummary?: boolean },
): ReportLayoutWidget[] {
  const includeSummary = options?.includeSummary ?? true
  const filtered = layout.widgets.filter((w) => {
    if (!w.visible) return false
    if (includeSummary && w.kind === 'summary' && w.id === 'global-summary') return true
    return w.panel_id === activePanelId
  })
  return repackCanvasWidgets(filtered)
}

export function layoutWidgetsForPanel(
  layout: DatamartReportLayoutV1,
  panelId: ReportPanelId,
): ReportLayoutWidget[] {
  return layout.widgets.filter((w) => w.panel_id === panelId && w.visible)
}

export function chartsForPanel(charts: unknown[], panelId: ReportPanelId): unknown[] {
  const want = panelId === 'primary' ? null : panelId
  return charts.filter((c) => {
    if (!c || typeof c !== 'object') return false
    const rid = normalizeResultBlockId(
      (c as { result_block_id?: string | null }).result_block_id,
    )
    return rid === want
  })
}
