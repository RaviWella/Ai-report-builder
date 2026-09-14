import { describe, expect, it } from 'vitest'
import { resolveActiveTemplateVersion } from './resolveTemplateVersion'
import type { TemplateVersionResponse } from '../../../services/datamartService'

const version = (
  id: string,
  templateId: string,
  overrides: Partial<TemplateVersionResponse> = {},
): TemplateVersionResponse => ({
  id,
  template_id: templateId,
  version_num: 1,
  label: null,
  sql_script: 'SELECT 1',
  post_process_config: null,
  chart_configs: null,
  extra_result_blocks: null,
  report_layout: null,
  narrative: null,
  source_session_id: null,
  source_message_id: null,
  is_latest: true,
  created_at: '2026-01-01T00:00:00Z',
  ...overrides,
})

describe('resolveActiveTemplateVersion', () => {
  it('returns null when versions belong to another template', () => {
    const stale = [version('v1', 'template-a')]
    expect(
      resolveActiveTemplateVersion({
        templateId: 'template-b',
        versions: stale,
        activeVersionId: null,
        latestFromTemplate: null,
      }),
    ).toBeNull()
  })

  it('prefers explicit selection when it matches template', () => {
    const versions = [
      version('v1', 't1', { is_latest: false }),
      version('v2', 't1', { is_latest: true }),
    ]
    expect(
      resolveActiveTemplateVersion({
        templateId: 't1',
        versions,
        activeVersionId: 'v1',
        latestFromTemplate: versions[1],
      }),
    ).toEqual(versions[0])
  })

  it('falls back to latest version for the requested template', () => {
    const latest = version('v2', 't2', { is_latest: true })
    expect(
      resolveActiveTemplateVersion({
        templateId: 't2',
        versions: [version('v1', 't2', { is_latest: false }), latest],
        activeVersionId: null,
        latestFromTemplate: latest,
      }),
    ).toEqual(latest)
  })
})
