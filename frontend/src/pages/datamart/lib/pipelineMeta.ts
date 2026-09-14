/**
 * S5/S6 pipeline turn metadata (mirrors backend PipelineTurnMeta).
 */
import type { DatamartResponse, PipelineTurnMeta } from '../../../services/datamartService'

type ValidationWithMeta = DatamartResponse['validation'] & {
  pipeline_meta?: PipelineTurnMeta | null
}

export function pipelineMetaFromResponse(
  data: DatamartResponse | null | undefined,
): PipelineTurnMeta | null {
  if (!data) return null
  if (data.pipeline_meta) return data.pipeline_meta
  const nested = (data.validation as ValidationWithMeta | null | undefined)
    ?.pipeline_meta
  return nested ?? null
}

export function formatPipelineMetaLine(meta: PipelineTurnMeta): string {
  const parts: string[] = []
  if (meta.domain) parts.push(`Domain: ${meta.domain}`)
  if (meta.sql_tier) parts.push(`Tier ${meta.sql_tier}`)
  if (meta.sql_source) parts.push(meta.sql_source)
  return parts.join(' · ')
}
