/**
 * Merge assistant message fields from API refresh (charts, extra blocks, layout).
 * Preserves in-memory SQL result rows — session messages do not store executed data.
 */
import type { DatamartResponse, MessageResponse } from '../../../services/datamartService'

export interface ChatMessageWithData {
  messageId?: string
  role: string
  data?: DatamartResponse | null
}

function mergeExtraBlocks(
  existing: DatamartResponse['extra_result_blocks'],
  apiBlocks: MessageResponse['extra_result_blocks'],
): DatamartResponse['extra_result_blocks'] {
  if (!apiBlocks?.length) return existing ?? null

  const existingById = new Map(
    (existing ?? []).map((b) => [b.block_id, b]),
  )

  return apiBlocks.map((apiBlk) => {
    const blockId = String(apiBlk.block_id ?? '')
    const prev = existingById.get(blockId)
    const hasPrevRows = !!(prev && prev.columns.length > 0 && prev.rows.length > 0)

    return {
      block_id: blockId,
      title: apiBlk.title ?? prev?.title ?? null,
      sql: apiBlk.sql_script ?? prev?.sql ?? null,
      post_process_config: Array.isArray(apiBlk.post_process_config)
        ? apiBlk.post_process_config
        : (prev?.post_process_config ?? null),
      narrative: prev?.narrative ?? '',
      columns: hasPrevRows ? prev!.columns : (prev?.columns ?? []),
      rows: hasPrevRows ? prev!.rows : (prev?.rows ?? []),
      row_count: hasPrevRows ? prev!.row_count : (prev?.row_count ?? 0),
      raw_columns: hasPrevRows ? prev!.raw_columns : (prev?.raw_columns ?? null),
      raw_rows: hasPrevRows ? prev!.raw_rows : (prev?.raw_rows ?? null),
      raw_row_count: hasPrevRows ? prev!.raw_row_count : (prev?.raw_row_count ?? null),
      error: prev?.error ?? null,
      validation: prev?.validation ?? null,
      pipeline_trace: prev?.pipeline_trace ?? null,
    }
  })
}

export function mergeAssistantMessagesFromApi<T extends ChatMessageWithData>(
  messages: T[],
  apiMessages: MessageResponse[],
): T[] {
  const apiById = new Map<string, MessageResponse>()
  for (const m of apiMessages) {
    if (m.role === 'assistant') apiById.set(m.id, m)
  }

  return messages.map((msg) => {
    if (msg.role !== 'assistant' || !msg.messageId || !msg.data) return msg
    const api = apiById.get(msg.messageId)
    if (!api) return msg

    const charts =
      Array.isArray(api.chart_configs) && api.chart_configs.length > 0
        ? api.chart_configs
        : msg.data.chart_configs

    const extras = api.extra_result_blocks?.length
      ? mergeExtraBlocks(msg.data.extra_result_blocks, api.extra_result_blocks)
      : msg.data.extra_result_blocks

    const reportLayout = api.report_layout ?? msg.data.report_layout

    const validationRaw =
      (api as MessageResponse & { validation?: DatamartResponse['validation'] })
        .validation ?? msg.data.validation
    const validation = validationRaw ?? msg.data.validation
    const storedTrace =
      validationRaw &&
      typeof validationRaw === 'object' &&
      'pipeline_trace' in validationRaw
        ? (validationRaw as { pipeline_trace?: DatamartResponse['pipeline_trace'] })
            .pipeline_trace
        : null
    const storedMeta =
      validationRaw &&
      typeof validationRaw === 'object' &&
      'pipeline_meta' in validationRaw
        ? (validationRaw as { pipeline_meta?: DatamartResponse['pipeline_meta'] })
            .pipeline_meta
        : null

    return {
      ...msg,
      data: {
        ...msg.data,
        chart_configs: charts ?? null,
        extra_result_blocks: extras ?? msg.data.extra_result_blocks,
        report_layout: reportLayout ?? msg.data.report_layout,
        validation: validation ?? msg.data.validation,
        pipeline_trace:
          msg.data.pipeline_trace ?? storedTrace ?? null,
        pipeline_meta: msg.data.pipeline_meta ?? storedMeta ?? null,
      },
    }
  })
}
