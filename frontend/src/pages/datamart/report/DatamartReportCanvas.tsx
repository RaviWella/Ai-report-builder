/**
 * Draggable report canvas (react-grid-layout) for report widgets.
 */
import React, { useCallback, useMemo } from 'react'
import { Responsive, WidthProvider, type Layout } from 'react-grid-layout'
import 'react-grid-layout/css/styles.css'
import 'react-resizable/css/styles.css'
import type { DatamartReportLayoutV1, ReportLayoutWidget, ReportPanelId } from '../lib/reportLayout'
import { visibleCanvasWidgets } from '../lib/reportLayout'
import { dmColors, dmRadius, dmSpace } from '../lib/tokens'

const ResponsiveGrid = WidthProvider(Responsive)

export interface DatamartReportCanvasProps {
  layout: DatamartReportLayoutV1
  /** When set (multi-scenario), only this scenario's widgets are shown on the canvas. */
  activePanelId?: ReportPanelId | null
  panelLabels?: Record<string, string>
  editable: boolean
  onLayoutChange: (widgets: ReportLayoutWidget[]) => void
  renderWidget: (widget: ReportLayoutWidget) => React.ReactNode
}

const DatamartReportCanvas: React.FC<DatamartReportCanvasProps> = ({
  layout,
  activePanelId = null,
  panelLabels,
  editable,
  onLayoutChange,
  renderWidget,
}) => {
  const visible = useMemo(() => {
    if (activePanelId) {
      return visibleCanvasWidgets(layout, activePanelId)
    }
    return layout.widgets.filter((w) => w.visible)
  }, [layout, activePanelId])

  const gridLayout: Layout[] = useMemo(
    () =>
      visible.map((w) => ({
        i: w.id,
        x: w.x,
        y: w.y,
        w: w.w,
        h: w.h,
        minW: 4,
        minH: w.kind === 'charts' ? 5 : 2,
        static: !editable,
      })),
    [visible, editable],
  )

  const widgetTitle = useCallback(
    (w: ReportLayoutWidget) => {
      const kind = w.kind.replace('_', ' ')
      if (w.kind === 'summary') return kind
      const label = panelLabels?.[w.panel_id] ?? w.panel_id
      return `${label} · ${kind}`
    },
    [panelLabels],
  )

  const handleLayoutChange = useCallback(
    (next: Layout[]) => {
      if (!editable) return
      const byId = new Map(next.map((l) => [l.i, l]))
      const merged = layout.widgets.map((w) => {
        const n = byId.get(w.id)
        if (!n) return w
        return { ...w, x: n.x, y: n.y, w: n.w, h: n.h }
      })
      onLayoutChange(merged)
    },
    [editable, layout.widgets, onLayoutChange],
  )

  if (visible.length === 0) {
    const panelHint = activePanelId
      ? panelLabels?.[activePanelId] ?? 'this scenario'
      : 'the report'
    return (
      <p style={{ fontSize: 13, color: dmColors.textMuted, margin: dmSpace.md }}>
        No components to display for {panelHint}. Run its query in Sections view or switch
        scenario.
      </p>
    )
  }

  return (
    <div style={{ margin: `0 ${dmSpace.lg}px ${dmSpace.lg}px` }}>
      <ResponsiveGrid
        key={activePanelId ?? 'all-panels'}
        className="datamart-report-canvas"
        layouts={{ lg: gridLayout }}
        breakpoints={{ lg: 900 }}
        cols={{ lg: 12 }}
        rowHeight={28}
        margin={[12, 12]}
        containerPadding={[0, 0]}
        draggableHandle={editable ? '.dm-canvas-drag-handle' : undefined}
        isDraggable={editable}
        isResizable={editable}
        onLayoutChange={handleLayoutChange}
        compactType="vertical"
      >
        {visible.map((w) => (
          <div
            key={w.id}
            style={{
              background: dmColors.surface,
              border: `1px solid ${dmColors.border}`,
              borderRadius: dmRadius.md,
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column',
              minHeight: 0,
            }}
          >
            {editable && (
              <div
                className="dm-canvas-drag-handle"
                style={{
                  cursor: 'grab',
                  padding: '6px 10px',
                  borderBottom: `1px solid ${dmColors.border}`,
                  background: dmColors.surfaceMuted,
                  fontSize: 11,
                  fontWeight: 600,
                  color: dmColors.textMuted,
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                }}
              >
                {widgetTitle(w)}
              </div>
            )}
            <div style={{ flex: 1, minHeight: 0, overflow: 'auto', padding: dmSpace.sm }}>
              {renderWidget(w)}
            </div>
          </div>
        ))}
      </ResponsiveGrid>
    </div>
  )
}

export function panelHeaderColor(panelId: ReportPanelId, active: boolean): string {
  if (active) return dmColors.accent
  return panelId === 'primary' ? '#0f766e' : '#0d9488'
}

export default DatamartReportCanvas
