/**
 * Report execution state for a single datamart turn (chat or template).
 */
import type { DatamartResponse, SqlExecuteResponse } from '../../../services/datamartService'
import { dmCopy } from '../lib/copy'

export type ReportRunStatus = 'idle' | 'running' | 'ready' | 'error'

export interface ReportRunState {
  status: ReportRunStatus
  /** User clicked Run / Re-run at least once this session. */
  hasUserRun: boolean
  rowCount: number
  error: string | null
}

export interface DeriveReportRunInput {
  data: DatamartResponse
  runResult: SqlExecuteResponse | null
  running: boolean
  runError: string | null
  /** When true, show rows returned on the latest chat turn (not on session reload). */
  hydrateFromApi?: boolean
}

export function deriveReportRunState({
  data,
  runResult,
  running,
  runError,
  hydrateFromApi = false,
}: DeriveReportRunInput): ReportRunState {
  const hasApiResults =
    hydrateFromApi && data.columns.length > 0
  const executed = runResult && !runResult.error
  const tableColumns = hasApiResults
    ? data.columns
    : executed || runResult
      ? runResult!.columns
      : []
  const hasTable = tableColumns.length > 0

  if (running) {
    return {
      status: 'running',
      hasUserRun: true,
      rowCount: 0,
      error: null,
    }
  }

  if (runError && !hasTable) {
    return {
      status: 'error',
      hasUserRun: true,
      rowCount: 0,
      error: runError,
    }
  }

  if (hasTable) {
    const tableRowCount = hasApiResults
      ? data.row_count
      : (runResult?.row_count ?? 0)
    return {
      status: 'ready',
      hasUserRun: hasApiResults || !!runResult,
      rowCount: tableRowCount,
      error: runError,
    }
  }

  return {
    status: 'idle',
    hasUserRun: !!runResult,
    rowCount: 0,
    error: null,
  }
}

export type ReportStatusBadge =
  | 'no_sql'
  | 'text_only'
  | 'ready'
  | 'not_loaded'
  | 'running'
  | 'error'
  | 'pipeline_error'

export function deriveStatusBadge(
  data: DatamartResponse,
  run: ReportRunState,
  hasError: boolean,
): ReportStatusBadge {
  if (hasError && !data.sql) return 'pipeline_error'
  if (!data.sql && data.narrative) return 'text_only'
  if (!data.sql) return 'no_sql'
  if (run.status === 'running') return 'running'
  if (run.status === 'error') return 'error'
  if (run.status === 'ready') return 'ready'
  return 'not_loaded'
}

export const STATUS_BADGE_LABEL: Record<ReportStatusBadge, string> = dmCopy.statusBadge
