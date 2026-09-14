/**
 * Per-scenario narrative, validation, and pipeline trace for multi-scenario reports.
 */
import type {
  DatamartResponse,
  DatamartValidation,
} from '../../../services/datamartService'
import type { DatamartReportLayoutV1, ReportPanelId } from './reportLayout'
import { pipelineTraceFromResponse, type PipelineTrace } from './pipelineTrace'
import { normalizeValidation, validationFromResponse } from './validation'

function layoutV1(
  raw: DatamartResponse['report_layout'],
): DatamartReportLayoutV1 | null {
  if (!raw || typeof raw !== 'object') return null
  const layout = raw as unknown as DatamartReportLayoutV1
  if (layout.schema_version !== 1) return null
  return layout
}

export function resolvePanelNarrative(
  data: DatamartResponse,
  panelId: ReportPanelId,
): string | undefined {
  const multi = (data.extra_result_blocks?.length ?? 0) > 0
  const layout = layoutV1(data.report_layout)

  if (panelId === 'primary') {
    if (multi && layout?.primary_narrative?.trim()) {
      return layout.primary_narrative.trim()
    }
    return data.narrative?.trim() || undefined
  }

  if (multi) {
    return data.narrative?.trim() || undefined
  }
  return undefined
}

export function resolvePanelPipelineTrace(
  data: DatamartResponse,
  panelId: ReportPanelId,
): PipelineTrace | null {
  const multi = (data.extra_result_blocks?.length ?? 0) > 0

  if (panelId !== 'primary') {
    const blk = data.extra_result_blocks?.find((b) => b.block_id === panelId)
    if (blk?.pipeline_trace?.steps?.length) return blk.pipeline_trace
  }

  if (multi && panelId === 'primary') {
    const anyBlockTrace = data.extra_result_blocks?.some(
      (b) => (b.pipeline_trace?.steps?.length ?? 0) > 0,
    )
    if (!anyBlockTrace) return pipelineTraceFromResponse(data)
    return null
  }

  return pipelineTraceFromResponse(data)
}

export function resolvePanelValidation(
  data: DatamartResponse,
  panelId: ReportPanelId,
): DatamartValidation | null {
  const multi = (data.extra_result_blocks?.length ?? 0) > 0
  const top = validationFromResponse(data)

  if (panelId !== 'primary') {
    const blk = data.extra_result_blocks?.find((b) => b.block_id === panelId)
    const blockVal = blk?.validation
    if (blockVal && typeof blockVal === 'object') {
      return (
        normalizeValidation(blockVal as unknown as DatamartValidation) ??
        top
      )
    }
    return top
  }

  if (multi) {
    const hasBlockValidation = data.extra_result_blocks?.some((b) => b.validation)
    if (!hasBlockValidation) return top
    return null
  }

  return top
}

export function primaryScenarioUnchangedNote(multi: boolean, panelId: ReportPanelId): string | null {
  if (!multi || panelId !== 'primary') return null
  return 'Primary scenario data is unchanged from your earlier question. Select an added scenario tab to see validation and the agent pathway for your latest question.'
}
