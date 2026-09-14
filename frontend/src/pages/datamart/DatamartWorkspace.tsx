/**
 * Single mount for /datamart/chat and /datamart/templates/:id.
 * Renders chat vs template from the browser URL so sidebar Link clicks cannot
 * leave the wrong page visible when React Router lags behind the address bar.
 */
import { Navigate } from 'react-router-dom'
import DatamartChat from './DatamartChat'
import DatamartTemplatePage from './DatamartTemplatePage'
import { useDatamartWorkspaceRoute } from './hooks/useDatamartWorkspaceRoute'

export default function DatamartWorkspace() {
  const { mode } = useDatamartWorkspaceRoute()

  if (mode === 'template') {
    return <DatamartTemplatePage />
  }

  if (mode === 'chat') {
    return <DatamartChat />
  }

  return <Navigate to="/datamart/chat" replace />
}
