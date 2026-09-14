/**
 * Contextual chart suggestions derived from the current result set (columns, rows, post-process).
 */
import React, { useState } from 'react'
import { BarChart3, Info, Plus, Sparkles } from 'lucide-react'
import type { ChartSuggestion } from './chartSuggestions'

export interface DatamartChartSuggestionsProps {
  suggestions: ChartSuggestion[]
  /** Shown in header so users know these ideas apply to one scenario only. */
  scenarioLabel?: string
  disabled?: boolean
  onApply: (suggestion: ChartSuggestion) => void
  onCustomize?: (suggestion: ChartSuggestion) => void
}

const DatamartChartSuggestions: React.FC<DatamartChartSuggestionsProps> = ({
  suggestions,
  scenarioLabel,
  disabled = false,
  onApply,
  onCustomize,
}) => {
  const [hoverId, setHoverId] = useState<string | null>(null)

  if (!suggestions.length) return null

  return (
    <div
      style={{
        marginTop: 10,
        marginBottom: 4,
        padding: '10px 12px',
        borderRadius: 10,
        border: '1px solid #99f6e4',
        background: '#f0fdfa',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
        <Sparkles size={14} color="#0d9488" />
        <span style={{ fontSize: 12, fontWeight: 600, color: '#0f766e' }}>
          {scenarioLabel
            ? `Suggested charts for “${scenarioLabel}”`
            : 'Suggested charts — one click to add'}
        </span>
        <span
          title="Based on your columns, row counts, and post-processing — not generic templates."
          style={{ display: 'inline-flex', cursor: 'help', color: '#64748b' }}
        >
          <Info size={13} />
        </span>
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {suggestions.map((s) => (
          <div
            key={s.id}
            style={{ position: 'relative' }}
            onMouseEnter={() => setHoverId(s.id)}
            onMouseLeave={() => setHoverId(null)}
          >
            <button
              type="button"
              disabled={disabled}
              onClick={() => onApply(s)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                fontSize: 12,
                fontWeight: 500,
                color: disabled ? '#94a3b8' : '#0f766e',
                background: '#ffffff',
                border: '1px solid #99f6e4',
                borderRadius: 20,
                padding: '5px 12px',
                cursor: disabled ? 'default' : 'pointer',
                boxShadow: hoverId === s.id ? '0 2px 8px rgba(13,148,136,0.12)' : 'none',
                transition: 'box-shadow 0.15s',
              }}
            >
              <BarChart3 size={12} />
              {s.label}
              <Plus size={11} style={{ opacity: 0.75 }} />
            </button>
            {hoverId === s.id && (
              <div
                role="tooltip"
                style={{
                  position: 'absolute',
                  zIndex: 20,
                  left: 0,
                  top: 'calc(100% + 6px)',
                  minWidth: 260,
                  maxWidth: 320,
                  padding: '10px 12px',
                  fontSize: 11,
                  lineHeight: 1.55,
                  color: '#334155',
                  background: '#ffffff',
                  border: '1px solid #e2e8f0',
                  borderRadius: 10,
                  boxShadow: '0 8px 24px rgba(15,23,42,0.12)',
                  pointerEvents: onCustomize ? 'auto' : 'none',
                }}
              >
                {s.tooltip}
                {onCustomize && (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation()
                      onCustomize(s)
                    }}
                    style={{
                      marginTop: 8,
                      fontSize: 11,
                      fontWeight: 600,
                      color: '#0d9488',
                      background: 'none',
                      border: 'none',
                      padding: 0,
                      cursor: 'pointer',
                      textDecoration: 'underline',
                    }}
                  >
                    Customize before adding…
                  </button>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

export default DatamartChartSuggestions
