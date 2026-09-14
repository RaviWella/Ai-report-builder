/**
 * Assistant error bubble with retry.
 */
import React from 'react'
import { AlertCircle, RotateCcw } from 'lucide-react'
import { dmColors, dmRadius, dmSpace } from '../lib/tokens'

export interface DatamartErrorTurnProps {
  message: string
  onRetry?: () => void
  retryDisabled?: boolean
}

const DatamartErrorTurn: React.FC<DatamartErrorTurnProps> = ({
  message,
  onRetry,
  retryDisabled,
}) => (
  <div
    style={{
      background: dmColors.dangerBg,
      border: `1px solid ${dmColors.dangerBorder}`,
      borderRadius: '4px 18px 18px 18px',
      padding: '12px 16px',
      maxWidth: '100%',
    }}
  >
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
      <AlertCircle size={16} color={dmColors.danger} style={{ flexShrink: 0, marginTop: 2 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <p style={{ margin: 0, fontSize: 14, color: dmColors.danger, lineHeight: 1.6 }}>{message}</p>
        {onRetry && (
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
      </div>
    </div>
  </div>
)

export default DatamartErrorTurn
