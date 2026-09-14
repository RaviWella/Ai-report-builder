/**
 * Presents post-process appended rows (per-group averages, grand totals) outside
 * the main detail grid — card layout with formatted numbers.
 * Charts are user-driven only (Generate chart); no charts are rendered here.
 */
import React, { useMemo } from 'react'
import { Sparkles } from 'lucide-react'
import { dmColors } from '../lib/tokens'
import { buildAggregationMetricLabels, lastAppendStep } from './datamartResultSplit'

function formatHeader(col: string): string {
  return col
    .replace(/_/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

function formatMetric(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'number' && !Number.isNaN(value)) {
    if (!Number.isFinite(value)) return '—'
    const abs = Math.abs(value)
    const frac = abs % 1 !== 0
    if (frac) {
      return value.toLocaleString(undefined, { maximumFractionDigits: 2, minimumFractionDigits: 0 })
    }
    return value.toLocaleString(undefined, { maximumFractionDigits: 0 })
  }
  return String(value)
}

function labelColumnHint(
  step: Record<string, unknown> | null,
  columns: string[],
): string | undefined {
  if (!step) return undefined
  const raw = step.label_column
  if (typeof raw !== 'string' || !raw.trim()) return undefined
  const want = raw.trim()
  const exact = columns.find((c) => c === want)
  if (exact) return exact
  const low = want.toLowerCase()
  return columns.find((c) => c.toLowerCase() === low)
}

export interface DatamartPostProcessSummariesProps {
  columns: string[]
  summaryRows: unknown[][]
  postProcessConfig: Array<Record<string, unknown>> | null | undefined
}

const DatamartPostProcessSummaries: React.FC<DatamartPostProcessSummariesProps> = ({
  columns,
  summaryRows,
  postProcessConfig,
}) => {
  const step = useMemo(() => lastAppendStep(postProcessConfig), [postProcessConfig])
  const metricLabels = useMemo(
    () => buildAggregationMetricLabels(step, columns),
    [step, columns],
  )
  const labelCol = useMemo(() => labelColumnHint(step, columns), [step, columns])
  const labelIdx = labelCol ? columns.indexOf(labelCol) : -1

  return (
    <section
      style={{
        borderTop: `1px solid ${dmColors.brandBorder}`,
        background: dmColors.surface,
        padding: '14px 16px 16px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <Sparkles size={16} color={dmColors.brand} />
        <span
          style={{
            fontSize: 12,
            fontWeight: 600,
            color: dmColors.brand,
          }}
        >
          Post-process summaries
        </span>
        <span
          style={{
            marginLeft: 'auto',
            fontSize: 11,
            color: '#64748b',
            fontWeight: 500,
            padding: '2px 8px',
            background: '#f5f3ff',
            borderRadius: 20,
            border: '1px solid #e9d5ff',
          }}
        >
          {summaryRows.length} {summaryRows.length === 1 ? 'row' : 'rows'}
        </span>
      </div>
      <p style={{ margin: '0 0 14px', fontSize: 12, color: '#64748b', lineHeight: 1.55 }}>
        Derived from your query result (not raw SQL rows). Values are formatted for readability.
        Use <strong>Generate chart</strong> above if you want a chart — none are added automatically.
      </p>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
          gap: 12,
        }}
      >
        {summaryRows.map((row, rIdx) => {
          const title =
            labelIdx >= 0 && row[labelIdx] != null && row[labelIdx] !== ''
              ? String(row[labelIdx])
              : `Summary ${rIdx + 1}`

          const aggColSet = metricLabels.size > 0 ? new Set(metricLabels.keys()) : null
          const cells = columns
            .map((col, i) => ({ col, i, v: row[i] }))
            .filter(({ i }) => i !== labelIdx)
            .filter(({ v }) => v !== null && v !== undefined && v !== '')
            .filter(({ col }) => !aggColSet || aggColSet.has(col))
            .map(({ col, v }) => ({
              col,
              v,
              label: metricLabels.get(col) ?? formatHeader(col),
            }))

          return (
            <div
              key={rIdx}
              style={{
                border: '1px solid #e9d5ff',
                borderRadius: 12,
                padding: '12px 14px',
                background: '#ffffff',
                boxShadow: '0 1px 2px rgba(91, 33, 182, 0.06)',
              }}
            >
              <div
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: '#4c1d95',
                  marginBottom: cells.length > 0 ? 10 : 0,
                  lineHeight: 1.4,
                  borderBottom: cells.length > 0 ? '1px solid #f3e8ff' : undefined,
                  paddingBottom: cells.length > 0 ? 8 : 0,
                }}
              >
                {title}
              </div>
              {cells.length === 1 ? (
                <div
                  style={{
                    fontSize: 28,
                    fontWeight: 700,
                    color: '#0f766e',
                    fontVariantNumeric: 'tabular-nums',
                    lineHeight: 1.2,
                    marginTop: 4,
                  }}
                >
                  {formatMetric(cells[0].v)}
                </div>
              ) : cells.length > 1 ? (
                <dl style={{ margin: 0, display: 'grid', gap: 6 }}>
                  {cells.map(({ col, v, label }) => (
                    <div
                      key={col}
                      style={{
                        display: 'grid',
                        gridTemplateColumns: '1fr auto',
                        gap: 8,
                        alignItems: 'baseline',
                        fontSize: 12,
                      }}
                    >
                      <dt style={{ margin: 0, color: '#64748b', fontWeight: 500 }}>{label}</dt>
                      <dd
                        style={{
                          margin: 0,
                          fontWeight: 600,
                          color: '#0f766e',
                          fontVariantNumeric: 'tabular-nums',
                          textAlign: 'right',
                        }}
                      >
                        {formatMetric(v)}
                      </dd>
                    </div>
                  ))}
                </dl>
              ) : null}
            </div>
          )
        })}
      </div>
    </section>
  )
}

export default DatamartPostProcessSummaries
