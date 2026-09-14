import type { QueryClient } from '@tanstack/react-query'
import type { NavigateFunction } from 'react-router-dom'
import { datamartService } from '../../../services/datamartService'
import { templatePathWithId } from './workspaceRoute'

export const templateDetailPath = (templateId: string): string =>
  `/datamart/templates/${templateId}`

/** Load template + versions into the React Query cache (sidebar click or route entry). */
export function prefetchTemplateWorkspace(
  queryClient: QueryClient,
  templateId: string,
): Promise<unknown[]> {
  return Promise.all([
    queryClient.prefetchQuery({
      queryKey: ['datamart-template', templateId],
      queryFn: () => datamartService.getTemplate(templateId),
    }),
    queryClient.prefetchQuery({
      queryKey: ['datamart-template-versions', templateId],
      queryFn: () => datamartService.listTemplateVersions(templateId),
    }),
  ])
}

export function invalidateTemplateWorkspace(
  queryClient: QueryClient,
  templateId: string,
): void {
  void queryClient.invalidateQueries({ queryKey: ['datamart-template', templateId] })
  void queryClient.invalidateQueries({ queryKey: ['datamart-template-versions', templateId] })
}

/** Sidebar / promote: warm cache then route (programmatic navigation). */
export function warmTemplateWorkspace(
  queryClient: QueryClient,
  templateId: string,
): void {
  invalidateTemplateWorkspace(queryClient, templateId)
  void prefetchTemplateWorkspace(queryClient, templateId)
}

export function navigateToTemplate(
  navigate: NavigateFunction,
  queryClient: QueryClient,
  templateId: string,
  currentSearch = '',
): void {
  const path = templatePathWithId(templateId, currentSearch)
  warmTemplateWorkspace(queryClient, templateId)
  const onTemplate =
    typeof window !== 'undefined' &&
    window.location.pathname.includes('/datamart/templates/') &&
    window.location.pathname.endsWith(templateId)
  if (onTemplate) {
    navigate(path, { replace: true, state: { templateRefresh: Date.now() } })
  } else {
    navigate(path)
  }
}
