import { describe, expect, it } from 'vitest'
import { getUndoInfoFromMessages } from './undoModification'

describe('getUndoInfoFromMessages', () => {
  it('allows undo when last user turn was continue_last', () => {
    const info = getUndoInfoFromMessages([
      { role: 'user', turn_index: 1 },
      { role: 'assistant', turn_index: 1 },
      { role: 'user', turn_index: 2, follow_up_mode: 'continue_last' },
      { role: 'assistant', turn_index: 2 },
    ])
    expect(info.canUndo).toBe(true)
    expect(info.lastTurnIndex).toBe(2)
  })

  it('disallows undo when last turn was new_question', () => {
    const info = getUndoInfoFromMessages([
      { role: 'user', turn_index: 1 },
      { role: 'assistant', turn_index: 1 },
      { role: 'user', turn_index: 2, follow_up_mode: 'new_question' },
      { role: 'assistant', turn_index: 2 },
    ])
    expect(info.canUndo).toBe(false)
  })

  it('disallows undo on first turn only', () => {
    const info = getUndoInfoFromMessages([
      { role: 'user', turn_index: 1 },
      { role: 'assistant', turn_index: 1 },
    ])
    expect(info.canUndo).toBe(false)
  })
})
