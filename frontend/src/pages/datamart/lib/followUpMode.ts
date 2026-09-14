/**
 * How a follow-up message in an existing session relates to the prior assistant turn.
 */
export type DatamartFollowUpMode =
  | 'continue_last'
  | 'add_scenario'
  | 'new_question'
  | 'clarify_reply'

export const FOLLOW_UP_MODE_OPTIONS: Array<{
  id: DatamartFollowUpMode
  label: string
  shortLabel: string
  description: string
}> = [
  {
    id: 'continue_last',
    label: 'Modify last result',
    shortLabel: 'Modify',
    description: 'Change filters, columns, totals, or ask about the table above',
  },
  {
    id: 'add_scenario',
    label: 'Add scenario',
    shortLabel: 'Scenario',
    description:
      'Ask something unrelated — keeps the previous table and adds a second dataset in this report',
  },
  {
    id: 'new_question',
    label: 'New question only',
    shortLabel: 'Free',
    description: 'Replace this reply with a new analysis (does not keep prior scenarios)',
  },
]

export function followUpPlaceholder(mode: DatamartFollowUpMode): string {
  if (mode === 'continue_last') return 'Modify the result above…'
  if (mode === 'add_scenario') return 'Describe the new scenario to add…'
  if (mode === 'clarify_reply') return 'Answer the clarification question…'
  return 'Ask a new question…'
}
