/**
 * DatamartMessage — thin wrapper around the report card for one assistant turn.
 */
import React from 'react'
import type { DatamartResponse } from '../../../services/datamartService'
import {
  useDatamartReportModel,
  type ReportChartActions,
  type ReportSnapshot,
  type UseDatamartReportModelOptions,
} from '../hooks/useDatamartReportModel'
import DatamartReportCard from '../report/DatamartReportCard'

export interface DatamartMessageProps {
  data: DatamartResponse
  messageId?: string
  sessionId?: string
  templateId?: string
  versionId?: string
  templateMode?: boolean
  /** Template mode: chart edits stay local until saveTemplateVersion. */
  onTemplateChartsChange?: (charts: unknown[]) => void
  /** When true with templateMode, Run query uses data.sql via executeTemplateVersionSql. */
  runSqlFromData?: boolean
  /** Draft preview: layout edits merge into pending draft (no PATCH on saved version). */
  onDraftLayoutChange?: UseDatamartReportModelOptions['onDraftLayoutChange']
  sectionPersistScope?: string
  hydrateResultsFromApi?: boolean
  isLatestTurn?: boolean
  onPromotedToTemplate?: (templateId: string, templateName: string) => void
  onChartConfigsChange?: (messageId: string, chartConfigs: unknown[]) => void
  onAskAgent?: (instruction: string) => void
  onReportSnapshot?: (snapshot: ReportSnapshot) => void
  onRegisterChartActions?: (actions: ReportChartActions | null) => void
  canUndoModification?: boolean
  undoingModification?: boolean
  onUndoModification?: () => void
  /** Re-run the user question for this turn (modify / scenario / new modes preserved). */
  onRetryTurn?: () => void
}

const DatamartMessage: React.FC<DatamartMessageProps> = (props) => {
  const model = useDatamartReportModel(props)
  return <DatamartReportCard model={model} />
}

export default DatamartMessage
