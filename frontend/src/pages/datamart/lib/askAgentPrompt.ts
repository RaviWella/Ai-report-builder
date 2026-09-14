/**
 * Builds a follow-up chat message for SQL changes (audited via new assistant turn).
 */
export function buildSqlChangePrompt(userInstruction: string): string {
  const trimmed = userInstruction.trim()
  if (!trimmed) {
    return 'Please update the SQL from your previous answer based on my latest request.'
  }
  return `Please update the SQL from your previous answer: ${trimmed}`
}
