/**
 * Detect whether the latest session turn can be undone (continue_last modification).
 */
import type { DatamartFollowUpMode } from '../../../services/datamartService'

export interface TurnUndoInfo {
  canUndo: boolean
  lastTurnIndex: number | null
}

export interface MessageTurnLike {
  role: string
  turn_index?: number
  turnIndex?: number
  follow_up_mode?: string | null
  followUpMode?: DatamartFollowUpMode | null
}

function turnIndexOf(m: MessageTurnLike): number | undefined {
  return m.turn_index ?? m.turnIndex
}

export function getUndoInfoFromMessages(messages: MessageTurnLike[]): TurnUndoInfo {
  let maxTurn = 0
  for (const m of messages) {
    const t = turnIndexOf(m)
    if (t != null && t > maxTurn) maxTurn = t
  }
  if (maxTurn < 2) {
    return { canUndo: false, lastTurnIndex: maxTurn || null }
  }

  const lastUser = messages.find(
    (m) => m.role === 'user' && turnIndexOf(m) === maxTurn,
  )
  const mode = lastUser?.follow_up_mode ?? lastUser?.followUpMode ?? null

  if (mode === 'new_question') {
    return { canUndo: false, lastTurnIndex: maxTurn }
  }

  return { canUndo: true, lastTurnIndex: maxTurn }
}
