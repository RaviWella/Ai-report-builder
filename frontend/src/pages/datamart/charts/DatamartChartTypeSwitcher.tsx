/**
 * Lets users convert an appended chart to another viable type (same data binding).
 */
import React, { useState } from 'react'
import { ArrowLeftRight } from 'lucide-react'
import type { DatamartChartType } from './chartConfig'
import type { ChartTypeOption } from './chartTypeAlternatives'

export interface DatamartChartTypeSwitcherProps {
  alternatives: ChartTypeOption[]
  disabled?: boolean
  onSelect: (type: DatamartChartType) => void
}

const DatamartChartTypeSwitcher: React.FC<DatamartChartTypeSwitcherProps> = ({
  alternatives,
  disabled = false,
  onSelect,
}) => {
  const [hoverType, setHoverType] = useState<DatamartChartType | null>(null)

  if (!alternatives.length) return null

  const activeHint = hoverType
    ? alternatives.find((a) => a.type === hoverType)?.hint
    : 'Same data — different visual emphasis.'

  return (
    <div
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        gap: 8,
        padding: '8px 14px',
        borderBottom: '1px solid #f1f5f9',
        background: '#f8fafc',
      }}
    >
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 5,
          fontSize: 11,
          fontWeight: 600,
          color: '#64748b',
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
        }}
      >
        <ArrowLeftRight size={12} />
        View as
      </span>
      {alternatives.map((alt) => (
        <button
          key={alt.type}
          type="button"
          disabled={disabled}
          title={alt.hint}
          onMouseEnter={() => setHoverType(alt.type)}
          onMouseLeave={() => setHoverType(null)}
          onClick={() => onSelect(alt.type)}
          style={{
            fontSize: 11,
            fontWeight: 600,
            color: disabled ? '#94a3b8' : '#0f766e',
            background: '#ffffff',
            border: '1px solid #99f6e4',
            borderRadius: 16,
            padding: '4px 10px',
            cursor: disabled ? 'default' : 'pointer',
          }}
        >
          {alt.label}
        </button>
      ))}
      <span style={{ flex: '1 1 140px', fontSize: 11, color: '#94a3b8', lineHeight: 1.4 }}>
        {activeHint}
      </span>
    </div>
  )
}

export default DatamartChartTypeSwitcher
