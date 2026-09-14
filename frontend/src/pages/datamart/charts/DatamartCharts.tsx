/**
 * Renders persisted chart definitions (v1) with Recharts from tabular data.
 */
import React, { useMemo } from 'react'
import { Loader2, X } from 'lucide-react'
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
} from 'recharts'
import type { DatamartChartConfigV1, DatamartChartType } from './chartConfig'
import { isDatamartChartConfigV1 } from './chartConfig'
import { filterRowsForChartScope } from './chartSuggestions'
import { getAlternativeChartTypes } from './chartTypeAlternatives'
import { chartHasCartesianAxes, sortChartRecords, swapChartAxes } from './chartAxisUtils'
import DatamartChartAxisControls from './DatamartChartAxisControls'
import DatamartChartTypeSwitcher from './DatamartChartTypeSwitcher'
import type { DatamartChartSortOrder } from './chartConfig'

import { dmChartPalette } from '../lib/tokens'

const PIE_COLORS = [...dmChartPalette]

function rowsToNamedRecords(
  columns: string[],
  rows: unknown[][],
): Record<string, unknown>[] {
  return rows.map((row) => {
    const rec: Record<string, unknown> = {}
    columns.forEach((c, i) => {
      rec[c] = row[i]
    })
    return rec
  })
}

function toNumber(v: unknown): number {
  if (v === null || v === undefined) return 0
  if (typeof v === 'number' && !Number.isNaN(v)) return v
  const n = Number(String(v).replace(/,/g, ''))
  return Number.isFinite(n) ? n : 0
}

function formatTooltipValue(value: unknown): string {
  const n = toNumber(value)
  const frac = Math.abs(n % 1) > 1e-9
  return n.toLocaleString(undefined, {
    maximumFractionDigits: frac ? 4 : 0,
    minimumFractionDigits: 0,
  })
}

function formatAxisNumber(v: unknown): string {
  if (typeof v === 'number' && Number.isFinite(v)) {
    return v.toLocaleString(undefined, { maximumFractionDigits: v % 1 !== 0 ? 2 : 0 })
  }
  return String(v ?? '')
}

const tooltipContentStyle: React.CSSProperties = {
  borderRadius: 8,
  border: '1px solid #e2e8f0',
  fontSize: 12,
  boxShadow: '0 4px 12px rgba(15, 23, 42, 0.08)',
}

function resolveDataset(
  chart: DatamartChartConfigV1,
  finalColumns: string[],
  finalRows: unknown[][],
  rawColumns: string[] | null | undefined,
  rawRows: unknown[][] | null | undefined,
): { data: Record<string, unknown>[]; error?: string } {
  if (chart.data_source === 'sql_raw' && rawColumns?.length && rawRows?.length) {
    const scoped = filterRowsForChartScope(rawColumns, rawRows, rawRows, chart.row_scope)
    return { data: rowsToNamedRecords(rawColumns, scoped) }
  }
  if (!finalColumns.length || !finalRows.length) {
    return { data: [], error: 'No tabular data for this chart.' }
  }
  const scoped = filterRowsForChartScope(finalColumns, finalRows, rawRows, chart.row_scope)
  return { data: rowsToNamedRecords(finalColumns, scoped) }
}

function chartRecordsForRecharts(
  data: Record<string, unknown>[],
  chart: DatamartChartConfigV1,
): { name: string; value: number }[] {
  const cat = chart.category_column
  const val = chart.value_column
  return data.map((row, idx) => ({
    name: String(row[cat] ?? `Row ${idx + 1}`),
    value: toNumber(row[val]),
  }))
}

export interface DatamartChartDatasetSlice {
  finalColumns: string[]
  finalRows: unknown[][]
  rawColumns?: string[] | null
  rawRows?: unknown[][] | null
}

export interface DatamartChartsProps {
  chartConfigs: unknown[] | null | undefined
  /** Primary SQL result (charts with no result_block_id). */
  primaryDataset: DatamartChartDatasetSlice
  /** keyed by block_id — charts with matching result_block_id use these rows. */
  blockDatasets?: Record<string, DatamartChartDatasetSlice>
  onRemoveChart?: (chartId: string) => void
  onChangeChartType?: (chartId: string, newType: DatamartChartType) => void
  onUpdateChart?: (chartId: string, chart: DatamartChartConfigV1) => void
  chartSaving?: boolean
  /** Minimal chrome for off-screen export capture. */
  exportMode?: boolean
}

const DatamartCharts: React.FC<DatamartChartsProps> = ({
  chartConfigs,
  primaryDataset,
  blockDatasets,
  onRemoveChart,
  onChangeChartType,
  onUpdateChart,
  chartSaving = false,
  exportMode = false,
}) => {
  const charts = useMemo(
    () => (chartConfigs ?? []).filter(isDatamartChartConfigV1) as DatamartChartConfigV1[],
    [chartConfigs],
  )

  if (charts.length === 0) return null

  return (
    <div
      className="dm-charts-stack"
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 20,
        marginTop: 4,
        position: 'relative',
        zIndex: 1,
        isolation: 'isolate',
      }}
    >
      {charts.map((chart) => {
        const bid = chart.result_block_id?.trim() || ''
        const slice =
          bid && blockDatasets && blockDatasets[bid] ? blockDatasets[bid] : primaryDataset
        const { data, error } = resolveDataset(
          chart,
          slice.finalColumns,
          slice.finalRows,
          slice.rawColumns,
          slice.rawRows,
        )
        if (error || !data.length) {
          return (
            <div
              key={chart.id}
              style={{
                padding: '14px 16px',
                borderRadius: 12,
                border: '1px solid #fecaca',
                background: '#fef2f2',
                fontSize: 13,
                color: '#b91c1c',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'flex-start' }}>
                <span>
                  {chart.title ? `${chart.title}: ` : ''}
                  {error ?? 'No rows available for this chart.'}
                </span>
                {onRemoveChart && (
                  <button
                    type="button"
                    disabled={chartSaving}
                    title="Remove chart"
                    aria-label="Remove chart"
                    onClick={() => onRemoveChart(chart.id)}
                    style={{
                      flexShrink: 0,
                      border: '1px solid #fecaca',
                      borderRadius: 6,
                      background: '#fff',
                      padding: 4,
                      cursor: chartSaving ? 'default' : 'pointer',
                      color: '#b91c1c',
                    }}
                  >
                    <X size={14} />
                  </button>
                )}
              </div>
            </div>
          )
        }

        const sortedData = sortChartRecords(data, chart)
        const pieData = chartRecordsForRecharts(sortedData, chart)
        const barData = sortedData

        const title = chart.title?.trim() || `${chart.chart_type} chart`
        const showLegend = chart.show_legend !== false
        const alternatives = getAlternativeChartTypes(chart, sortedData)
        const showTypeSwitcher =
          !exportMode && Boolean(onChangeChartType && alternatives.length > 0)
        const showAxisControls =
          !exportMode && chartHasCartesianAxes(chart.chart_type) && Boolean(onUpdateChart)
        const hasToolbar = showTypeSwitcher || showAxisControls

        return (
          <div
            key={chart.id}
            className="dm-chart-card"
            style={{
              border: '1px solid #e2e8f0',
              borderRadius: 14,
              overflow: 'visible',
              background: '#ffffff',
              position: 'relative',
              zIndex: 1,
              boxShadow: '0 1px 3px rgba(15, 23, 42, 0.06)',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 8,
                padding: '10px 14px',
                borderBottom: hasToolbar ? 'none' : '1px solid #f1f5f9',
                fontSize: 13,
                fontWeight: 600,
                color: '#334155',
              }}
            >
              <span style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis' }}>{title}</span>
              {!exportMode && onRemoveChart && (
                <button
                  type="button"
                  disabled={chartSaving}
                  title="Remove chart"
                  aria-label={`Remove chart: ${title}`}
                  onClick={() => onRemoveChart(chart.id)}
                  style={{
                    flexShrink: 0,
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    width: 28,
                    height: 28,
                    padding: 0,
                    border: '1px solid #e2e8f0',
                    borderRadius: 8,
                    background: chartSaving ? '#f8fafc' : '#ffffff',
                    color: chartSaving ? '#94a3b8' : '#64748b',
                    cursor: chartSaving ? 'default' : 'pointer',
                  }}
                  onMouseEnter={(e) => {
                    if (chartSaving) return
                    const el = e.currentTarget
                    el.style.background = '#fef2f2'
                    el.style.borderColor = '#fecaca'
                    el.style.color = '#dc2626'
                  }}
                  onMouseLeave={(e) => {
                    const el = e.currentTarget
                    el.style.background = chartSaving ? '#f8fafc' : '#ffffff'
                    el.style.borderColor = '#e2e8f0'
                    el.style.color = chartSaving ? '#94a3b8' : '#64748b'
                  }}
                >
                  {chartSaving ? (
                    <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} />
                  ) : (
                    <X size={14} />
                  )}
                </button>
              )}
            </div>
            {showTypeSwitcher && (
              <DatamartChartTypeSwitcher
                alternatives={alternatives}
                disabled={chartSaving}
                onSelect={(newType) => onChangeChartType!(chart.id, newType)}
              />
            )}
            {showAxisControls && (
              <DatamartChartAxisControls
                chart={chart}
                data={sortedData}
                disabled={chartSaving}
                onSwapAxes={() => onUpdateChart!(chart.id, swapChartAxes(chart))}
                onSortOrder={(order: DatamartChartSortOrder) =>
                  onUpdateChart!(chart.id, { ...chart, sort_order: order })
                }
              />
            )}
            <div
              data-chart-export-id={chart.id}
              className="dm-chart-plot"
              style={{
                padding: '8px 8px 16px',
                width: '100%',
                minHeight: 280,
                background: '#ffffff',
                overflow: 'visible',
              }}
            >
              <ResponsiveContainer width="100%" height={280}>
                {chart.chart_type === 'pie' ? (
                  <PieChart>
                    {showLegend && <Legend wrapperStyle={{ fontSize: 12 }} />}
                    <Tooltip
                      formatter={(v: unknown) => [formatTooltipValue(v), chart.value_column]}
                      contentStyle={tooltipContentStyle}
                    />
                    <Pie
                      data={pieData}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      outerRadius={100}
                      label={({ name, percent }) =>
                        `${name} (${(percent * 100).toFixed(0)}%)`
                      }
                    >
                      {pieData.map((_, i) => (
                        <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                      ))}
                    </Pie>
                  </PieChart>
                ) : chart.chart_type === 'line' ? (
                  <LineChart data={barData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                    <XAxis dataKey={chart.category_column} tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} tickFormatter={formatAxisNumber} />
                    <Tooltip
                      formatter={(v: unknown) => [formatTooltipValue(v), chart.value_column]}
                      labelFormatter={(l) => String(l ?? '')}
                      contentStyle={tooltipContentStyle}
                    />
                    {showLegend && <Legend wrapperStyle={{ fontSize: 12 }} />}
                    <Line
                      type="monotone"
                      dataKey={chart.value_column}
                      stroke="#0d9488"
                      strokeWidth={2}
                      dot={{ r: 3 }}
                    />
                  </LineChart>
                ) : chart.chart_type === 'bar' ? (
                  <BarChart
                    layout="vertical"
                    data={barData}
                    margin={{ top: 8, right: 16, left: 8, bottom: 0 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                    <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={formatAxisNumber} />
                    <YAxis
                      type="category"
                      dataKey={chart.category_column}
                      width={120}
                      tick={{ fontSize: 10 }}
                    />
                    <Tooltip
                      formatter={(v: unknown) => [formatTooltipValue(v), chart.value_column]}
                      labelFormatter={(l) => String(l ?? '')}
                      contentStyle={tooltipContentStyle}
                    />
                    {showLegend && <Legend wrapperStyle={{ fontSize: 12 }} />}
                    <Bar dataKey={chart.value_column} fill="#0f766e" radius={[0, 4, 4, 0]} />
                  </BarChart>
                ) : (
                  <BarChart data={barData} margin={{ top: 8, right: 16, left: 0, bottom: 32 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                    <XAxis
                      dataKey={chart.category_column}
                      tick={{ fontSize: 10 }}
                      angle={-25}
                      textAnchor="end"
                      height={70}
                    />
                    <YAxis tick={{ fontSize: 11 }} tickFormatter={formatAxisNumber} />
                    <Tooltip
                      formatter={(v: unknown) => [formatTooltipValue(v), chart.value_column]}
                      labelFormatter={(l) => String(l ?? '')}
                      contentStyle={tooltipContentStyle}
                    />
                    {showLegend && <Legend wrapperStyle={{ fontSize: 12 }} />}
                    <Bar dataKey={chart.value_column} fill="#0d9488" radius={[4, 4, 0, 0]} />
                  </BarChart>
                )}
              </ResponsiveContainer>
            </div>
          </div>
        )
      })}
    </div>
  )
}

export default DatamartCharts
