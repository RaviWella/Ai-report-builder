/**
 * Remove a turn and all following messages from in-memory chat state.
 */
export interface TurnIndexedMessage {
  turnIndex?: number
}

export function truncateMessagesFromTurn<T extends TurnIndexedMessage>(
  messages: T[],
  fromTurnIndex: number,
): T[] {
  const start = messages.findIndex(
    (m) => m.turnIndex != null && m.turnIndex >= fromTurnIndex,
  )
  if (start < 0) return messages
  return messages.slice(0, start)
}
