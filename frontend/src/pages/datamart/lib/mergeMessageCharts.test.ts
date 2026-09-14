import { describe, expect, it } from 'vitest'
import { mergeChartConfigsFromHistory } from './mergeMessageCharts'
import type { MessageResponse } from '../../../services/datamartService'

describe('mergeChartConfigsFromHistory', () => {
  it('keeps in-memory charts when API returns empty', () => {
    const messages = [
      {
        id: 'a1',
        role: 'assistant' as const,
        messageId: 'm1',
        data: {
          chart_configs: [{ schema_version: 1, id: 'c1' }],
        },
      },
    ]
    const api: MessageResponse[] = [
      {
        id: 'm1',
        role: 'assistant',
        content: '',
        sql_script: null,
        question_ref: null,
        post_process_config: null,
        chart_configs: [],
        turn_index: 0,
        is_summarised: false,
      },
    ]
    const out = mergeChartConfigsFromHistory(messages, api)
    expect(out[0]?.data?.chart_configs).toHaveLength(1)
  })
})
