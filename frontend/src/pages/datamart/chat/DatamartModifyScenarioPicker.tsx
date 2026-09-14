/**
 * Multi-select scenario chips shown in modify mode when the last report has 2+ scenarios.
 */
import React from 'react'
import { Check } from 'lucide-react'
import type { ScenarioDescriptor } from '../lib/reportLayout'
import { dmColors, dmRadius } from '../lib/tokens'

export interface DatamartModifyScenarioPickerProps {
  scenarios: ScenarioDescriptor[]
  selectedIds: string[]
  disabled?: boolean
  onChange: (ids: string[]) => void
}

const DatamartModifyScenarioPicker: React.FC<DatamartModifyScenarioPickerProps> = ({
  scenarios,
  selectedIds,
  disabled,
  onChange,
}) => {
  const selectedSet = new Set(selectedIds)
  const allSelected = scenarios.length > 0 && scenarios.every((s) => selectedSet.has(s.panelId))
  const noneSelected = selectedIds.length === 0

  const toggle = (panelId: string) => {
    if (disabled) return
    onChange(
      selectedIds.includes(panelId)
        ? selectedIds.filter((id) => id !== panelId)
        : [...selectedIds, panelId],
    )
  }

  const selectAll = () => {
    if (disabled || allSelected) return
    onChange(scenarios.map((s) => s.panelId))
  }

  const stopFormFocusSteal = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
  }

  return (
    <div
      role="group"
      aria-label="Scenarios to modify"
      onMouseDown={stopFormFocusSteal}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        paddingTop: 4,
        borderTop: `1px solid ${dmColors.borderLight}`,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          gap: 10,
          flexWrap: 'wrap',
        }}
      >
        <div style={{ minWidth: 0, flex: 1 }}>
          <div
            style={{
              fontSize: 11,
              fontWeight: 600,
              color: noneSelected ? dmColors.danger : dmColors.text,
              lineHeight: 1.35,
              letterSpacing: '0.01em',
            }}
          >
            Apply changes to
          </div>
          <div style={{ fontSize: 11, color: dmColors.textMuted, marginTop: 2, lineHeight: 1.4 }}>
            {noneSelected
              ? 'Select at least one scenario before sending.'
              : 'Only selected scenarios are updated (SQL, summaries, charts).'}
          </div>
        </div>
        <button
          type="button"
          disabled={disabled || allSelected}
          onMouseDown={stopFormFocusSteal}
          onClick={selectAll}
          style={{
            fontSize: 11,
            fontWeight: 600,
            color: dmColors.brand,
            background: 'transparent',
            border: 'none',
            cursor: disabled || allSelected ? 'default' : 'pointer',
            opacity: disabled || allSelected ? 0.45 : 1,
            padding: '2px 4px',
            flexShrink: 0,
          }}
        >
          Select all
        </button>
      </div>

      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 6,
          alignItems: 'center',
        }}
      >
        {scenarios.map((s) => {
          const on = selectedSet.has(s.panelId)
          const label = s.isPrimary ? 'Primary' : s.label
          return (
            <button
              key={s.panelId}
              type="button"
              disabled={disabled}
              aria-pressed={on}
              aria-label={`${on ? 'Deselect' : 'Select'} ${label}`}
              onMouseDown={stopFormFocusSteal}
              onClick={() => toggle(s.panelId)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 8,
                padding: '7px 12px 7px 8px',
                borderRadius: dmRadius.pill,
                border: `1px solid ${on ? dmColors.brand : dmColors.border}`,
                background: on ? dmColors.brandMuted : dmColors.surface,
                color: on ? dmColors.brand : dmColors.text,
                fontSize: 12,
                fontWeight: on ? 600 : 500,
                cursor: disabled ? 'not-allowed' : 'pointer',
                boxShadow: on
                  ? '0 0 0 1px rgba(13, 148, 136, 0.15)'
                  : '0 1px 2px rgba(15, 23, 42, 0.04)',
                maxWidth: 'min(100%, 280px)',
                transition: 'border-color 0.12s ease, background 0.12s ease, box-shadow 0.12s ease',
                opacity: disabled ? 0.55 : 1,
              }}
              title={s.label}
            >
              <span
                style={{
                  width: 18,
                  height: 18,
                  borderRadius: 5,
                  border: `2px solid ${on ? dmColors.brand : '#cbd5e1'}`,
                  background: on ? dmColors.brand : dmColors.surface,
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                  boxSizing: 'border-box',
                }}
                aria-hidden
              >
                {on ? <Check size={12} color="#fff" strokeWidth={3} /> : null}
              </span>
              <span
                style={{
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  textAlign: 'left',
                }}
              >
                {label}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}

export default DatamartModifyScenarioPicker
