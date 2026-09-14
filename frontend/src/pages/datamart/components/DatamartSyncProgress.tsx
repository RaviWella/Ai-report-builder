/**
 * Progress steps while full datamart sync runs (Sync button).
 */
import React from 'react'
import { AlertCircle, Check, Loader2 } from 'lucide-react'
import type { DatamartSyncStep } from '../lib/datamartSyncSteps'
import { dmColors } from '../lib/tokens'

export interface DatamartSyncProgressProps {
  steps: DatamartSyncStep[]
}

function StepIcon({ status }: { status: DatamartSyncStep['status'] }) {
  if (status === 'completed') {
    return <Check size={14} color={dmColors.brand} aria-hidden />
  }
  if (status === 'running') {
    return (
      <Loader2
        size={14}
        color={dmColors.brand}
        style={{ animation: 'spin 1s linear infinite' }}
        aria-hidden
      />
    )
  }
  if (status === 'failed') {
    return <AlertCircle size={14} color="#b91c1c" aria-hidden />
  }
  return (
    <span
      style={{
        width: 14,
        height: 14,
        borderRadius: '50%',
        border: `2px solid ${dmColors.border}`,
        flexShrink: 0,
      }}
      aria-hidden
    />
  )
}

const DatamartSyncProgress: React.FC<DatamartSyncProgressProps> = ({ steps }) => {
  const running = steps.some((s) => s.status === 'running')

  return (
    <div
      className="dm-sync-progress"
      role="status"
      aria-live="polite"
      aria-busy={running}
      data-testid="datamart-sync-progress"
    >
      <p className="dm-sync-progress__title">Syncing warehouse &amp; catalog</p>
      <ul className="dm-sync-progress__list">
        {steps.map((step) => (
          <li
            key={step.id}
            className="dm-sync-progress__item"
            data-status={step.status}
            data-testid={`sync-step-${step.id}`}
          >
            <span className="dm-sync-progress__icon">
              <StepIcon status={step.status} />
            </span>
            <span className="dm-sync-progress__body">
              <span
                className="dm-sync-progress__label"
                style={{ fontWeight: step.status === 'running' ? 600 : 400 }}
              >
                {step.label}
              </span>
              {step.detail && (
                <span className="dm-sync-progress__detail">{step.detail}</span>
              )}
            </span>
          </li>
        ))}
      </ul>
      <p className="dm-sync-progress__hint">
        Large warehouses may take 1–2 minutes. Please keep this tab open.
      </p>
    </div>
  )
}

export default DatamartSyncProgress
