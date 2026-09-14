import { Menu, RefreshCw } from 'lucide-react'
import type { DatamartBootstrapResponse } from '../../../services/datamartService'

type Props = {
  bootstrap: DatamartBootstrapResponse | undefined
  isLoading: boolean
  isError: boolean
  onRefresh: () => void
  isRefreshing: boolean
  onOpenSidebar?: () => void
}

export function DatamartChatHeader({
  bootstrap,
  isLoading,
  isError,
  onRefresh,
  isRefreshing,
  onOpenSidebar,
}: Props) {
  const legacy = bootstrap?.profile !== 'tenant_etl'
  const notReady = bootstrap ? !bootstrap.ready : false
  const lowSemantic = (bootstrap?.table_counts?.hr_semantic ?? 0) === 0
  const showCriticalBanner = isError || (bootstrap && (notReady || legacy))
  const pillTitle =
    lowSemantic && !notReady && !legacy
      ? 'hr_semantic has no views/tables visible to the reader; queries fall back to hr marts. Click Sync after publishing semantic views.'
      : undefined

  let pillClass = 'dm-status-pill dm-status-pill--ok'
  let dotClass = 'dm-status-dot dm-status-dot--ok'
  let pillLabel = 'Warehouse ready'

  if (isLoading) {
    pillClass = 'dm-status-pill dm-status-pill--load'
    dotClass = 'dm-status-dot'
    pillLabel = 'Connecting…'
  } else if (isError) {
    pillClass = 'dm-status-pill dm-status-pill--err'
    dotClass = 'dm-status-dot dm-status-dot--err'
    pillLabel = 'Metadata unavailable'
  } else if (notReady || legacy) {
    pillClass = 'dm-status-pill dm-status-pill--warn'
    dotClass = 'dm-status-dot dm-status-dot--warn'
    pillLabel = notReady ? 'Warehouse not ready' : 'Wrong warehouse profile'
  } else if (lowSemantic) {
    pillClass = 'dm-status-pill dm-status-pill--warn'
    dotClass = 'dm-status-dot dm-status-dot--warn'
    pillLabel = 'Using hr marts'
  } else if (bootstrap) {
    pillLabel = `${bootstrap.total_tables} tables`
  }

  return (
    <>
      <header className="dm-topbar">
        <div className="dm-topbar__left">
          <button
            type="button"
            className="dm-topbar__menu-btn"
            aria-label="Open workspaces"
            onClick={onOpenSidebar}
          >
            <Menu size={18} />
          </button>
          <div className="dm-topbar__titles">
            <h2 className="dm-topbar__title">Datamart Assistant</h2>
            <p className="dm-topbar__subtitle">Ask questions about your HR warehouse in plain English</p>
          </div>
        </div>
        <div className="dm-topbar__actions">
          <span className={pillClass} title={pillTitle}>
            {!isLoading && <span className={dotClass} aria-hidden />}
            {pillLabel}
          </span>
          <button
            type="button"
            className="dm-btn-ghost"
            onClick={onRefresh}
            disabled={isRefreshing || (isLoading && !bootstrap)}
            title="Full sync: semantic catalog YAML + warehouse table counts (may take 1–2 min)"
          >
            <RefreshCw
              size={14}
              className={isRefreshing ? 'dm-spin' : undefined}
              aria-hidden
            />
            {isRefreshing ? 'Syncing…' : 'Sync'}
          </button>
        </div>
      </header>

      {showCriticalBanner && (
        <div className="dm-status-banner" role="alert">
          {isError ? (
            <>
              Could not load warehouse metadata. Check the API on port 8000 and{' '}
              <code>REACT_APP_API_KEY</code> in <code>frontend/.env</code>.
              <button type="button" className="dm-btn-ghost dm-status-banner__btn" onClick={onRefresh}>
                Retry
              </button>
            </>
          ) : (
            <>
              <strong>{bootstrap!.database_name}</strong> · profile {bootstrap!.profile}
              {notReady && ' — warehouse not ready.'}
              {legacy && ' — set DATAMART_PROFILE=tenant_etl in backend/.env.'}
              <button type="button" className="dm-btn-ghost dm-status-banner__btn" onClick={onRefresh}>
                Sync metadata
              </button>
            </>
          )}
        </div>
      )}
    </>
  )
}
