import { describe, expect, it, vi } from 'vitest'
import {
  templateDetailPath,
  navigateToTemplate,
  warmTemplateWorkspace,
} from './templateNavigation'

describe('templateNavigation', () => {
  it('builds template detail path', () => {
    expect(templateDetailPath('abc-123')).toBe('/datamart/templates/abc-123')
  })

  it('navigates to a different template and warms cache', () => {
    const navigate = vi.fn()
    const invalidateQueries = vi.fn()
    const prefetchQuery = vi.fn().mockResolvedValue(undefined)
    const queryClient = {
      invalidateQueries,
      prefetchQuery,
    } as unknown as import('@tanstack/react-query').QueryClient

    navigateToTemplate(navigate, queryClient, 'tpl-b', '?organization_id=alpha')

    expect(navigate).toHaveBeenCalledWith('/datamart/templates/tpl-b?organization_id=alpha')
    expect(invalidateQueries).toHaveBeenCalledTimes(2)
    expect(prefetchQuery).toHaveBeenCalledTimes(2)
  })

  it('re-navigates with refresh state when already on the same template path', () => {
    Object.defineProperty(window, 'location', {
      value: { pathname: '/datamart/templates/tpl-a', search: '?organization_id=alpha' },
      writable: true,
    })
    const navigate = vi.fn()
    const queryClient = {
      invalidateQueries: vi.fn(),
      prefetchQuery: vi.fn().mockResolvedValue(undefined),
    } as unknown as import('@tanstack/react-query').QueryClient

    navigateToTemplate(navigate, queryClient, 'tpl-a', '?organization_id=alpha')

    expect(navigate).toHaveBeenCalledWith(
      '/datamart/templates/tpl-a?organization_id=alpha',
      expect.objectContaining({
        replace: true,
        state: expect.objectContaining({ templateRefresh: expect.any(Number) }),
      }),
    )
  })

  it('warmTemplateWorkspace invalidates and prefetches', () => {
    const invalidateQueries = vi.fn()
    const prefetchQuery = vi.fn().mockResolvedValue(undefined)
    const queryClient = {
      invalidateQueries,
      prefetchQuery,
    } as unknown as import('@tanstack/react-query').QueryClient

    warmTemplateWorkspace(queryClient, 'tpl-x')

    expect(invalidateQueries).toHaveBeenCalledTimes(2)
    expect(prefetchQuery).toHaveBeenCalledTimes(2)
  })
})
