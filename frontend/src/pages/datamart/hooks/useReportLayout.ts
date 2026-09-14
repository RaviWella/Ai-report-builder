/**
 * Scenario list + canvas layout state for one assistant report.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { DatamartResponse } from '../../../services/datamartService'
import { datamartService } from '../../../services/datamartService'
import {
  buildDefaultReportLayout,
  buildScenarioList,
  ensureReportCanvasLayout,
  normalizeReportLayout,
  type DatamartReportLayoutV1,
  type ReportLayoutPersistPatch,
  type ReportLayoutWidget,
  type ReportPanelId,
} from '../lib/reportLayout'

export type { ReportLayoutPersistPatch } from '../lib/reportLayout'

export function useReportLayout({
  data,
  messageId,
  sessionId,
  templateId,
  versionId,
  hasSummary,
  disablePersist = false,
  onLocalLayoutChange,
}: {
  data: DatamartResponse
  messageId?: string
  sessionId?: string
  templateId?: string
  versionId?: string
  hasSummary: boolean
  /** When true, layout edits stay local (e.g. template draft preview before save). */
  disablePersist?: boolean
  onLocalLayoutChange?: (patch: ReportLayoutPersistPatch) => void
}) {
  const [layout, setLayout] = useState<DatamartReportLayoutV1>(() => {
    const initialScenarios = buildScenarioList(
      (data.report_layout as DatamartReportLayoutV1 | undefined)?.primary_label,
      data.question,
      data.extra_result_blocks?.map((b) => ({ block_id: b.block_id, title: b.title })),
    )
    return normalizeReportLayout(data.report_layout, initialScenarios, hasSummary)
  })

  const scenarios = useMemo(
    () =>
      buildScenarioList(
        layout.primary_label,
        data.question,
        data.extra_result_blocks?.map((b) => ({
          block_id: b.block_id,
          title: b.title,
        })),
      ),
    [layout.primary_label, data.question, data.extra_result_blocks],
  )
  const [activePanelId, setActivePanelId] = useState<ReportPanelId>(
    () => layout.active_panel_id ?? 'primary',
  )
  const persistTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    const next = normalizeReportLayout(data.report_layout, scenarios, hasSummary)
    setLayout(next)
    setActivePanelId(next.active_panel_id ?? 'primary')
  }, [messageId, versionId, data.report_layout, scenarios, hasSummary])

  const schedulePersist = useCallback(
    (patch: ReportLayoutPersistPatch) => {
      if (disablePersist) {
        onLocalLayoutChange?.(patch)
        return
      }
      const persistTarget =
        templateId && versionId
          ? { kind: 'template' as const, templateId, versionId }
          : messageId && sessionId
            ? { kind: 'message' as const, sessionId, messageId }
            : null
      if (!persistTarget) return
      if (persistTimer.current) clearTimeout(persistTimer.current)
      persistTimer.current = setTimeout(async () => {
        const apiPatch = {
          ...patch,
          report_layout: patch.report_layout as Record<string, unknown> | undefined,
        }
        try {
          if (persistTarget.kind === 'template') {
            await datamartService.patchTemplateVersionReportMeta(
              persistTarget.templateId,
              persistTarget.versionId,
              apiPatch,
            )
          } else {
            await datamartService.patchReportMeta(
              persistTarget.sessionId,
              persistTarget.messageId,
              apiPatch,
            )
          }
        } catch {
          /* non-blocking */
        }
      }, 450)
    },
    [disablePersist, messageId, onLocalLayoutChange, sessionId, templateId, versionId],
  )

  const updateLayout = useCallback(
    (widgets: ReportLayoutWidget[]) => {
      setLayout((prev) => {
        const next = ensureReportCanvasLayout(
          { ...prev, widgets },
          scenarios,
          hasSummary,
        )
        schedulePersist({ report_layout: next })
        return next
      })
    },
    [schedulePersist, scenarios, hasSummary],
  )

  const setViewMode = useCallback(
    (mode: 'stacked' | 'canvas') => {
      setLayout((prev) => {
        const next =
          mode === 'canvas'
            ? ensureReportCanvasLayout({ ...prev, view_mode: 'canvas' }, scenarios, hasSummary)
            : { ...prev, view_mode: mode }
        schedulePersist({ report_layout: next })
        return next
      })
    },
    [schedulePersist, scenarios, hasSummary],
  )

  const renameScenario = useCallback(
    (panelId: ReportPanelId, label: string) => {
      const trimmed = label.trim()
      if (!trimmed) return
      setLayout((prev) => {
        const next =
          panelId === 'primary' ? { ...prev, primary_label: trimmed } : { ...prev }
        schedulePersist({
          report_layout: next,
          ...(panelId === 'primary'
            ? { primary_label: trimmed }
            : { block_labels: { [panelId]: trimmed } }),
        })
        return next
      })
    },
    [schedulePersist],
  )

  const setActivePanel = useCallback(
    (panelId: ReportPanelId) => {
      setActivePanelId(panelId)
      setLayout((prev) => {
        const next = { ...prev, active_panel_id: panelId }
        schedulePersist({ report_layout: next })
        return next
      })
    },
    [schedulePersist],
  )

  const resetLayout = useCallback(() => {
    const fresh = buildDefaultReportLayout(scenarios, hasSummary)
    setLayout(fresh)
    schedulePersist({ report_layout: fresh })
  }, [hasSummary, scenarios, schedulePersist])

  const multiScenario = scenarios.length > 1

  const canvasLayout = useMemo(
    () => ensureReportCanvasLayout(layout, scenarios, hasSummary),
    [layout, scenarios, hasSummary],
  )

  return {
    scenarios,
    layout,
    canvasLayout,
    multiScenario,
    activePanelId,
    setActivePanel,
    updateLayout,
    setViewMode,
    renameScenario,
    resetLayout,
    canvasMode: layout.view_mode === 'canvas',
  }
}
