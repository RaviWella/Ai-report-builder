/**
 * Collapsible section primitive for datamart report cards.
 */
import React, { useCallback, useId, useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import type { ReportSectionPersist } from '../hooks/useReportSectionPersist'
import { dmColors, dmRadius, dmSpace } from '../lib/tokens'

export interface DatamartReportSectionProps {
  title: string
  badge?: string
  defaultOpen?: boolean
  open?: boolean
  onOpenChange?: (open: boolean) => void
  /** When set with `persist`, restores open state from sessionStorage. */
  sectionKey?: string
  persist?: ReportSectionPersist | null
  disabled?: boolean
  actions?: React.ReactNode
  children: React.ReactNode
}

const DatamartReportSection: React.FC<DatamartReportSectionProps> = ({
  title,
  badge,
  defaultOpen = false,
  open: controlledOpen,
  onOpenChange,
  sectionKey,
  persist,
  disabled = false,
  actions,
  children,
}) => {
  const [uncontrolledOpen, setUncontrolledOpen] = useState(() => {
    if (persist && sectionKey) return persist.getOpen(sectionKey, defaultOpen)
    return defaultOpen
  })
  const isControlled = controlledOpen !== undefined
  const persistedOpen =
    persist && sectionKey && !isControlled ? persist.getOpen(sectionKey, defaultOpen) : undefined
  const open = isControlled ? controlledOpen : (persistedOpen ?? uncontrolledOpen)
  const headerId = useId()
  const panelId = useId()

  const setOpen = useCallback(
    (next: boolean) => {
      if (disabled) return
      if (!isControlled) {
        setUncontrolledOpen(next)
        if (persist && sectionKey) persist.setOpen(sectionKey, next)
      }
      onOpenChange?.(next)
    },
    [disabled, isControlled, onOpenChange, persist, sectionKey],
  )

  const toggle = () => setOpen(!open)
  const expandLabel = open ? `Collapse ${title}` : `Expand ${title}`
  const isChartsPanel = sectionKey === 'charts'

  return (
    <section style={{ borderTop: `1px solid ${dmColors.borderLight}` }}>
      <button
        type="button"
        disabled={disabled}
        aria-expanded={open}
        aria-controls={panelId}
        aria-label={expandLabel}
        id={headerId}
        onClick={toggle}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: dmSpace.sm,
          width: '100%',
          padding: `${dmSpace.md}px ${dmSpace.lg}px`,
          background: open ? dmColors.surface : dmColors.surfaceMuted,
          border: 'none',
          cursor: disabled ? 'default' : 'pointer',
          textAlign: 'left',
          opacity: disabled ? 0.6 : 1,
          transition: 'background 0.15s ease',
        }}
      >
        {open ? (
          <ChevronDown size={16} color={dmColors.textMuted} aria-hidden />
        ) : (
          <ChevronRight size={16} color={dmColors.textMuted} aria-hidden />
        )}
        <span
          style={{
            flex: 1,
            fontSize: 12,
            fontWeight: 700,
            letterSpacing: '0.06em',
            textTransform: 'uppercase',
            color: dmColors.textMuted,
          }}
        >
          {title}
        </span>
        {badge && (
          <span
            style={{
              fontSize: 11,
              fontWeight: 500,
              color: dmColors.textMuted,
              padding: '2px 8px',
              borderRadius: dmRadius.pill,
              border: `1px solid ${dmColors.border}`,
              background: dmColors.surface,
            }}
          >
            {badge}
          </span>
        )}
        {actions && (
          <span onClick={(e) => e.stopPropagation()} onKeyDown={(e) => e.stopPropagation()}>
            {actions}
          </span>
        )}
      </button>
      {open && (
        <div
          id={panelId}
          role="region"
          aria-labelledby={headerId}
          className={isChartsPanel ? 'dm-report-section-panel--charts' : undefined}
          style={{
            padding: `${dmSpace.sm}px ${dmSpace.lg}px ${dmSpace.lg}px`,
            background: dmColors.surface,
            overflow: isChartsPanel ? 'visible' : undefined,
          }}
        >
          {children}
        </div>
      )}
    </section>
  )
}

export default DatamartReportSection

