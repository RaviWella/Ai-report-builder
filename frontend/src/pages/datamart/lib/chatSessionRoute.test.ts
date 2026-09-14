import { describe, expect, it, vi } from 'vitest'
import { chatPathWithSession, navigateToChatSession, sessionIdFromSearch } from './chatSessionRoute'

describe('chatSessionRoute', () => {
  it('parses session id from search string', () => {
    expect(sessionIdFromSearch('?session=abc-123&organization_id=alpha')).toBe('abc-123')
  })

  it('builds chat path with encoded session and org', () => {
    expect(chatPathWithSession('sess-uuid', '?organization_id=alpha')).toBe(
      '/datamart/chat?organization_id=alpha&session=sess-uuid',
    )
  })

  it('navigates to a new session', () => {
    const navigate = vi.fn()
    navigateToChatSession(navigate, 'sess-b', '?session=sess-a&organization_id=alpha')
    expect(navigate).toHaveBeenCalledWith(
      '/datamart/chat?organization_id=alpha&session=sess-b',
    )
  })

  it('re-navigates with refresh when session unchanged', () => {
    const navigate = vi.fn()
    navigateToChatSession(navigate, 'sess-a', '?session=sess-a&organization_id=alpha')
    expect(navigate).toHaveBeenCalledWith(
      '/datamart/chat?organization_id=alpha&session=sess-a',
      expect.objectContaining({ replace: true }),
    )
  })
})
