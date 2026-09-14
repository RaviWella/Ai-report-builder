/**
 * Execute primary SQL and all extra_result_blocks for one report turn.
 */
import type { DatamartResponse, SqlExecuteResponse } from '../../../services/datamartService'
import { datamartService } from '../../../services/datamartService'

export interface RunScenarioQueriesContext {
  data: DatamartResponse
  sessionId?: string
  messageId?: string
  templateId?: string
  versionId?: string
  isTemplateReport: boolean
  primarySqlOverride?: { sql: string }
}

export interface RunScenarioQueriesResult {
  primary: SqlExecuteResponse | null
  blocks: Record<string, SqlExecuteResponse>
  firstError: string | null
}

export async function runAllScenarioQueries(
  ctx: RunScenarioQueriesContext,
): Promise<RunScenarioQueriesResult> {
  const { data, isTemplateReport, primarySqlOverride } = ctx
  const extraBlocks = (data.extra_result_blocks ?? []).filter((b) => b.sql?.trim())
  const hasPrimary = !!data.sql?.trim()

  let primary: SqlExecuteResponse | null = null
  const blocks: Record<string, SqlExecuteResponse> = {}
  let firstError: string | null = null

  const runPrimary = async (): Promise<void> => {
    if (!hasPrimary) return
    if (isTemplateReport) {
      if (!ctx.templateId || !ctx.versionId) return
      primary = await datamartService.executeTemplateVersionSql(
        ctx.templateId,
        ctx.versionId,
        primarySqlOverride,
      )
    } else {
      if (!ctx.sessionId || !ctx.messageId) return
      primary = await datamartService.executeMessageSql(
        ctx.sessionId,
        ctx.messageId,
        primarySqlOverride,
      )
    }
    if (primary?.error && !firstError) firstError = primary.error
  }

  const runExtra = async (blockId: string): Promise<void> => {
    let result: SqlExecuteResponse
    if (isTemplateReport) {
      if (!ctx.templateId || !ctx.versionId) return
      result = await datamartService.executeTemplateVersionBlock(
        ctx.templateId,
        ctx.versionId,
        blockId,
      )
    } else {
      if (!ctx.sessionId || !ctx.messageId) return
      result = await datamartService.executeMessageBlock(
        ctx.sessionId,
        ctx.messageId,
        blockId,
      )
    }
    if (result.error) {
      if (!firstError) firstError = result.error
    } else {
      blocks[blockId] = result
    }
  }

  await Promise.all([
    runPrimary(),
    ...extraBlocks.map((b) => runExtra(b.block_id)),
  ])

  return { primary, blocks, firstError }
}
