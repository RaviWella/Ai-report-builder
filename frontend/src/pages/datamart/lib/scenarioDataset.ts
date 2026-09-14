/**
 * Resolve tabular data for one extra_result_blocks entry (API snapshot or live run).
 */
import type { DatamartResultBlock, SqlExecuteResponse } from '../../../services/datamartService'

export interface ResolvedScenarioDataset {
  columns: string[]
  rows: unknown[][]
  raw_columns: string[] | null
  raw_rows: unknown[][] | null
  hasData: boolean
}

export function resolveExtraBlockDataset(
  block: DatamartResultBlock,
  blockSqlResults: Record<string, SqlExecuteResponse>,
): ResolvedScenarioDataset {
  const live = block.columns.length > 0
  const ex = blockSqlResults[block.block_id]
  const columns = live ? block.columns : (ex?.columns ?? [])
  const rows = live ? block.rows : (ex?.rows ?? [])
  return {
    columns,
    rows,
    raw_columns: live ? (block.raw_columns ?? null) : (ex?.raw_columns ?? null),
    raw_rows: live ? (block.raw_rows ?? null) : (ex?.raw_rows ?? null),
    hasData: columns.length > 0,
  }
}
