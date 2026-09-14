/**
 * Clarification turns: assistant asked a business question before SQL could run.
 */
import type { DatamartValidation } from '../../../services/datamartService'
import type { DatamartFollowUpMode } from './followUpMode'

export function isAwaitingClarification(
  validation: DatamartValidation | null | undefined,
  sql: string | null | undefined,
): boolean {
  if (sql?.trim()) return false
  if (!validation) return false
  if (validation.awaiting_clarification) return true
  const retrieval = validation.retrieval
  if (
    retrieval?.status === 'ambiguous' ||
    retrieval?.status === 'insufficient'
  ) {
    return validation.overall === 'needs_review' || validation.overall === 'blocked'
  }
  if (validation.generation?.binding === 'failed') {
    return true
  }
  return false
}

export function resolveFollowUpModeForSend(
  mode: DatamartFollowUpMode,
  awaitingClarification: boolean,
): DatamartFollowUpMode | undefined {
  if (awaitingClarification) return 'clarify_reply'
  return mode
}

export function clarificationComposerPlaceholder(anchorQuestion?: string | null): string {
  if (anchorQuestion?.trim()) {
    return 'Answer the question above to continue your report…'
  }
  return 'Add the missing detail the assistant asked for…'
}
