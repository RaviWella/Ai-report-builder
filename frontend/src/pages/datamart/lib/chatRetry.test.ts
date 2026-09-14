import { describe, expect, it } from 'vitest'
import {
  buildRetryContextFromMessages,
  canRetryFailedAssistant,
  messagesAfterRemovingFailedTurn,
} from './chatRetry'

describe('chatRetry', () => {
  it('captures follow-up mode and targets from the user turn before the error', () => {
    const ctx = buildRetryContextFromMessages(
      [
        { id: 'u1', role: 'user', text: 'top paid', turnIndex: 1 },
        { id: 'a1', role: 'assistant', data: { sql: 'SELECT 1' } },
        {
          id: 'u2',
          role: 'user',
          text: 'payroll summary',
          turnIndex: 2,
          followUpMode: 'add_scenario',
          targetScenarioIds: ['primary'],
        },
        { id: 'e1', role: 'assistant', error: 'column missing' },
      ],
      'e1',
    )
    expect(ctx).toEqual({
      question: 'payroll summary',
      followUpMode: 'add_scenario',
      targetScenarioIds: ['primary'],
      editFromTurnIndex: 2,
    })
  })

  it('defaults first-turn failures to new_question when mode was not stored', () => {
    const ctx = buildRetryContextFromMessages(
      [
        { id: 'u1', role: 'user', text: 'headcount by department', turnIndex: 1 },
        { id: 'e1', role: 'assistant', error: 'timeout' },
      ],
      'e1',
    )
    expect(ctx).toEqual({
      question: 'headcount by department',
      followUpMode: 'new_question',
      editFromTurnIndex: 1,
    })
  })

  it('allows retry on the first turn when it is not the latest assistant', () => {
    const messages = [
      { id: 'u1', role: 'user' as const, text: 'q1', turnIndex: 1 },
      { id: 'a1', role: 'assistant' as const, data: { error: 'fail', sql: null } },
      { id: 'u2', role: 'user' as const, text: 'q2', turnIndex: 2 },
      { id: 'a2', role: 'assistant' as const, data: { sql: 'SELECT 1' } },
    ]
    expect(canRetryFailedAssistant(messages[1], messages, 'a2')).toBe(true)
    expect(canRetryFailedAssistant(messages[3], messages, 'a2')).toBe(false)
  })

  it('removes a persisted assistant turn when resending', () => {
    const next = messagesAfterRemovingFailedTurn(
      [
        { id: 'u', role: 'user', text: 'q', turnIndex: 1 },
        { id: 'a', role: 'assistant', data: { sql: 'SELECT 1' } },
      ],
      'a',
      { removePersistedAssistantWithError: true },
    )
    expect(next).toHaveLength(1)
    expect(next[0].id).toBe('u')
  })

  it('strips the error assistant bubble', () => {
    const next = messagesAfterRemovingFailedTurn(
      [
        { id: 'u', role: 'user', text: 'q' },
        { id: 'e', role: 'assistant', error: 'fail' },
      ],
      'e',
    )
    expect(next).toHaveLength(1)
    expect(next[0].id).toBe('u')
  })
})
