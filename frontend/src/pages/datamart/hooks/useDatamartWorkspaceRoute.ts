import { useLayoutEffect, useSyncExternalStore } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  resolveWorkspaceRoute,
  syncRouterToBrowser,
  type DatamartWorkspaceRouteState,
} from '../lib/workspaceRoute'

function browserUrlSnapshot(): string {
  if (typeof window === 'undefined') return ''
  return `${window.location.pathname}${window.location.search}`
}

/** Re-render when the address bar changes (Link clicks update window before React Router sometimes). */
function subscribeBrowserUrl(onStoreChange: () => void): () => void {
  const notify = () => onStoreChange()
  window.addEventListener('popstate', notify)
  window.addEventListener('hashchange', notify)
  const interval = window.setInterval(notify, 50)
  return () => {
    window.removeEventListener('popstate', notify)
    window.removeEventListener('hashchange', notify)
    window.clearInterval(interval)
  }
}

/**
 * One workspace route hook for chat + template pages.
 * Browser URL is authoritative; React Router is synced in layout effect.
 */
export function useDatamartWorkspaceRoute(): DatamartWorkspaceRouteState {
  const location = useLocation()
  const navigate = useNavigate()
  const browserUrl = useSyncExternalStore(
    subscribeBrowserUrl,
    browserUrlSnapshot,
    () => '',
  )

  useLayoutEffect(() => {
    syncRouterToBrowser(navigate, location.pathname, location.search)
  }, [browserUrl, location.pathname, location.search, navigate])

  const pathname =
    typeof window !== 'undefined' ? window.location.pathname : location.pathname
  const search =
    typeof window !== 'undefined' ? window.location.search : location.search

  return resolveWorkspaceRoute(pathname, search)
}
