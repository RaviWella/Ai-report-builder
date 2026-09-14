import { describe, expect, it } from 'vitest'
import {
  buildFilterPrompt,
  buildRemoveColumnPrompt,
  buildSortPrompt,
  truncateContextLabel,
} from './quickActionPrompts'
describe('quickActionPrompts', () => {
  it('builds remove column prompt', () => {
    expect(buildRemoveColumnPrompt('leave_days')).toContain('leave_days')
    expect(buildRemoveColumnPrompt('leave_days')).toContain('previous answer')
  })

  it('builds filter prompt', () => {
    expect(buildFilterPrompt('only Head Office')).toContain('Head Office')
  })

  it('builds sort prompt with direction', () => {
    expect(buildSortPrompt('full_name', 'desc')).toContain('descending')
    expect(buildSortPrompt('full_name', 'asc')).toContain('ascending')
  })

  it('truncates long labels', () => {
    const long = 'a'.repeat(60)
    expect(truncateContextLabel(long, 48).endsWith('…')).toBe(true)
  })
})
