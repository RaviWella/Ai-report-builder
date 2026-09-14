import { describe, expect, it } from 'vitest'
import {
  isAwaitingClarification,
  resolveFollowUpModeForSend,
} from './clarificationReply'
import type { DatamartValidation } from '../../../services/datamartService'

describe('clarificationReply', () => {
  it('detects explicit awaiting flag', () => {
    const v = { awaiting_clarification: true } as DatamartValidation
    expect(isAwaitingClarification(v, null)).toBe(true)
  })

  it('resolves clarify_reply when awaiting', () => {
    expect(resolveFollowUpModeForSend('continue_last', true)).toBe('clarify_reply')
    expect(resolveFollowUpModeForSend('continue_last', false)).toBe('continue_last')
  })
})
