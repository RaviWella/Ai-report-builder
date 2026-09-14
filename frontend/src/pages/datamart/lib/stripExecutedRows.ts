/**
 * Remove executed row payloads from a datamart response so the UI only shows
 * results after the user clicks Run query (UX: manual run, no auto-hydrate).
 */
import type { DatamartResponse } from '../../../services/datamartService'

export function stripExecutedRows(response: DatamartResponse): DatamartResponse {
  return {
    ...response,
    columns: [],
    rows: [],
    row_count: 0,
    raw_columns: null,
    raw_rows: null,
    raw_row_count: null,
    extra_result_blocks:
      response.extra_result_blocks?.map((block) => ({
        ...block,
        columns: [],
        rows: [],
        row_count: 0,
        raw_columns: null,
        raw_rows: null,
        raw_row_count: null,
      })) ?? null,
  }
}
