/**
 * Right-pane preview of an unsaved template modification (SQL + sections, run before save).
 */
import React, { useMemo } from 'react'
import type { DatamartResponse } from '../../../services/datamartService'
import DatamartMessage from '../components/DatamartMessage'
import type {
  ReportChartActions,
  ReportSnapshot,
  UseDatamartReportModelOptions,
} from '../hooks/useDatamartReportModel'
import { dmCopy } from '../lib/copy'
import { dmColors, dmRadius, dmSpace } from '../lib/tokens'

export interface TemplateDraftPreviewProps {
  templateId: string
  /** Latest saved version id — template execute / block APIs require a version. */
  versionId: string
  draft: DatamartResponse
  onDismiss: () => void
  onAskAgent: (instruction: string) => void
  onChartsChange?: (charts: unknown[]) => void
  onDraftLayoutChange?: UseDatamartReportModelOptions['onDraftLayoutChange']
  onReportSnapshot?: (snapshot: ReportSnapshot) => void
  onRegisterChartActions?: (actions: ReportChartActions | null) => void
}

const TemplateDraftPreview: React.FC<TemplateDraftPreviewProps> = ({
  templateId,
  versionId,
  draft,
  onDismiss,
  onAskAgent,
  onChartsChange,
  onDraftLayoutChange,
  onReportSnapshot,
  onRegisterChartActions,
}) => {
  const hydrateResultsFromApi = useMemo(
    () => draft.columns.length > 0 && draft.rows.length > 0,
    [draft.columns.length, draft.rows.length],
  )

  return (
    <div style={{ padding: dmSpace.lg }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          gap: dmSpace.md,
          marginBottom: dmSpace.md,
          padding: '10px 14px',
          borderRadius: dmRadius.md,
          background: dmColors.purpleBg,
          border: `1px solid ${dmColors.purpleBorder}`,
        }}
      >
        <div>
          <p style={{ margin: 0, fontSize: 13, fontWeight: 600, color: '#5b21b6' }}>
            {dmCopy.template.draftPreviewTitle}
          </p>
          <p style={{ margin: '4px 0 0', fontSize: 12, color: '#6d28d9', lineHeight: 1.5 }}>
            {dmCopy.template.draftPreviewBody}
          </p>
        </div>
        <button
          type="button"
          onClick={onDismiss}
          aria-label={dmCopy.template.dismissDraft}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            fontSize: 18,
            color: dmColors.purple,
            lineHeight: 1,
          }}
        >
          ×
        </button>
      </div>
      <DatamartMessage
        data={draft}
        templateId={templateId}
        versionId={versionId}
        templateMode
        runSqlFromData
        sectionPersistScope={`tpl-draft:${templateId}:${versionId}`}
        hydrateResultsFromApi={hydrateResultsFromApi}
        onTemplateChartsChange={onChartsChange}
        onDraftLayoutChange={onDraftLayoutChange}
        onAskAgent={onAskAgent}
        onReportSnapshot={onReportSnapshot}
        onRegisterChartActions={onRegisterChartActions}
      />
    </div>
  )
}

export default TemplateDraftPreview
