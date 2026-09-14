import { describe, expect, it } from 'vitest'
import {
  extraBlocksToSavePayload,
  templateVersionToReport,
} from './versionToReport'
import type { TemplateVersionResponse } from '../../../services/datamartService'

const baseVersion: TemplateVersionResponse = {
  id: 'v1',
  template_id: 't1',
  version_num: 1,
  label: 'Q1 headcount',
  sql_script: 'SELECT 1',
  post_process_config: null,
  chart_configs: [{ id: 'c1' }],
  extra_result_blocks: [
    {
      block_id: 'blk-a',
      title: 'Scenario 2',
      sql_script: 'SELECT 2',
      post_process_config: null,
    },
  ],
  report_layout: { schema_version: 1, view_mode: 'stacked', widgets: [] },
  narrative: 'Summary text',
  source_session_id: null,
  source_message_id: null,
  is_latest: true,
  created_at: '2026-01-01T00:00:00Z',
}

describe('templateVersionToReport', () => {
  it('maps extra blocks and report layout', () => {
    const report = templateVersionToReport(baseVersion, 'My template')
    expect(report.sql).toBe('SELECT 1')
    expect(report.report_layout?.view_mode).toBe('stacked')
    expect(report.extra_result_blocks).toHaveLength(1)
    expect(report.extra_result_blocks?.[0].sql).toBe('SELECT 2')
    expect(report.extra_result_blocks?.[0].columns).toEqual([])
  })
})

describe('extraBlocksToSavePayload', () => {
  it('serializes blocks with sql_script for save', () => {
    const report = templateVersionToReport(baseVersion)
    const payload = extraBlocksToSavePayload(report.extra_result_blocks)
    expect(payload).toEqual([
      {
        block_id: 'blk-a',
        title: 'Scenario 2',
        sql_script: 'SELECT 2',
        post_process_config: null,
      },
    ])
  })
})
