/**
 * Retry a failed datamart turn while preserving follow-up mode (modify / scenario / new).
 */
import type { DatamartResponse } from '../../../services/datamartService'
import type { DatamartFollowUpMode } from './followUpMode'

export interface RetryableChatMessage {
  id: string
  role: 'user' | 'assistant'
  text?: string
  error?: string
  turnIndex?: number
  followUpMode?: DatamartFollowUpMode
  targetScenarioIds?: string[]
  data?: DatamartResponse
}

export interface RetrySendContext {
  question: string
  followUpMode: DatamartFollowUpMode
  targetScenarioIds?: string[]
  /** When set, replace this turn in the session (failed turn was persisted). */
  editFromTurnIndex?: number
}

/** True when an earlier assistant turn produced runnable SQL (or scenarios). */
export function hasPriorSuccessfulAssistant(
  messages: RetryableChatMessage[],
  beforeIndex: number,
): boolean {
  for (let i = 0; i < beforeIndex; i += 1) {
    const m = messages[i]
    if (m.role !== 'assistant' || !m.data) continue
    if (m.data.sql?.trim()) return true
    const extras = m.data.extra_result_blocks ?? []
    if (extras.some((b) => b.sql?.trim())) return true
  }
  return false
}

export function isInitialTurnAssistant(
  msg: RetryableChatMessage,
  messages: RetryableChatMessage[],
): boolean {
  if (msg.turnIndex === 1) return true
  const firstAssistantIdx = messages.findIndex((m) => m.role === 'assistant')
  return firstAssistantIdx >= 0 && messages[firstAssistantIdx]?.id === msg.id
}

/** Whether this failed assistant turn can show "Try again". */
export function canRetryFailedAssistant(
  msg: RetryableChatMessage,
  messages: RetryableChatMessage[],
  latestAssistantId: string | null | undefined,
): boolean {
  const pipelineFailed = msg.role === 'assistant' && !!msg.data?.error
  if (!pipelineFailed) return false
  if (msg.id === latestAssistantId) return true
  return isInitialTurnAssistant(msg, messages)
}

function resolveRetryFollowUpMode(
  user: RetryableChatMessage,
  messages: RetryableChatMessage[],
  userIdx: number,
): DatamartFollowUpMode {
  if (user.followUpMode) return user.followUpMode
  if (!hasPriorSuccessfulAssistant(messages, userIdx)) return 'new_question'
  return 'continue_last'
}

/**
 * Build resend context from the user message that preceded a failed assistant turn.
 */
export function buildRetryContextFromMessages(
  messages: RetryableChatMessage[],
  errorMessageId: string,
): RetrySendContext | null {
  const errIdx = messages.findIndex((m) => m.id === errorMessageId)
  if (errIdx < 0) return null

  let userIdx = -1
  for (let i = errIdx - 1; i >= 0; i -= 1) {
    if (messages[i]?.role === 'user') {
      userIdx = i
      break
    }
  }
  if (userIdx < 0) return null

  const user = messages[userIdx]
  const question = (user.text ?? '').trim()
  if (!question) return null

  const turnIndex = user.turnIndex
  const editFromTurnIndex =
    turnIndex != null && turnIndex > 0 ? turnIndex : undefined

  return {
    question,
    followUpMode: resolveRetryFollowUpMode(user, messages, userIdx),
    targetScenarioIds: user.targetScenarioIds,
    editFromTurnIndex,
  }
}

/** Remove a failed assistant error bubble (or failed assistant data turn when retrying in place). */
export function messagesAfterRemovingFailedTurn<T extends RetryableChatMessage>(
  messages: T[],
  failedId: string,
  opts?: { removePersistedAssistantWithError?: boolean },
): T[] {
  const errIdx = messages.findIndex((m) => m.id === failedId)
  if (errIdx < 0) return messages

  const failed = messages[errIdx]
  if (failed.role === 'assistant' && failed.error) {
    return [...messages.slice(0, errIdx), ...messages.slice(errIdx + 1)]
  }

  if (
    opts?.removePersistedAssistantWithError &&
    failed.role === 'assistant' &&
    failed.data
  ) {
    return [...messages.slice(0, errIdx), ...messages.slice(errIdx + 1)]
  }

  return messages
}
