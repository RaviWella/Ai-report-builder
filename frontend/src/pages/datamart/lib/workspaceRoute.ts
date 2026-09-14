import type { NavigateFunction } from 'react-router-dom'
import { sessionIdFromSearch } from './chatSessionRoute'
import { templateDetailPath } from './templateNavigation'
import { templateIdFromPathname } from './templateRoute'

const ORG_PARAM_KEYS = [
  'organization_id',
  'environment',
  'access_token',
  'submodule_code',
  'legal_entity_id',
] as const

export type DatamartWorkspaceMode = 'chat' | 'template' | 'unknown'

export interface DatamartWorkspaceRouteState {
  mode: DatamartWorkspaceMode
  sessionId: string | null
  templateId: string | null
}

/** Auth/org query string to carry across workspace links (no session param). */
export function preserveOrgSearch(search: string): string {
  const raw = search.startsWith('?') ? search.slice(1) : search
  if (!raw) return ''
  const src = new URLSearchParams(raw)
  const out = new URLSearchParams()
  for (const key of ORG_PARAM_KEYS) {
    const val = src.get(key)
    if (val) out.set(key, val)
  }
  const q = out.toString()
  return q ? `?${q}` : ''
}

export function chatPathWithSession(sessionId: string, search = ''): string {
  const org = preserveOrgSearch(search)
  const params = new URLSearchParams(org ? org.slice(1) : '')
  params.set('session', sessionId)
  return `/datamart/chat?${params.toString()}`
}

export function templatePathWithId(templateId: string, search = ''): string {
  return `${templateDetailPath(templateId)}${preserveOrgSearch(search)}`
}

export function resolveWorkspaceRoute(
  pathname: string,
  search: string,
): DatamartWorkspaceRouteState {
  const templateId = templateIdFromPathname(pathname)
  if (templateId) {
    return { mode: 'template', templateId, sessionId: null }
  }
  if (pathname === '/datamart/chat' || pathname.endsWith('/datamart/chat')) {
    return {
      mode: 'chat',
      templateId: null,
      sessionId: sessionIdFromSearch(search),
    }
  }
  return { mode: 'unknown', templateId: null, sessionId: null }
}

/** Align React Router location with the browser URL (single source of truth). */
export function targetPathFromBrowser(
  browserPathname: string,
  browserSearch: string,
): string | null {
  const templateId = templateIdFromPathname(browserPathname)
  if (templateId) {
    return templatePathWithId(templateId, browserSearch)
  }
  if (browserPathname === '/datamart/chat' || browserPathname.endsWith('/datamart/chat')) {
    const sessionId = sessionIdFromSearch(browserSearch)
    if (sessionId) {
      return chatPathWithSession(sessionId, browserSearch)
    }
    return `/datamart/chat${preserveOrgSearch(browserSearch)}`
  }
  return null
}

export function syncRouterToBrowser(
  navigate: NavigateFunction,
  routerPathname: string,
  routerSearch: string,
): void {
  if (typeof window === 'undefined') return

  const browserPathname = window.location.pathname
  const browserSearch = window.location.search

  if (browserPathname === routerPathname && browserSearch === routerSearch) {
    return
  }

  const isChatPath =
    browserPathname === '/datamart/chat' || browserPathname.endsWith('/datamart/chat')
  const isTemplatePath = !!templateIdFromPathname(browserPathname)
  const isRouterTemplatePath = !!templateIdFromPathname(routerPathname)
  const browserSession = sessionIdFromSearch(browserSearch)
  const routerSession = sessionIdFromSearch(routerSearch)

  // Mid-navigation: address bar briefly shows /datamart/chat before ?session= is applied.
  if (isChatPath && !browserSession && routerSession) {
    return
  }

  // Never skip when switching between chat and template (different route elements).
  if (isTemplatePath !== isRouterTemplatePath) {
    const target = targetPathFromBrowser(browserPathname, browserSearch)
    if (target) navigate(target, { replace: true })
    return
  }

  const target = targetPathFromBrowser(browserPathname, browserSearch)
  if (target) {
    navigate(target, { replace: true })
  }
}
