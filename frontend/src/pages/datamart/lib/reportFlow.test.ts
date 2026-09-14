import { describe, expect, it } from 'vitest'
import {
  buildRemoveColumnFollowUpPrompt,
  reportFlowReducer,
  REPORT_FLOW_E2E_STEPS,
} from './reportFlow'

describe('reportFlow', () => {
  it('runs ask → sql → run → remove column → follow-up path', () => {
    let step = reportFlowReducer('idle', { type: 'send_question' })
    expect(step).toBe('awaiting_assistant')

    step = reportFlowReducer(step, { type: 'assistant_sql' })
    expect(step).toBe('sql_ready')

    step = reportFlowReducer(step, { type: 'run_query' })
    expect(step).toBe('results_loaded')

    step = reportFlowReducer(step, { type: 'remove_column', column: 'leave_days' })
    expect(step).toBe('follow_up_sent')

    const prompt = buildRemoveColumnFollowUpPrompt('leave_days')
    expect(prompt).toContain('leave_days')
  })

  it('documents E2E steps', () => {
    expect(REPORT_FLOW_E2E_STEPS.length).toBeGreaterThanOrEqual(5)
  })
})
