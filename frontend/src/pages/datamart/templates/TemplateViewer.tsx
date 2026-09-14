/**
 * Template workspace: version timeline + modify chat + shared report card.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { FileText } from 'lucide-react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { datamartService, type DatamartResponse } from '../../../services/datamartService'
import { buildSqlChangePrompt } from '../lib/askAgentPrompt'
import { mergeLayoutPatchIntoDraft, type ReportLayoutPersistPatch } from '../lib/reportLayout'
import {
  buildDraftEditingContext,
  buildTemplateEditingContext,
} from '../lib/latestTurnContext'
import type { ReportChartActions, ReportSnapshot } from '../hooks/useDatamartReportModel'
import { dmCopy } from '../lib/copy'
import TemplateVersionTimeline from './TemplateVersionTimeline'
import TemplateModifyPanel from './TemplateModifyPanel'
import TemplateReportPane from './TemplateReportPane'
import TemplateDraftPreview from './TemplateDraftPreview'
import { resolveActiveTemplateVersion } from '../lib/resolveTemplateVersion'
import { dmColors, dmSpace } from '../lib/tokens'

export interface TemplateViewerProps {
  templateId: string
}

const TemplateViewer: React.FC<TemplateViewerProps> = ({ templateId }) => {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [activeVersionId, setActiveVersionId] = useState<string | null>(null)
  const [draftCharts, setDraftCharts] = useState<unknown[]>([])
  const [pendingPreview, setPendingPreview] = useState<DatamartResponse | null>(null)
  const [composerPrefill, setComposerPrefill] = useState<string | null>(null)
  const [reportSnapshot, setReportSnapshot] = useState<ReportSnapshot | null>(null)
  const chartActionsRef = useRef<ReportChartActions | null>(null)

  useQuery({
    queryKey: ['datamart', 'bootstrap'],
    queryFn: () => datamartService.bootstrap(),
    staleTime: 15 * 60 * 1000,
    retry: 1,
  })

  const {
    data: templateData,
    isLoading: templateLoading,
    isError: templateError,
    refetch: refetchTemplate,
  } = useQuery({
    queryKey: ['datamart-template', templateId],
    queryFn: () => datamartService.getTemplate(templateId),
    enabled: Boolean(templateId),
    staleTime: 0,
    refetchOnMount: 'always',
    structuralSharing: false,
  })

  const {
    data: versionsData,
    isLoading: versionsLoading,
    isError: versionsError,
    refetch: refetchVersions,
  } = useQuery({
    queryKey: ['datamart-template-versions', templateId],
    queryFn: () => datamartService.listTemplateVersions(templateId),
    enabled: Boolean(templateId),
    staleTime: 0,
    refetchOnMount: 'always',
    structuralSharing: false,
  })

  // Switching templates via sidebar must not keep stale state from the previous template.
  useEffect(() => {
    setActiveVersionId(null)
    setDraftCharts([])
    setPendingPreview(null)
    setComposerPrefill(null)
    setReportSnapshot(null)
    chartActionsRef.current = null
  }, [templateId])

  const resolvedTemplate = useMemo(
    () => (templateData?.id === templateId ? templateData : undefined),
    [templateData, templateId],
  )

  const staleTemplateCache = Boolean(templateData && templateData.id !== templateId)
  const staleVersionsCache = Boolean(
    versionsData?.versions?.length &&
      versionsData.versions.some((v) => v.template_id !== templateId),
  )

  const versions = useMemo(() => {
    const list = versionsData?.versions ?? []
    return list.filter((v) => v.template_id === templateId)
  }, [versionsData?.versions, templateId])

  const activeVersion = useMemo(
    () =>
      resolveActiveTemplateVersion({
        templateId,
        versions,
        activeVersionId,
        latestFromTemplate: resolvedTemplate?.latest_version,
      }),
    [templateId, versions, activeVersionId, resolvedTemplate?.latest_version],
  )

  const handleVersionSelect = (versionId: string) => {
    setActiveVersionId(versionId)
    setDraftCharts([])
    setPendingPreview(null)
    setReportSnapshot(null)
  }

  const handleVersionSaved = () => {
    void refetchVersions()
    void queryClient.invalidateQueries({ queryKey: ['datamart-templates'] })
    setActiveVersionId(null)
    setDraftCharts([])
    setPendingPreview(null)
    setComposerPrefill(null)
  }

  const handleAskAgentFromReport = (instruction: string) => {
    setComposerPrefill(buildSqlChangePrompt(instruction))
  }

  const handleDraftLayoutChange = useCallback((patch: ReportLayoutPersistPatch) => {
    setPendingPreview((prev) => (prev ? mergeLayoutPatchIntoDraft(prev, patch) : prev))
  }, [])

  const editingContext = useMemo(() => {
    if (pendingPreview?.sql) {
      return buildDraftEditingContext(pendingPreview, reportSnapshot)
    }
    if (activeVersion) {
      return buildTemplateEditingContext(activeVersion, resolvedTemplate?.name, reportSnapshot)
    }
    return null
  }, [pendingPreview, activeVersion, resolvedTemplate?.name, reportSnapshot])

  const loading =
    !templateId ||
    staleTemplateCache ||
    staleVersionsCache ||
    ((templateLoading || versionsLoading) && !activeVersion)

  if (!templateId) {
    return null
  }
  const loadError = templateError || versionsError

  if (loading) {
    return (
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: dmColors.textMuted }}>
        Loading template…
      </div>
    )
  }

  if (loadError && !activeVersion) {
    return (
      <div
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 12,
          padding: 24,
          color: dmColors.textMuted,
        }}
      >
        <p style={{ margin: 0, fontSize: 14 }}>Could not load this template.</p>
        <button
          type="button"
          onClick={() => {
            void refetchTemplate()
            void refetchVersions()
          }}
          style={{
            fontSize: 12,
            fontWeight: 600,
            color: dmColors.purple,
            background: dmColors.purpleBg,
            border: `1px solid ${dmColors.purpleBorder}`,
            borderRadius: 8,
            padding: '8px 14px',
            cursor: 'pointer',
          }}
        >
          Retry
        </button>
        <button
          type="button"
          onClick={() => navigate('/datamart/chat')}
          style={{
            fontSize: 12,
            color: dmColors.textSubtle,
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            textDecoration: 'underline',
          }}
        >
          Back to chat
        </button>
      </div>
    )
  }

  if (!activeVersion) {
    return (
      <div
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 8,
          padding: 24,
          color: dmColors.textMuted,
        }}
      >
        <p style={{ margin: 0, fontSize: 14 }}>This template has no saved versions yet.</p>
        <button
          type="button"
          onClick={() => navigate('/datamart/chat')}
          style={{
            fontSize: 12,
            color: dmColors.textSubtle,
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            textDecoration: 'underline',
          }}
        >
          Back to chat
        </button>
      </div>
    )
  }

  return (
    <div
      style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minHeight: 0 }}
    >
      <header
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          padding: '14px 20px',
          borderBottom: `1px solid ${dmColors.border}`,
          background: dmColors.surface,
          flexShrink: 0,
        }}
      >
        <FileText size={18} color={dmColors.purple} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <h1
            data-testid="datamart-template-title"
            data-template-id={templateId}
            style={{ margin: 0, fontSize: 16, fontWeight: 700, color: dmColors.text }}
          >
            {resolvedTemplate?.name ?? 'Template'}
          </h1>
          <p style={{ margin: 0, fontSize: 11, color: dmColors.textSubtle }}>
            {versions.length} version{versions.length === 1 ? '' : 's'} · Run query to load results
          </p>
        </div>
        <button
          type="button"
          onClick={() => navigate('/datamart/chat')}
          style={{
            fontSize: 12,
            fontWeight: 600,
            color: dmColors.textMuted,
            background: dmColors.surfaceMuted,
            border: `1px solid ${dmColors.border}`,
            borderRadius: 8,
            padding: '6px 12px',
            cursor: 'pointer',
          }}
        >
          Back to chat
        </button>
      </header>

      <div style={{ flex: 1, display: 'flex', overflow: 'hidden', minHeight: 0 }}>
        <TemplateVersionTimeline
          versions={versions}
          activeVersionId={activeVersion.id}
          onSelectVersion={handleVersionSelect}
        />

        <div className="template-workspace-main">
          <TemplateModifyPanel
            templateId={templateId}
            versionId={activeVersion.id}
            chartConfigsForSave={draftCharts}
            pendingDraft={pendingPreview}
            editingContext={editingContext}
            composerPrefill={composerPrefill}
            onDismissComposerPrefill={() => setComposerPrefill(null)}
            onVersionSaved={handleVersionSaved}
            onPendingResult={setPendingPreview}
            onAddChart={() => chartActionsRef.current?.openChartModal()}
          />

          <div
            className="template-workspace-report"
            style={{ overflowY: 'auto', background: dmColors.surfaceMuted, minWidth: 0 }}
          >
            {composerPrefill && !pendingPreview && (
              <div
                style={{
                  margin: dmSpace.lg,
                  marginBottom: 0,
                  padding: '8px 12px',
                  borderRadius: 8,
                  background: dmColors.purpleBg,
                  border: `1px solid ${dmColors.purpleBorder}`,
                  fontSize: 12,
                  color: '#5b21b6',
                  display: 'flex',
                  justifyContent: 'space-between',
                  gap: 8,
                }}
              >
                <span>{dmCopy.template.modifyPanelHint}</span>
                <button
                  type="button"
                  onClick={() => setComposerPrefill(null)}
                  aria-label="Dismiss"
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: dmColors.purple }}
                >
                  ×
                </button>
              </div>
            )}

            {pendingPreview ? (
              <TemplateDraftPreview
                templateId={templateId}
                versionId={activeVersion.id}
                draft={pendingPreview}
                onDismiss={() => {
                  setPendingPreview(null)
                  setReportSnapshot(null)
                }}
                onAskAgent={handleAskAgentFromReport}
                onChartsChange={setDraftCharts}
                onDraftLayoutChange={handleDraftLayoutChange}
                onReportSnapshot={setReportSnapshot}
                onRegisterChartActions={(actions) => {
                  chartActionsRef.current = actions
                }}
              />
            ) : (
              <TemplateReportPane
                key={`${templateId}:${activeVersion.id}`}
                templateId={templateId}
                version={activeVersion}
                templateName={resolvedTemplate?.name}
                onAskAgent={handleAskAgentFromReport}
                onChartsChange={setDraftCharts}
                onReportSnapshot={setReportSnapshot}
                onRegisterChartActions={(actions) => {
                  chartActionsRef.current = actions
                }}
              />
            )}
          </div>
        </div>
      </div>
      <style>{`
        .template-workspace-main {
          flex: 1;
          display: flex;
          flex-direction: row;
          min-width: 0;
          overflow: hidden;
        }
        .template-workspace-report {
          flex: 1;
          min-width: 0;
        }
        @media (max-width: 1200px) {
          .template-workspace-main {
            flex-direction: column;
            overflow-y: auto;
          }
          .template-modify-panel {
            max-width: none !important;
            width: 100% !important;
            border-right: none !important;
            border-bottom: 1px solid ${dmColors.border};
            max-height: 42vh;
          }
          .template-workspace-report {
            flex: 1;
            min-height: 50vh;
          }
        }
      `}</style>
    </div>
  )
}

export default TemplateViewer
