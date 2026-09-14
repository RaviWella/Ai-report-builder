/**
 * Compact follow-up mode: modify last result vs new question.
 */
import React from 'react'
import { Layers, Link2, MessageSquarePlus } from 'lucide-react'
import {
  FOLLOW_UP_MODE_OPTIONS,
  type DatamartFollowUpMode,
} from '../lib/followUpMode'
import { dmColors, dmRadius } from '../lib/tokens'

export interface DatamartFollowUpModeToggleProps {
  mode: DatamartFollowUpMode
  lastQuestionLabel: string
  disabled?: boolean
  /** When true, hides inline context text (toolbar uses title tooltips only). */
  embedded?: boolean
  onChange: (mode: DatamartFollowUpMode) => void
}

const DatamartFollowUpModeToggle: React.FC<DatamartFollowUpModeToggleProps> = ({
  mode,
  lastQuestionLabel,
  disabled,
  embedded = false,
  onChange,
}) => {
  const continueTitle =
    mode === 'continue_last'
      ? `Modify last result: ${lastQuestionLabel}`
      : undefined
  const scenarioTitle =
    mode === 'add_scenario'
      ? 'Add a new dataset to this report (previous table stays unchanged)'
      : undefined

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        flexShrink: 0,
        width: embedded ? '100%' : undefined,
        maxWidth: '100%',
      }}
      role="radiogroup"
      aria-label="Follow-up mode"
    >
      <div
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 2,
          padding: 2,
          borderRadius: dmRadius.pill,
          background: dmColors.surfaceMuted,
          border: `1px solid ${dmColors.border}`,
          width: embedded ? '100%' : undefined,
        }}
      >
        {FOLLOW_UP_MODE_OPTIONS.map((opt) => {
          const selected = mode === opt.id
          const Icon =
            opt.id === 'continue_last'
              ? Link2
              : opt.id === 'add_scenario'
                ? Layers
                : MessageSquarePlus
          const shortLabel = opt.shortLabel
          const title =
            opt.id === 'continue_last' && continueTitle
              ? `${opt.label} — ${continueTitle}`
              : opt.id === 'add_scenario' && scenarioTitle
                ? `${opt.label} — ${scenarioTitle}`
                : `${opt.label} — ${opt.description}`
          return (
            <button
              key={opt.id}
              type="button"
              role="radio"
              aria-checked={selected}
              disabled={disabled}
              title={title}
              onClick={() => onChange(opt.id)}
              style={{
                flex: embedded ? 1 : undefined,
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 4,
                padding: '4px 8px',
                borderRadius: dmRadius.pill,
                border: 'none',
                background: selected ? dmColors.surface : 'transparent',
                color: selected ? dmColors.brand : dmColors.textMuted,
                fontSize: 11,
                fontWeight: selected ? 600 : 500,
                cursor: disabled ? 'default' : 'pointer',
                boxShadow: selected ? '0 1px 2px rgba(15, 23, 42, 0.06)' : 'none',
                whiteSpace: 'nowrap',
                minWidth: 0,
              }}
            >
              <Icon size={12} aria-hidden style={{ flexShrink: 0 }} />
              <span>{shortLabel}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}

export default DatamartFollowUpModeToggle
