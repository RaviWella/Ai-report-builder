import type { NavigateFunction } from 'react-router-dom'
import { chatPathWithSession, preserveOrgSearch } from './workspaceRoute'

export function sessionIdFromSearch(search: string): string | null {
  const raw = search.startsWith('?') ? search.slice(1) : search
  if (!raw) return null
  return new URLSearchParams(raw).get('session')
}

export { chatPathWithSession }

/** Programmatic navigation to a chat session (promote, etc.). */
export function navigateToChatSession(
  navigate: NavigateFunction,
  sessionId: string,
  currentSearch?: string,
): void {
  const path = chatPathWithSession(sessionId, currentSearch ?? '')
  const currentSession = sessionIdFromSearch(currentSearch ?? '')
  if (currentSession === sessionId && currentSearch?.includes('session=')) {
    navigate(path, { replace: true, state: { sessionRefresh: Date.now() } })
  } else {
    navigate(path)
  }
}

export function navigateToNewChat(
  navigate: NavigateFunction,
  currentSearch?: string,
): void {
  navigate(`/datamart/chat${preserveOrgSearch(currentSearch ?? '')}`)
}
