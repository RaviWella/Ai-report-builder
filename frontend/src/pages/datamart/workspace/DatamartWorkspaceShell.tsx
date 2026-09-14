/**
 * Shared layout shell for /datamart/chat and /datamart/templates/:id.
 */
import '../datamart-page.css'
import React, { useCallback, useEffect, useState } from 'react'

export interface DatamartWorkspaceShellProps {
  sidebar: React.ReactNode
  main: React.ReactNode
  /** Fill parent height (used by datamart chat page wrapper). */
  fillHeight?: boolean
}

const DatamartWorkspaceShell: React.FC<DatamartWorkspaceShellProps> = ({
  sidebar,
  main,
  fillHeight = false,
}) => {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const closeSidebar = useCallback(() => setSidebarOpen(false), [])

  useEffect(() => {
    const mq = window.matchMedia('(min-width: 901px)')
    const onChange = () => {
      if (mq.matches) setSidebarOpen(false)
    }
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  useEffect(() => {
    if (!sidebarOpen) return undefined
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeSidebar()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [sidebarOpen, closeSidebar])

  return (
    <div
      className={
        sidebarOpen
          ? 'datamart-workspace-shell datamart-workspace-shell--sidebar-open'
          : 'datamart-workspace-shell'
      }
      style={fillHeight ? { height: '100%' } : undefined}
      data-sidebar-open={sidebarOpen ? 'true' : 'false'}
    >
      <button
        type="button"
        className="datamart-workspace-shell__backdrop"
        aria-label="Close sidebar"
        onClick={closeSidebar}
      />
      <div className="datamart-workspace-shell__sidebar">{sidebar}</div>
      <div className="datamart-workspace-shell__main">
        {React.isValidElement(main)
          ? React.cloneElement(main as React.ReactElement<{ onOpenSidebar?: () => void }>, {
              onOpenSidebar: () => setSidebarOpen(true),
            })
          : main}
      </div>
    </div>
  )
}

export default DatamartWorkspaceShell
