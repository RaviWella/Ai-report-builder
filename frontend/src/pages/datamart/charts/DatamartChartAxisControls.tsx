/**
 * X/Y labels, swap axes, and sort order for column / bar / line charts.
 */
import React from 'react'
import { ArrowDownUp, Repeat } from 'lucide-react'
import type { DatamartChartConfigV1, DatamartChartSortOrder } from './chartConfig'
import {
  SORT_ORDER_OPTIONS,
  canSwapAxes,
  chartHasCartesianAxes,
  getAxisLabels,
} from './chartAxisUtils'

export interface DatamartChartAxisControlsProps {
  chart: DatamartChartConfigV1
  data: Record<string, unknown>[]
  disabled?: boolean
  onSwapAxes: () => void
  onSortOrder: (order: DatamartChartSortOrder) => void
}

const DatamartChartAxisControls: React.FC<DatamartChartAxisControlsProps> = ({
  chart,
  data,
  disabled = false,
  onSwapAxes,
  onSortOrder,
}) => {
  if (!chartHasCartesianAxes(chart.chart_type)) return null

  const { x, y } = getAxisLabels(chart)
  const swapOk = canSwapAxes(chart, data)
  const sortOrder = chart.sort_order ?? 'original'

  return (
    <div
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        gap: 10,
        padding: '8px 14px',
        borderBottom: '1px solid #f1f5f9',
        background: '#fafafa',
      }}
    >
      <span
        style={{
          fontSize: 11,
          fontWeight: 600,
          color: '#64748b',
          display: 'inline-flex',
          alignItems: 'center',
          gap: 4,
        }}
      >
        <ArrowDownUp size={12} />
        Axes
      </span>
      <span style={{ fontSize: 11, color: '#475569' }}>
        <strong>X:</strong> {x}
      </span>
      <span style={{ fontSize: 11, color: '#475569' }}>
        <strong>Y:</strong> {y}
      </span>
      <button
        type="button"
        disabled={disabled || !swapOk}
        title={
          swapOk
            ? 'Swap which field is on X vs Y (category ↔ value)'
            : 'Swap is only available when the other field can be used as numeric values and labels'
        }
        onClick={onSwapAxes}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 4,
          fontSize: 11,
          fontWeight: 600,
          color: disabled || !swapOk ? '#94a3b8' : '#4f46e5',
          background: '#ffffff',
          border: `1px solid ${swapOk ? '#c7d2fe' : '#e2e8f0'}`,
          borderRadius: 16,
          padding: '4px 10px',
          cursor: disabled || !swapOk ? 'not-allowed' : 'pointer',
        }}
      >
        <Repeat size={12} />
        Swap X ↔ Y
      </button>
      <label
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          fontSize: 11,
          color: '#475569',
          marginLeft: 'auto',
        }}
      >
        <span style={{ fontWeight: 600 }}>Order</span>
        <select
          value={sortOrder}
          disabled={disabled}
          onChange={(e) => onSortOrder(e.target.value as DatamartChartSortOrder)}
          style={{
            fontSize: 11,
            border: '1px solid #e2e8f0',
            borderRadius: 8,
            padding: '4px 8px',
            background: '#ffffff',
            color: '#334155',
            maxWidth: 160,
          }}
        >
          {SORT_ORDER_OPTIONS.map((o) => (
            <option key={o.id} value={o.id}>
              {o.label}
            </option>
          ))}
        </select>
      </label>
    </div>
  )
}

export default DatamartChartAxisControls
