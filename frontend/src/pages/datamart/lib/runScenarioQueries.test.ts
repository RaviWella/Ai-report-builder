import { describe, expect, it, vi, beforeEach } from 'vitest'
import type { DatamartResponse } from '../../../services/datamartService'

vi.mock('../../../services/datamartService', () => ({
  datamartService: {
    executeMessageSql: vi.fn(),
    executeMessageBlock: vi.fn(),
    executeTemplateVersionSql: vi.fn(),
    executeTemplateVersionBlock: vi.fn(),
  },
}))

import { datamartService } from '../../../services/datamartService'
import { runAllScenarioQueries } from './runScenarioQueries'

const baseData: DatamartResponse = {
  question: 'Q',
  narrative: 'N',
  sql: 'SELECT 1',
  post_process_config: null,
  columns: [],
  rows: [],
  row_count: 0,
  error: null,
  session_id: 's1',
  message_id: 'm1',
  extra_result_blocks: [
    {
      block_id: 'scenario_b',
      title: 'Scenario B',
      sql: 'SELECT 2',
      post_process_config: null,
      columns: [],
      rows: [],
      row_count: 0,
    },
  ],
}

describe('runAllScenarioQueries', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(datamartService.executeMessageSql).mockResolvedValue({
      columns: ['a'],
      rows: [[1]],
      row_count: 1,
    })
    vi.mocked(datamartService.executeMessageBlock).mockResolvedValue({
      columns: ['b'],
      rows: [[2]],
      row_count: 1,
    })
  })

  it('runs primary and every extra block in parallel', async () => {
    const result = await runAllScenarioQueries({
      data: baseData,
      sessionId: 's1',
      messageId: 'm1',
      isTemplateReport: false,
    })

    expect(datamartService.executeMessageSql).toHaveBeenCalledWith('s1', 'm1', undefined)
    expect(datamartService.executeMessageBlock).toHaveBeenCalledWith(
      's1',
      'm1',
      'scenario_b',
    )
    expect(result.primary?.columns).toEqual(['a'])
    expect(result.blocks.scenario_b?.columns).toEqual(['b'])
  })
})
