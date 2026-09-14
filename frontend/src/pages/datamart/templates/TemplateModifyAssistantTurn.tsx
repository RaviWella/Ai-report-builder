/**
 * Compact assistant turn in the modify-chat column (full report lives in draft preview).
 */
import React from 'react'
import { CheckCircle2, AlertCircle, RotateCcw } from 'lucide-react'
import type { DatamartResponse } from '../../../services/datamartService'
import { dmColors, dmRadius, dmSpace } from '../lib/tokens'

export interface TemplateModifyAssistantTurnProps {
  data: DatamartResponse
  onRetry?: () => void
  retryDisabled?: boolean
}

const TemplateModifyAssistantTurn: React.FC<TemplateModifyAssistantTurnProps> = ({
  data,
  onRetry,
  retryDisabled,
}) => {
  const hasError = !!data.error
  const narrative = data.narrative?.trim()
  const sqlChanged = !!data.sql?.trim()

  return (
    <div
      style={{
        borderRadius: dmRadius.md,
        border: `1px solid ${hasError ? '#fecaca' : dmColors.border}`,
        background: hasError ? '#fef2f2' : dmColors.surfaceMuted,
        padding: `${dmSpace.sm}px ${dmSpace.md}px`,
        fontSize: 13,
        lineHeight: 1.55,
        color: dmColors.text,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
        {hasError ? (
          <AlertCircle size={16} color={dmColors.danger} style={{ flexShrink: 0, marginTop: 2 }} />
        ) : (
          <CheckCircle2 size={16} color={dmColors.brand} style={{ flexShrink: 0, marginTop: 2 }} />
        )}
        <div style={{ minWidth: 0, flex: 1 }}>
          <p style={{ margin: 0, fontWeight: 600, fontSize: 12, color: dmColors.textMuted }}>
            {hasError ? 'Modification issue' : 'Modification ready'}
          </p>
          {narrative && (
            <p style={{ margin: `${dmSpace.xs}px 0 0`, color: dmColors.text }}>{narrative}</p>
          )}
          {hasError && (
            <p style={{ margin: `${dmSpace.xs}px 0 0`, color: dmColors.danger }}>{data.error}</p>
          )}
          {hasError && onRetry && (
            <button
              type="button"
              onClick={onRetry}
              disabled={retryDisabled}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                marginTop: dmSpace.sm,
                fontSize: 12,
                fontWeight: 600,
                color: dmColors.danger,
                background: dmColors.surface,
                border: `1px solid ${dmColors.dangerBorder}`,
                borderRadius: dmRadius.sm,
                padding: '6px 10px',
                cursor: retryDisabled ? 'default' : 'pointer',
                opacity: retryDisabled ? 0.6 : 1,
              }}
            >
              <RotateCcw size={12} />
              Try again
            </button>
          )}
          {sqlChanged && !hasError && (
            <p style={{ margin: `${dmSpace.xs}px 0 0`, fontSize: 12, color: dmColors.textSubtle }}>
              SQL updated — review and run query in the draft preview on the right, then save when ready.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

export default TemplateModifyAssistantTurn
