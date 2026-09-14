/**
 * Maps a saved template version to the shared DatamartResponse report shape.
 */
import type {
  DatamartResponse,
  DatamartResultBlock,
  TemplateExtraBlockMeta,
  TemplateVersionResponse,
} from '../../../services/datamartService'

function extraMetaToResultBlock(meta: TemplateExtraBlockMeta): DatamartResultBlock {
  return {
    block_id: meta.block_id,
    title: meta.title ?? null,
    narrative: '',
    sql: meta.sql_script ?? null,
    post_process_config: meta.post_process_config ?? null,
    columns: [],
    rows: [],
    row_count: 0,
    raw_columns: null,
    raw_rows: null,
    raw_row_count: null,
    error: null,
  }
}

/** Convert API/runtime blocks to metadata saved on a new template version. */
export function extraBlocksToSavePayload(
  blocks: DatamartResultBlock[] | null | undefined,
): TemplateExtraBlockMeta[] | null {
  if (!blocks?.length) return null
  const out: TemplateExtraBlockMeta[] = []
  for (const b of blocks) {
    const sql = b.sql?.trim()
    if (!sql) continue
    out.push({
      block_id: b.block_id,
      title: b.title ?? null,
      sql_script: sql,
      post_process_config: b.post_process_config ?? null,
    })
  }
  return out.length ? out : null
}

export function templateVersionToReport(
  version: TemplateVersionResponse,
  templateName?: string,
): DatamartResponse {
  const extraBlocks =
    version.extra_result_blocks?.map(extraMetaToResultBlock) ?? null

  return {
    question: version.label?.trim() || templateName || `Version ${version.version_num}`,
    narrative: version.narrative ?? '',
    sql: version.sql_script ?? null,
    post_process_config: version.post_process_config ?? null,
    chart_configs: version.chart_configs ?? null,
    columns: [],
    rows: [],
    row_count: 0,
    error: null,
    session_id: version.source_session_id,
    message_id: version.source_message_id,
    extra_result_blocks: extraBlocks,
    report_layout: version.report_layout ?? null,
  }
}
