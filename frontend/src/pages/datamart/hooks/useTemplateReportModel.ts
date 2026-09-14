/**
 * Report model for a saved template version — delegates to useDatamartReportModel.
 */
import { useMemo } from 'react'
import type { TemplateVersionResponse } from '../../../services/datamartService'
import { templateVersionToReport } from '../templates/versionToReport'
import {
  useDatamartReportModel,
  type DatamartReportModel,
  type ReportChartActions,
  type ReportSnapshot,
} from './useDatamartReportModel'

export interface UseTemplateReportModelOptions {
  templateId: string
  version: TemplateVersionResponse
  templateName?: string
  onAskAgent?: (instruction: string) => void
  /** Called when user edits charts locally (included on next version save). */
  onChartsChange?: (charts: unknown[]) => void
  onReportSnapshot?: (snapshot: ReportSnapshot) => void
  onRegisterChartActions?: (actions: ReportChartActions | null) => void
}

export function useTemplateReportModel({
  templateId,
  version,
  templateName,
  onAskAgent,
  onChartsChange,
  onReportSnapshot,
  onRegisterChartActions,
}: UseTemplateReportModelOptions): DatamartReportModel {
  const data = useMemo(
    () => templateVersionToReport(version, templateName),
    [version, templateName],
  )

  return useDatamartReportModel({
    data,
    templateId,
    versionId: version.id,
    sectionPersistScope: `tpl:${templateId}:${version.id}`,
    onAskAgent,
    onTemplateChartsChange: onChartsChange,
    onReportSnapshot,
    onRegisterChartActions,
    templateMode: true,
  })
}
