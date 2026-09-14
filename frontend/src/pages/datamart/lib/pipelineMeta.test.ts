import { describe, expect, it } from 'vitest'
import { formatPipelineMetaLine } from './pipelineMeta'

describe('formatPipelineMetaLine', () => {
  it('joins domain tier and source', () => {
    const line = formatPipelineMetaLine({
      domain: 'recruitment',
      sql_tier: 'A',
      sql_source: 'recruitment_pipeline_template',
    })
    expect(line).toContain('recruitment')
    expect(line).toContain('Tier A')
    expect(line).toContain('recruitment_pipeline_template')
  })
})
