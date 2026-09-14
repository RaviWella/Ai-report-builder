/**
 * Route: /datamart/templates/:templateId
 */
import { useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import DatamartSidebar from './components/DatamartSidebar'
import TemplateViewer from './templates/TemplateViewer'
import DatamartWorkspaceShell from './workspace/DatamartWorkspaceShell'
import { useDatamartWorkspaceSidebar } from './hooks/useDatamartWorkspaceSidebar'
import { prefetchTemplateWorkspace } from './lib/templateNavigation'
import { useDatamartWorkspaceRoute } from './hooks/useDatamartWorkspaceRoute'
import { navigateToNewChat } from './lib/chatSessionRoute'
import './datamart-page.css'

export default function DatamartTemplatePage() {
  const location = useLocation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { templateId } = useDatamartWorkspaceRoute()
  const refreshToken =
    (location.state as { templateRefresh?: number } | null)?.templateRefresh ?? 0

  const sidebarProps = useDatamartWorkspaceSidebar({
    activeSessionId: null,
    activeTemplateId: templateId ?? null,
    navigate,
  })

  useEffect(() => {
    if (!templateId) return
    void prefetchTemplateWorkspace(queryClient, templateId)
  }, [templateId, queryClient])

  const sidebar = {
    ...sidebarProps,
    onNewSession: () => {
      navigateToNewChat(navigate, location.search)
    },
  }

  if (!templateId) {
    return (
      <div className="datamart-chat-page" style={{ padding: 24, color: '#64748b' }}>
        Loading template…
      </div>
    )
  }

  return (
    <div className="datamart-chat-page">
      <DatamartWorkspaceShell
        key={`${templateId}:${location.pathname}:${refreshToken}`}
        fillHeight
        sidebar={<DatamartSidebar {...sidebar} />}
        main={
          <TemplateViewer
            key={`${templateId}:${refreshToken}`}
            templateId={templateId}
          />
        }
      />
    </div>
  )
}
