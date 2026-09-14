/**
 * Contextual follow-up chips for the latest report turn.
 */
import React, { useEffect, useRef, useState } from 'react'
import { BarChart3, Filter, ListOrdered, X } from 'lucide-react'
import type { LatestTurnContext } from '../lib/latestTurnContext'
import {
  buildFilterPrompt,
  buildRemoveColumnPrompt,
  buildSortPrompt,
} from '../lib/quickActionPrompts'
import { dmColors, dmRadius, dmSpace } from '../lib/tokens'

export interface DatamartQuickActionsProps {
  context: LatestTurnContext
  disabled?: boolean
  compact?: boolean
  onSendFollowUp: (prompt: string) => void
  onAddChart?: () => void
}

type Panel = 'none' | 'remove' | 'filter' | 'sort'

const chipBase: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 4,
  fontWeight: 600,
  borderRadius: dmRadius.pill,
  cursor: 'pointer',
  border: `1px solid ${dmColors.border}`,
  background: dmColors.surface,
  color: dmColors.textMuted,
  whiteSpace: 'nowrap',
  flexShrink: 0,
}

const DatamartQuickActions: React.FC<DatamartQuickActionsProps> = ({
  context,
  disabled,
  compact = false,
  onSendFollowUp,
  onAddChart,
}) => {
  const chipStyle: React.CSSProperties = {
    ...chipBase,
    fontSize: compact ? 11 : 12,
    padding: compact ? '3px 8px' : '6px 12px',
  }
  const [panel, setPanel] = useState<Panel>('none')
  const [filterText, setFilterText] = useState('')
  const panelRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setPanel('none')
    setFilterText('')
  }, [context.messageId])

  useEffect(() => {
    if (panel === 'none') return undefined
    const onDoc = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setPanel('none')
      }
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [panel])

  if (!context.sql) return null

  const hasColumns = context.columns.length > 0

  const submitFilter = () => {
    const t = filterText.trim()
    if (!t) return
    onSendFollowUp(buildFilterPrompt(t))
    setPanel('none')
    setFilterText('')
  }

  const panelSurface: React.CSSProperties = {
    padding: compact ? dmSpace.sm : dmSpace.md,
    borderRadius: dmRadius.md,
    border: `1px solid ${dmColors.border}`,
    background: dmColors.surface,
    boxShadow: compact ? '0 -8px 24px rgba(15, 23, 42, 0.12)' : undefined,
  }

  const panelPosition: React.CSSProperties = compact
    ? {
        position: 'absolute',
        left: 0,
        right: 0,
        bottom: 'calc(100% + 4px)',
        zIndex: 30,
        maxHeight: 200,
        overflowY: 'auto',
      }
    : {
        marginTop: dmSpace.sm,
      }

  return (
    <div
      style={{
        marginBottom: compact ? 0 : dmSpace.md,
        minWidth: compact ? 0 : undefined,
        width: compact ? '100%' : undefined,
        maxWidth: '100%',
        position: compact ? 'relative' : undefined,
      }}
      ref={panelRef}
      data-testid="datamart-quick-actions"
    >
      {!compact && (
        <p
          style={{
            margin: `0 0 ${dmSpace.sm}px`,
            fontSize: 11,
            fontWeight: 600,
            color: dmColors.textSubtle,
            letterSpacing: '0.04em',
            textTransform: 'uppercase',
          }}
        >
          Quick actions
        </p>
      )}
      <div
        style={{
          display: 'flex',
          flexWrap: compact ? 'nowrap' : 'wrap',
          gap: compact ? 6 : 8,
          alignItems: 'center',
          overflowX: compact ? 'auto' : undefined,
          overflowY: 'hidden',
          paddingBottom: compact ? 2 : 0,
          WebkitOverflowScrolling: 'touch',
        }}
      >
        <button
          type="button"
          data-testid="datamart-quick-remove-column"
          disabled={disabled || !hasColumns}
          title={hasColumns ? undefined : 'Run query first to pick a column'}
          onClick={() => setPanel((p) => (p === 'remove' ? 'none' : 'remove'))}
          style={{
            ...chipStyle,
            opacity: disabled || !hasColumns ? 0.45 : 1,
            cursor: disabled || !hasColumns ? 'default' : 'pointer',
            borderColor: panel === 'remove' ? dmColors.brandBorder : dmColors.border,
            background: panel === 'remove' ? dmColors.brandMuted : dmColors.surface,
            color: panel === 'remove' ? dmColors.brand : dmColors.textMuted,
          }}
        >
          <X size={11} />
          {compact ? 'Column' : 'Remove column'}
        </button>

        <button
          type="button"
          disabled={disabled}
          onClick={() => setPanel((p) => (p === 'filter' ? 'none' : 'filter'))}
          style={{
            ...chipStyle,
            opacity: disabled ? 0.45 : 1,
            borderColor: panel === 'filter' ? dmColors.brandBorder : dmColors.border,
            background: panel === 'filter' ? dmColors.brandMuted : dmColors.surface,
            color: panel === 'filter' ? dmColors.brand : dmColors.textMuted,
          }}
        >
          <Filter size={11} />
          Filter
        </button>

        <button
          type="button"
          disabled={disabled || !hasColumns}
          title={hasColumns ? undefined : 'Run query first to pick a column'}
          onClick={() => setPanel((p) => (p === 'sort' ? 'none' : 'sort'))}
          style={{
            ...chipStyle,
            opacity: disabled || !hasColumns ? 0.45 : 1,
            cursor: disabled || !hasColumns ? 'default' : 'pointer',
            borderColor: panel === 'sort' ? dmColors.brandBorder : dmColors.border,
            background: panel === 'sort' ? dmColors.brandMuted : dmColors.surface,
            color: panel === 'sort' ? dmColors.brand : dmColors.textMuted,
          }}
        >
          <ListOrdered size={11} />
          Sort
        </button>

        {onAddChart && (
          <button
            type="button"
            disabled={disabled || !context.canGenerateChart}
            title={
              context.canGenerateChart
                ? undefined
                : 'Run query and load results to add a chart'
            }
            onClick={onAddChart}
            style={{
              ...chipStyle,
              opacity: disabled || !context.canGenerateChart ? 0.45 : 1,
              cursor: disabled || !context.canGenerateChart ? 'default' : 'pointer',
              color: dmColors.purple,
              borderColor: dmColors.purpleBorder,
              background: dmColors.purpleBg,
            }}
          >
            <BarChart3 size={11} />
            {compact ? 'Chart' : 'Add chart'}
          </button>
        )}
      </div>

      {panel === 'remove' && hasColumns && (
        <div
          style={{
            ...panelSurface,
            ...panelPosition,
            display: 'flex',
            flexWrap: 'wrap',
            gap: 6,
          }}
        >
          {context.columns.map((col) => (
            <button
              key={col}
              type="button"
              disabled={disabled}
              onClick={() => {
                onSendFollowUp(buildRemoveColumnPrompt(col))
                setPanel('none')
              }}
              style={{
                ...chipStyle,
                fontSize: 11,
                padding: '4px 10px',
              }}
            >
              {col}
            </button>
          ))}
        </div>
      )}

      {panel === 'filter' && (
        <div
          style={{
            ...panelSurface,
            ...panelPosition,
          }}
        >
          <input
            type="text"
            value={filterText}
            onChange={(e) => setFilterText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                submitFilter()
              }
            }}
            placeholder="e.g. only Head Office branch"
            disabled={disabled}
            style={{
              width: '100%',
              boxSizing: 'border-box',
              fontSize: 13,
              border: `1px solid ${dmColors.border}`,
              borderRadius: dmRadius.sm,
              padding: '8px 10px',
              marginBottom: 8,
            }}
          />
          <button
            type="button"
            disabled={disabled || !filterText.trim()}
            onClick={submitFilter}
            style={{
              ...chipStyle,
              color: dmColors.brand,
              borderColor: dmColors.brandBorder,
              background: dmColors.brandMuted,
            }}
          >
            Apply filter
          </button>
        </div>
      )}

      {panel === 'sort' && hasColumns && (
        <div
          style={{
            ...panelSurface,
            ...panelPosition,
            display: 'flex',
            flexDirection: 'column',
            gap: 6,
          }}
        >
          {context.columns.map((col) => (
            <div key={col} style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              <button
                type="button"
                disabled={disabled}
                onClick={() => {
                  onSendFollowUp(buildSortPrompt(col, 'asc'))
                  setPanel('none')
                }}
                style={{ ...chipStyle, fontSize: 11 }}
              >
                {col} ↑
              </button>
              <button
                type="button"
                disabled={disabled}
                onClick={() => {
                  onSendFollowUp(buildSortPrompt(col, 'desc'))
                  setPanel('none')
                }}
                style={{ ...chipStyle, fontSize: 11 }}
              >
                {col} ↓
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default DatamartQuickActions
