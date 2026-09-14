/**
 * Right pane: shared report card for one template version.
 */
import React from 'react'
import type { TemplateVersionResponse } from '../../../services/datamartService'
import {
  useTemplateReportModel,
} from '../hooks/useTemplateReportModel'
import type { ReportChartActions, ReportSnapshot } from '../hooks/useDatamartReportModel'
import DatamartReportCard from '../report/DatamartReportCard'
import { dmSpace } from '../lib/tokens'

export interface TemplateReportPaneProps {
  templateId: string
  version: TemplateVersionResponse
  templateName?: string
  onAskAgent: (instruction: string) => void
  onChartsChange: (charts: unknown[]) => void
  onReportSnapshot?: (snapshot: ReportSnapshot) => void
  onRegisterChartActions?: (actions: ReportChartActions | null) => void
}

const TemplateReportPane: React.FC<TemplateReportPaneProps> = ({
  templateId,
  version,
  templateName,
  onAskAgent,
  onChartsChange,
  onReportSnapshot,
  onRegisterChartActions,
}) => {
  const model = useTemplateReportModel({
    templateId,
    version,
    templateName,
    onAskAgent,
    onChartsChange,
    onReportSnapshot,
    onRegisterChartActions,
  })

  return (
    <div style={{ padding: dmSpace.lg, minWidth: 0 }}>
      <DatamartReportCard model={model} />
    </div>
  )
}

export default TemplateReportPane
