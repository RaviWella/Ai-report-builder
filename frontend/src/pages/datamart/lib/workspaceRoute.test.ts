import { describe, expect, it, vi } from 'vitest'
import {
  chatPathWithSession,
  preserveOrgSearch,
  resolveWorkspaceRoute,
  targetPathFromBrowser,
  templatePathWithId,
} from './workspaceRoute'

describe('workspaceRoute', () => {
  it('preserveOrgSearch keeps auth params only', () => {
    expect(
      preserveOrgSearch('?session=abc&organization_id=alpha&environment=development'),
    ).toBe('?organization_id=alpha&environment=development')
  })

  it('template path drops session query param', () => {
    expect(
      templatePathWithId(
        'tpl-1',
        '?session=sess-a&organization_id=alpha',
      ),
    ).toBe('/datamart/templates/tpl-1?organization_id=alpha')
  })

  it('chat path keeps session and org', () => {
    expect(
      chatPathWithSession('sess-b', '?organization_id=alpha'),
    ).toBe('/datamart/chat?organization_id=alpha&session=sess-b')
  })

  it('resolveWorkspaceRoute prefers template pathname', () => {
    expect(
      resolveWorkspaceRoute('/datamart/templates/tpl-9', '?session=old'),
    ).toEqual({
      mode: 'template',
      templateId: 'tpl-9',
      sessionId: null,
    })
  })

  it('resolveWorkspaceRoute reads chat session', () => {
    expect(
      resolveWorkspaceRoute('/datamart/chat', '?session=sess-1&organization_id=alpha'),
    ).toEqual({
      mode: 'chat',
      templateId: null,
      sessionId: 'sess-1',
    })
  })

  it('targetPathFromBrowser builds template target without session', () => {
    expect(
      targetPathFromBrowser(
        '/datamart/templates/tpl-2',
        '?session=sess-x&organization_id=alpha',
      ),
    ).toBe('/datamart/templates/tpl-2?organization_id=alpha')
  })

  it('targetPathFromBrowser builds chat target from browser', () => {
    expect(
      targetPathFromBrowser(
        '/datamart/chat',
        '?session=sess-y&organization_id=alpha',
      ),
    ).toBe('/datamart/chat?organization_id=alpha&session=sess-y')
  })
})

describe('syncRouterToBrowser', () => {
  it('navigates when browser and router differ', async () => {
    const navigate = vi.fn()
    const { syncRouterToBrowser } = await import('./workspaceRoute')

    Object.defineProperty(window, 'location', {
      value: {
        pathname: '/datamart/templates/tpl-a',
        search: '?organization_id=alpha',
      },
      writable: true,
    })

    syncRouterToBrowser(navigate, '/datamart/chat', '?session=sess-1')
    expect(navigate).toHaveBeenCalledWith(
      '/datamart/templates/tpl-a?organization_id=alpha',
      { replace: true },
    )
  })
})
