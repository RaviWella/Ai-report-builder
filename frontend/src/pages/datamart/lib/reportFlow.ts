/**
 * Pure state machine for the datamart report user journey (used in tests and E2E docs).
 */
import { buildRemoveColumnPrompt } from './quickActionPrompts'

export type ReportFlowStep =
  | 'idle'
  | 'awaiting_assistant'
  | 'sql_ready'
  | 'results_loaded'
  | 'follow_up_sent'

export type ReportFlowEvent =
  | { type: 'send_question' }
  | { type: 'assistant_sql' }
  | { type: 'run_query' }
  | { type: 'remove_column'; column: string }
  | { type: 'reset' }

export function reportFlowReducer(
  state: ReportFlowStep,
  event: ReportFlowEvent,
): ReportFlowStep {
  switch (event.type) {
    case 'reset':
      return 'idle'
    case 'send_question':
      return state === 'idle' || state === 'results_loaded' || state === 'follow_up_sent'
        ? 'awaiting_assistant'
        : state
    case 'assistant_sql':
      return state === 'awaiting_assistant' ? 'sql_ready' : state
    case 'run_query':
      return state === 'sql_ready' || state === 'follow_up_sent' ? 'results_loaded' : state
    case 'remove_column':
      return state === 'results_loaded' ? 'follow_up_sent' : state
    default:
      return state
  }
}

/** Scripted flow: ask → run → remove column quick action → run again. */
export function buildRemoveColumnFollowUpPrompt(column: string): string {
  return buildRemoveColumnPrompt(column)
}

export const REPORT_FLOW_E2E_STEPS = [
  'Open /datamart/chat and start a new session',
  'Ask a question via the composer',
  'Wait for assistant SQL on the report card',
  'Click Run query and load results',
  'Use Remove column quick action on a column',
  'Click Run query again on the updated turn',
] as const
