import { describe, expect, it } from 'vitest'
import { templateIdFromPathname } from './templateRoute'

describe('templateIdFromPathname', () => {
  it('parses template id from pathname', () => {
    expect(templateIdFromPathname('/datamart/templates/abc-123')).toBe('abc-123')
  })

  it('parses when query string is present on pathname only', () => {
    expect(templateIdFromPathname('/datamart/templates/xyz')).toBe('xyz')
  })

  it('returns null for unrelated paths', () => {
    expect(templateIdFromPathname('/datamart/chat')).toBeNull()
  })
})
