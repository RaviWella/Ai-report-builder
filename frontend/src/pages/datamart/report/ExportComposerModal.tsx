/**
 * Export composer — drag-and-drop canvas to choose export sections and order.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import {
  X,
  FileSpreadsheet,
  FileText,
  GripVertical,
  LayoutGrid,
  Loader2,
} from 'lucide-react'
import DatamartReportCanvas from './DatamartReportCanvas'
import type { ExportReportInput } from '../lib/exportReportModel'
import type { ExportScenarioSlice } from '../lib/exportReportContext'
import { widgetLabel } from '../lib/exportReportContext'
import { EXPORT_WIDGET_KIND_META } from '../lib/exportWidgetKindMeta'
import {
  buildDefaultReportLayout,
  chartsForPanel,
  type DatamartReportLayoutV1,
  type ReportLayoutWidget,
  type ScenarioDescriptor,
} from '../lib/reportLayout'
import { dmColors, dmRadius, dmSpace } from '../lib/tokens'
import { dmCopy } from '../lib/copy'

const COMPOSER_CSS = `
.export-composer-overlay {
  position: fixed;
  inset: 0;
  z-index: 2000;
  display: flex;
  align-items: stretch;
  justify-content: center;
  padding: 12px;
  background: rgba(15, 23, 42, 0.45);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
}
.export-composer-panel {
  display: flex;
  flex-direction: column;
  width: 100%;
  max-width: 1120px;
  max-height: 100%;
  margin: auto;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 24px 64px rgba(15, 23, 42, 0.18);
  overflow: hidden;
  min-height: 0;
}
.export-composer-body {
  display: grid;
  grid-template-columns: minmax(240px, 280px) minmax(0, 1fr);
  flex: 1;
  min-height: 0;
  overflow: hidden;
}
@media (max-width: 768px) {
  .export-composer-overlay { padding: 0; align-items: flex-end; }
  .export-composer-panel {
    max-width: 100%;
    max-height: 96vh;
    border-radius: 16px 16px 0 0;
  }
  .export-composer-body {
    grid-template-columns: 1fr;
    grid-template-rows: auto minmax(200px, 1fr);
  }
}
`

let cssInjected = false
function injectComposerCss() {
  if (cssInjected) return
  const el = document.createElement('style')
  el.textContent = COMPOSER_CSS
  document.head.appendChild(el)
  cssInjected = true
}

function ensureExportLayout(
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
      h: ex.h,
      visible: ex.visible,
      include_in_export: ex.include_in_export,
    }
  })
  return { ...layout, view_mode: 'canvas', widgets }
}

export interface ExportComposerModalProps {
  open: boolean
  onClose: () => void
  layout: DatamartReportLayoutV1
  onLayoutChange: (next: DatamartReportLayoutV1) => void
  scenarios: ScenarioDescriptor[]
  hasSummary: boolean
  narrative?: string
  scenarioSlices: ExportScenarioSlice[]
  charts: unknown[]
  getExportInput: (layout: DatamartReportLayoutV1) => ExportReportInput | null
  exporting: boolean
  onExportCsv: (input: ExportReportInput) => Promise<void>
  onExportPdf: (input: ExportReportInput) => Promise<void>
}

const ExportComposerModal: React.FC<ExportComposerModalProps> = ({
  open,
  onClose,
  layout,
  onLayoutChange,
  scenarios,
  hasSummary,
  narrative,
  scenarioSlices,
  charts,
  getExportInput,
  exporting,
  onExportCsv,
  onExportPdf,
}) => {
  const [draft, setDraft] = useState<DatamartReportLayoutV1>(layout)

  useEffect(() => {
    injectComposerCss()
  }, [])

  useEffect(() => {
    if (!open) return
    setDraft(ensureExportLayout(layout, scenarios, hasSummary))
  }, [open, layout, scenarios, hasSummary])

  useEffect(() => {
    if (!open) return undefined
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])

  const sortedWidgets = useMemo(
    () =>
      [...draft.widgets].sort(
        (a, b) => a.y - b.y || a.x - b.x || a.id.localeCompare(b.id),
      ),
    [draft.widgets],
  )

  const includedCount = draft.widgets.filter((w) => w.include_in_export).length

  const canvasLayout = useMemo(
    (): DatamartReportLayoutV1 => ({
      ...draft,
      view_mode: 'canvas',
      widgets: draft.widgets.filter((w) => w.include_in_export),
    }),
    [draft],
  )

  const patchWidgets = useCallback(
    (widgets: ReportLayoutWidget[]) => {
      const next = { ...draft, widgets }
      setDraft(next)
      onLayoutChange(next)
    },
    [draft, onLayoutChange],
  )

  const toggleInclude = useCallback(
    (id: string) => {
      patchWidgets(
        draft.widgets.map((w) =>
          w.id === id ? { ...w, include_in_export: !w.include_in_export } : w,
        ),
      )
    },
    [draft.widgets, patchWidgets],
  )

  const selectAll = useCallback(
    (on: boolean) => {
      patchWidgets(draft.widgets.map((w) => ({ ...w, include_in_export: on })))
    },
    [draft.widgets, patchWidgets],
  )

  const handleCanvasLayoutChange = useCallback(
    (visibleWidgets: ReportLayoutWidget[]) => {
      const byId = new Map(visibleWidgets.map((w) => [w.id, w]))
      patchWidgets(
        draft.widgets.map((w) => {
          const moved = byId.get(w.id)
          if (!moved) return w
          return {
            ...w,
            x: moved.x,
            y: moved.y,
            w: moved.w,
            h: moved.h,
          }
        }),
      )
    },
    [draft.widgets, patchWidgets],
  )

  const runExport = useCallback(
    async (format: 'csv' | 'pdf') => {
      const input = getExportInput(draft)
      if (!input || exporting) return
      if (format === 'csv') await onExportCsv(input)
      else await onExportPdf(input)
    },
    [draft, exporting, getExportInput, onExportCsv, onExportPdf],
  )

  const renderPreview = useCallback(
    (w: ReportLayoutWidget) => {
      const slice = scenarioSlices.find((s) => s.panelId === w.panel_id)
      const meta = EXPORT_WIDGET_KIND_META[w.kind]

      if (w.kind === 'summary') {
        return (
          <p style={{ fontSize: 12, color: dmColors.text, margin: 0, lineHeight: 1.5 }}>
            {(narrative ?? '').slice(0, 220)}
            {(narrative?.length ?? 0) > 220 ? '…' : ''}
          </p>
        )
      }
      if (w.kind === 'sql') {
        return (
          <pre
            style={{
              margin: 0,
              fontSize: 10,
              color: '#94a3b8',
              background: '#0f172a',
              padding: 8,
              borderRadius: 6,
              maxHeight: 72,
              overflow: 'auto',
            }}
          >
            {(slice?.sql ?? '—').slice(0, 400)}
          </pre>
        )
      }
      if (w.kind === 'table') {
        const rows = slice?.tableRows.length ?? 0
        const cols = slice?.tableColumns.length ?? 0
        return (
          <div style={{ fontSize: 12, color: dmColors.textMuted }}>
            <strong style={{ color: dmColors.brand }}>{rows}</strong> rows ·{' '}
            <strong style={{ color: dmColors.brand }}>{cols}</strong> columns
          </div>
        )
      }
      if (w.kind === 'charts') {
        const n = chartsForPanel(charts, w.panel_id).length
        return (
          <p style={{ fontSize: 12, color: dmColors.textMuted, margin: 0 }}>
            {n} chart{n === 1 ? '' : 's'} will be exported as images
          </p>
        )
      }
      if (w.kind === 'transformations') {
        const steps = slice?.postProcessConfig?.length ?? 0
        return (
          <p style={{ fontSize: 12, color: dmColors.textMuted, margin: 0 }}>
            {steps} transformation step{steps === 1 ? '' : 's'}
          </p>
        )
      }
      return (
        <p style={{ fontSize: 12, color: dmColors.textMuted, margin: 0 }}>
          {meta.short}
        </p>
      )
    },
    [charts, narrative, scenarioSlices, scenarios],
  )

  if (!open) return null

  return createPortal(
    <div
      className="export-composer-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="export-composer-title"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className="export-composer-panel" onMouseDown={(e) => e.stopPropagation()}>
        <header
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: 12,
            padding: `${dmSpace.md}px ${dmSpace.lg}px`,
            borderBottom: `1px solid ${dmColors.border}`,
            flexShrink: 0,
          }}
        >
          <div
            style={{
              width: 40,
              height: 40,
              borderRadius: 12,
              background: dmColors.brandMuted,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            <LayoutGrid size={20} color={dmColors.brand} />
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <h2
              id="export-composer-title"
              style={{
                margin: 0,
                fontSize: 17,
                fontWeight: 700,
                color: dmColors.text,
                letterSpacing: '-0.02em',
              }}
            >
              {dmCopy.exportComposer.title}
            </h2>
            <p style={{ margin: '4px 0 0', fontSize: 13, color: dmColors.textMuted, lineHeight: 1.45 }}>
              {dmCopy.exportComposer.subtitle}
            </p>
          </div>
          <button
            type="button"
            aria-label="Close"
            onClick={onClose}
            style={{
              border: 'none',
              background: dmColors.surfaceMuted,
              borderRadius: dmRadius.sm,
              padding: 8,
              cursor: 'pointer',
              color: dmColors.textMuted,
            }}
          >
            <X size={18} />
          </button>
        </header>

        <div className="export-composer-body">
          <aside
            style={{
              borderRight: `1px solid ${dmColors.border}`,
              overflowY: 'auto',
              padding: dmSpace.md,
              background: dmColors.surfaceMuted,
              minHeight: 0,
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: 10,
              }}
            >
              <span style={{ fontSize: 11, fontWeight: 700, color: dmColors.textMuted, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                Components ({includedCount}/{draft.widgets.length})
              </span>
              <div style={{ display: 'flex', gap: 6 }}>
                <button
                  type="button"
                  onClick={() => selectAll(true)}
                  style={linkBtn}
                >
                  All
                </button>
                <button
                  type="button"
                  onClick={() => selectAll(false)}
                  style={linkBtn}
                >
                  None
                </button>
              </div>
            </div>

            <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 6 }}>
              {sortedWidgets.map((w) => {
                const meta = EXPORT_WIDGET_KIND_META[w.kind]
                return (
                  <li key={w.id}>
                    <label
                      style={{
                        display: 'flex',
                        alignItems: 'flex-start',
                        gap: 8,
                        padding: '8px 10px',
                        borderRadius: dmRadius.md,
                        background: w.include_in_export ? '#fff' : 'transparent',
                        border: `1px solid ${w.include_in_export ? dmColors.brandBorder : 'transparent'}`,
                        cursor: 'pointer',
                        opacity: w.include_in_export ? 1 : 0.55,
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={w.include_in_export}
                        onChange={() => toggleInclude(w.id)}
                        style={{ marginTop: 3, accentColor: dmColors.brand }}
                      />
                      <span style={{ fontSize: 16, lineHeight: 1 }} aria-hidden>
                        {meta.icon}
                      </span>
                      <span style={{ flex: 1, minWidth: 0 }}>
                        <span
                          style={{
                            display: 'block',
                            fontSize: 12,
                            fontWeight: 600,
                            color: dmColors.text,
                            lineHeight: 1.35,
                          }}
                        >
                          {widgetLabel(w, scenarios)}
                        </span>
                      </span>
                      <GripVertical size={14} color={dmColors.textSubtle} style={{ flexShrink: 0 }} />
                    </label>
                  </li>
                )
              })}
            </ul>
          </aside>

          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              minHeight: 0,
              overflow: 'hidden',
              background: '#f8fafc',
            }}
          >
            <p
              style={{
                margin: 0,
                padding: `${dmSpace.sm}px ${dmSpace.lg}px`,
                fontSize: 12,
                color: dmColors.textMuted,
                borderBottom: `1px solid ${dmColors.borderLight}`,
                flexShrink: 0,
              }}
            >
              {dmCopy.exportComposer.canvasHint}
            </p>
            <div style={{ flex: 1, minHeight: 0, overflow: 'auto', padding: dmSpace.sm }}>
              {includedCount === 0 ? (
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    minHeight: 200,
                    padding: dmSpace.lg,
                    textAlign: 'center',
                  }}
                >
                  <p style={{ margin: 0, fontSize: 13, color: dmColors.textMuted, lineHeight: 1.5 }}>
                    No components selected. Check items on the left to preview them here.
                  </p>
                </div>
              ) : (
                <DatamartReportCanvas
                  layout={canvasLayout}
                  editable
                  onLayoutChange={handleCanvasLayoutChange}
                  renderWidget={(w) => (
                    <div>
                      <div
                        style={{
                          fontSize: 11,
                          fontWeight: 600,
                          color: dmColors.text,
                          marginBottom: 6,
                        }}
                      >
                        {widgetLabel(w, scenarios)}
                      </div>
                      {renderPreview(w)}
                    </div>
                  )}
                />
              )}
            </div>
          </div>
        </div>

        <footer
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            gap: 10,
            padding: `${dmSpace.md}px ${dmSpace.lg}px`,
            borderTop: `1px solid ${dmColors.border}`,
            background: dmColors.surface,
            flexShrink: 0,
          }}
        >
          <button type="button" onClick={onClose} style={secondaryBtn} disabled={exporting}>
            Cancel
          </button>
          <span style={{ flex: 1, minWidth: 8 }} />
          <button
            type="button"
            disabled={exporting || includedCount === 0}
            onClick={() => void runExport('csv')}
            style={primaryBtn(dmColors.brand, dmColors.brandMuted)}
          >
            {exporting ? (
              <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} />
            ) : (
              <FileSpreadsheet size={14} />
            )}
            {dmCopy.exportComposer.exportCsv}
          </button>
          <button
            type="button"
            disabled={exporting || includedCount === 0}
            onClick={() => void runExport('pdf')}
            style={primaryBtn('#dc2626', '#fef2f2')}
          >
            {exporting ? (
              <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} />
            ) : (
              <FileText size={14} />
            )}
            {dmCopy.exportComposer.exportPdf}
          </button>
        </footer>
      </div>
    </div>,
    document.body,
  )
}

const linkBtn: React.CSSProperties = {
  fontSize: 11,
  fontWeight: 600,
  color: '#0d9488',
  background: 'none',
  border: 'none',
  cursor: 'pointer',
  padding: '2px 4px',
}

const secondaryBtn: React.CSSProperties = {
  fontSize: 13,
  fontWeight: 500,
  padding: '8px 16px',
  borderRadius: dmRadius.md,
  border: `1px solid ${dmColors.border}`,
  background: dmColors.surface,
  color: dmColors.text,
  cursor: 'pointer',
}

function primaryBtn(color: string, bg: string): React.CSSProperties {
  return {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    fontSize: 13,
    fontWeight: 600,
    padding: '8px 16px',
    borderRadius: dmRadius.md,
    border: 'none',
    background: bg,
    color,
    cursor: 'pointer',
  }
}

export default ExportComposerModal
