/**
 * Agent pipeline trace (mirrors backend pipeline_trace.py).
 */
import type { DatamartResponse } from '../../../services/datamartService'

export type PipelineStepStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'warning'
  | 'failed'
  | 'skipped'
  | 'blocked'

export interface PipelineStep {
  id: string
  label: string
  status: PipelineStepStatus
  detail?: string | null
  duration_ms?: number | null
}

export interface RecoveryEvent {
  attempt: number
  phase: string
  issue: string
  action: string
  detail: string
  user_message: string
}

export interface PipelineTrace {
  steps: PipelineStep[]
  repair_attempts_used: number
  repair_attempts_max: number
  recovery_events?: RecoveryEvent[]
}

type ValidationWithTrace = DatamartResponse['validation'] & {
  pipeline_trace?: PipelineTrace
}

/** @deprecated Import from `pipelineStepCatalog` — kept for older imports. */
export { CHAT_LOADING_PIPELINE_LABELS } from './pipelineStepCatalog'

export function pipelineTraceFromResponse(
  data: DatamartResponse | null | undefined,
): PipelineTrace | null {
  if (!data) return null
  const top = (data as DatamartResponse & { pipeline_trace?: PipelineTrace })
    .pipeline_trace
  if (top?.steps?.length) return top
  const nested = (data.validation as ValidationWithTrace | null | undefined)
    ?.pipeline_trace
  if (nested?.steps?.length) return nested
  return null
}
