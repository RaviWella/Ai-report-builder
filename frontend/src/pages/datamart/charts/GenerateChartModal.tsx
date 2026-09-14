/**
 * Multi-step modal to add a custom chart (schema v1) from the current result columns.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react'
import {
  X,
  ChevronLeft,
  BarChart3,
  BarChartHorizontal,
  LineChart,
  PieChart,
  type LucideIcon,
} from 'lucide-react'
import { v4 as uuidv4 } from 'uuid'
import type {
  DatamartChartConfigV1,
  DatamartChartType,
  DatamartChartRowScope,
} from './chartConfig'
import { dmColors, dmRadius } from '../lib/tokens'
import {
  analyzeDatasetColumns,
  getAxisFieldLabels,
  getRowScopeOptions,
  isValidAxisPair,
  pickDefaultAxisColumns,
  type DatasetColumnRoles,
} from '../lib/chartColumnRoles'

export interface ChartDatasetOption {
  result_block_id: string | null
  label: string
  columns: string[]
  rows: unknown[][]
  raw_columns?: string[] | null
  raw_rows?: unknown[][] | null
  post_process_config?: Array<Record<string, unknown>> | null
  hasRawSnapshot: boolean
}

export interface GenerateChartModalProps {
  open: boolean
  onClose: () => void
  datasets: ChartDatasetOption[]
  initialDraft?: DatamartChartConfigV1 | null
  /** Pre-select scenario when opening (e.g. active report tab). */
  initialDatasetKey?: string | null
  onSave: (chart: DatamartChartConfigV1) => void
}

type WizardStep = 'type' | 'configure'

const CHART_TYPE_OPTIONS: Array<{
  id: DatamartChartType
  label: string
  description: string
  Icon: LucideIcon
}> = [
  {
    id: 'column',
    label: 'Column',
    description: 'Compare values across categories (vertical bars)',
    Icon: BarChart3,
  },
  {
    id: 'bar',
    label: 'Bar',
    description: 'Horizontal bars — good for long category names',
    Icon: BarChartHorizontal,
  },
  {
    id: 'line',
    label: 'Line',
    description: 'Trends and sequences over categories',
    Icon: LineChart,
  },
  {
    id: 'pie',
    label: 'Pie',
    description: 'Share of a total across a few categories',
    Icon: PieChart,
  },
]

const selectStyle: React.CSSProperties = {
  fontSize: 13,
  padding: '8px 10px',
  borderRadius: 8,
  border: `1px solid ${dmColors.border}`,
  background: dmColors.surface,
  width: '100%',
}

const labelStyle: React.CSSProperties = {
  fontSize: 12,
  fontWeight: 600,
  color: '#475569',
}

function applyDefaultAxes(
  roles: DatasetColumnRoles,
  columns: string[],
  rows: unknown[][],
  setCategory: (v: string) => void,
  setValue: (v: string) => void,
): void {
  const picked = pickDefaultAxisColumns(roles, columns, rows)
  if (picked) {
    setCategory(picked.categoryColumn)
    setValue(picked.valueColumn)
    return
  }
  if (roles.categoryColumns[0]) setCategory(roles.categoryColumns[0])
  if (roles.valueColumns[0]) setValue(roles.valueColumns[0])
}

function datasetKey(d: ChartDatasetOption): string {
  return d.result_block_id ?? '__primary__'
}

const GenerateChartModal: React.FC<GenerateChartModalProps> = ({
  open,
  onClose,
  datasets,
  initialDraft,
  initialDatasetKey,
  onSave,
}) => {
  const [step, setStep] = useState<WizardStep>('type')
  const [chartType, setChartType] = useState<DatamartChartType>('column')
  const [selectedDatasetKey, setSelectedDatasetKey] = useState<string>('__primary__')
  const [categoryColumn, setCategoryColumn] = useState('')
  const [valueColumn, setValueColumn] = useState('')
  const [title, setTitle] = useState('')
  const [showLegend, setShowLegend] = useState(true)
  const [rowScope, setRowScope] = useState<DatamartChartRowScope>('all')

  const multiScenario = datasets.length > 1

  const activeDataset =
    datasets.find((d) => datasetKey(d) === selectedDatasetKey) ?? datasets[0]

  const { columns: activeColumns, rows: activeRows } = useMemo(() => {
    if (!activeDataset) return { columns: [] as string[], rows: [] as unknown[][] }
    return { columns: activeDataset.columns, rows: activeDataset.rows }
  }, [activeDataset])

  const columnRoles = useMemo(
    () => analyzeDatasetColumns(activeColumns, activeRows),
    [activeColumns, activeRows],
  )

  const axisLabels = useMemo(() => getAxisFieldLabels(chartType), [chartType])

  const rowScopeOptions = useMemo(() => {
    if (!activeDataset) return []
    return getRowScopeOptions(
      activeDataset.columns,
      activeDataset.rows,
      activeDataset.raw_rows ?? null,
      activeDataset.post_process_config ?? null,
    )
  }, [activeDataset])

  const resetForm = useCallback(() => {
    setStep(initialDraft ? 'configure' : 'type')
    setChartType(initialDraft?.chart_type ?? 'column')
    const draftKey = initialDraft?.result_block_id ?? null
    const preferredKey = initialDatasetKey ?? '__primary__'
    const keyFromDraft = draftKey ?? preferredKey
    const validKey = datasets.some((d) => datasetKey(d) === keyFromDraft)
      ? keyFromDraft
      : (datasets[0] ? datasetKey(datasets[0]) : '__primary__')
    setSelectedDatasetKey(validKey)
    setCategoryColumn(initialDraft?.category_column ?? '')
    setValueColumn(initialDraft?.value_column ?? '')
    setTitle(initialDraft?.title ?? '')
    setShowLegend(initialDraft?.show_legend !== false)
    setRowScope(initialDraft?.row_scope ?? 'all')
  }, [initialDraft, initialDatasetKey, datasets])

  useEffect(() => {
    if (!open) return
    resetForm()
  }, [open, resetForm])

  useEffect(() => {
    if (!open || !datasets.length) return
    if (!datasets.some((d) => datasetKey(d) === selectedDatasetKey)) {
      setSelectedDatasetKey(datasetKey(datasets[0]))
    }
  }, [open, datasets, selectedDatasetKey])

  useEffect(() => {
    if (!open || initialDraft) return
    setCategoryColumn('')
    setValueColumn('')
    setRowScope('all')
  }, [open, initialDraft, selectedDatasetKey])

  const selectScenario = (key: string) => {
    if (key === selectedDatasetKey) return
    setSelectedDatasetKey(key)
    if (!initialDraft) {
      setCategoryColumn('')
      setValueColumn('')
      setRowScope('all')
    }
  }

  useEffect(() => {
    if (!open || initialDraft) return
    if (step !== 'configure') return
    if (categoryColumn && valueColumn) return
    applyDefaultAxes(columnRoles, activeColumns, activeRows, setCategoryColumn, setValueColumn)
  }, [
    open,
    initialDraft,
    step,
    columnRoles,
    activeColumns,
    activeRows,
    categoryColumn,
    valueColumn,
  ])

  useEffect(() => {
    if (!open || step !== 'configure') return
    if (
      categoryColumn &&
      valueColumn &&
      isValidAxisPair(categoryColumn, valueColumn, columnRoles)
    ) {
      return
    }
    applyDefaultAxes(columnRoles, activeColumns, activeRows, setCategoryColumn, setValueColumn)
  }, [
    open,
    step,
    selectedDatasetKey,
    chartType,
    columnRoles,
    activeColumns,
    activeRows,
    categoryColumn,
    valueColumn,
  ])

  useEffect(() => {
    if (!rowScopeOptions.some((o) => o.id === rowScope)) {
      setRowScope('all')
    }
  }, [rowScopeOptions, rowScope])

  const categoryOptions = columnRoles.categoryColumns
  const valueOptions = columnRoles.valueColumns

  const canSave =
    activeColumns.length > 0 &&
    activeRows.length > 0 &&
    isValidAxisPair(categoryColumn, valueColumn, columnRoles)

  const handleSelectChartType = (type: DatamartChartType) => {
    setChartType(type)
    setStep('configure')
    if (!initialDraft) {
      setCategoryColumn('')
      setValueColumn('')
    }
  }

  const handleBack = () => {
    if (step === 'configure' && !initialDraft) setStep('type')
    else onClose()
  }

  const handleSave = () => {
    if (!canSave) return
    const rid = selectedDatasetKey === '__primary__' ? null : selectedDatasetKey
    const chart: DatamartChartConfigV1 = {
      schema_version: 1,
      id: initialDraft?.id ?? uuidv4(),
      chart_type: chartType,
      title: title.trim() || undefined,
      data_source: 'final',
      result_block_id: rid ?? undefined,
      row_scope: rowScope !== 'all' ? rowScope : undefined,
      category_column: categoryColumn,
      value_column: valueColumn,
      show_legend: showLegend,
    }
    onSave(chart)
    onClose()
    setTitle('')
  }

  useEffect(() => {
    if (!open) return undefined
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null
  if (!datasets.length) return null

  const stepIndex = step === 'type' ? 1 : 2
  const selectedTypeMeta = CHART_TYPE_OPTIONS.find((t) => t.id === chartType)
  const SelectedTypeIcon = selectedTypeMeta?.Icon
  const previewTitle =
    title.trim() ||
    (categoryColumn && valueColumn ? `${valueColumn} by ${categoryColumn}` : '')

  return (
    <div
      role="presentation"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1000,
        background: 'rgba(15, 23, 42, 0.45)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 20,
      }}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="generate-chart-modal-title"
        style={{
          width: '100%',
          maxWidth: step === 'type' ? 480 : 520,
          background: dmColors.surface,
          borderRadius: dmRadius.lg,
          boxShadow: '0 25px 50px -12px rgba(0,0,0,0.25)',
          overflow: 'hidden',
        }}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '16px 18px',
            borderBottom: `1px solid ${dmColors.borderLight}`,
          }}
        >
          <div>
            <p style={{ margin: 0, fontSize: 11, fontWeight: 600, color: dmColors.textSubtle, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Step {stepIndex} of 2
            </p>
            <h2 id="generate-chart-modal-title" style={{ margin: '4px 0 0', fontSize: 16, fontWeight: 700, color: dmColors.text }}>
              {step === 'type' ? 'Choose chart type' : 'Map columns to chart'}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            style={{
              border: 'none',
              background: dmColors.surfaceMuted,
              borderRadius: 8,
              padding: 6,
              cursor: 'pointer',
              display: 'flex',
            }}
          >
            <X size={18} color={dmColors.textMuted} />
          </button>
        </div>

        <div style={{ padding: '16px 18px 20px', display: 'flex', flexDirection: 'column', gap: 14 }}>
          {step === 'type' ? (
            <>
              {multiScenario && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <p style={{ margin: 0, fontSize: 12, fontWeight: 600, color: dmColors.text }}>
                    Which scenario is this chart for?
                  </p>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {datasets.map((d) => {
                      const key = datasetKey(d)
                      const selected = selectedDatasetKey === key
                      return (
                        <button
                          key={key}
                          type="button"
                          onClick={() => selectScenario(key)}
                          style={{
                            display: 'block',
                            width: '100%',
                            textAlign: 'left',
                            padding: '10px 12px',
                            borderRadius: dmRadius.md,
                            border: `2px solid ${selected ? dmColors.brand : dmColors.border}`,
                            background: selected ? dmColors.brandMuted : dmColors.surface,
                            cursor: 'pointer',
                            fontSize: 12,
                            fontWeight: selected ? 600 : 500,
                            color: selected ? dmColors.brand : dmColors.text,
                            lineHeight: 1.45,
                          }}
                        >
                          {d.label}
                          <span
                            style={{
                              display: 'block',
                              marginTop: 4,
                              fontSize: 11,
                              fontWeight: 400,
                              color: dmColors.textMuted,
                            }}
                          >
                            {d.columns.length} columns · {d.rows.length.toLocaleString()} rows
                          </span>
                        </button>
                      )
                    })}
                  </div>
                </div>
              )}
              <p style={{ margin: 0, fontSize: 13, color: dmColors.textMuted, lineHeight: 1.55 }}>
                {multiScenario
                  ? 'Then pick how to visualize that scenario. Axis options on the next step use only that scenario’s columns.'
                  : 'Pick how you want to visualize the current result. On the next step, axis options come from your loaded columns only.'}
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                {CHART_TYPE_OPTIONS.map(({ id, label, description, Icon }) => {
                  const selected = chartType === id
                  return (
                    <button
                      key={id}
                      type="button"
                      onClick={() => handleSelectChartType(id)}
                      style={{
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'flex-start',
                        gap: 8,
                        padding: '12px 14px',
                        textAlign: 'left',
                        borderRadius: dmRadius.md,
                        border: `2px solid ${selected ? dmColors.brand : dmColors.border}`,
                        background: selected ? dmColors.brandMuted : dmColors.surface,
                        cursor: 'pointer',
                      }}
                    >
                      <Icon size={22} color={selected ? dmColors.brand : dmColors.textMuted} />
                      <span style={{ fontSize: 14, fontWeight: 700, color: dmColors.text }}>{label}</span>
                      <span style={{ fontSize: 11, color: dmColors.textMuted, lineHeight: 1.4 }}>{description}</span>
                    </button>
                  )
                })}
              </div>
            </>
          ) : (
            <>
              {selectedTypeMeta && (
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    padding: '10px 12px',
                    borderRadius: dmRadius.md,
                    background: dmColors.brandMuted,
                    border: `1px solid ${dmColors.brandBorder}`,
                  }}
                >
                  {SelectedTypeIcon ? <SelectedTypeIcon size={20} color={dmColors.brand} /> : null}
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: dmColors.text }}>{selectedTypeMeta.label} chart</div>
                    <div style={{ fontSize: 11, color: dmColors.textMuted }}>
                      {activeRows.length.toLocaleString()} rows · {activeColumns.length} columns in scope
                    </div>
                  </div>
                </div>
              )}

              {multiScenario && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <span style={labelStyle}>Scenario</span>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {datasets.map((d) => {
                      const key = datasetKey(d)
                      const selected = selectedDatasetKey === key
                      return (
                        <button
                          key={key}
                          type="button"
                          onClick={() => selectScenario(key)}
                          style={{
                            display: 'block',
                            width: '100%',
                            textAlign: 'left',
                            padding: '8px 10px',
                            borderRadius: dmRadius.md,
                            border: `1px solid ${selected ? dmColors.brand : dmColors.border}`,
                            background: selected ? dmColors.brandMuted : dmColors.surface,
                            cursor: 'pointer',
                            fontSize: 12,
                            fontWeight: selected ? 600 : 500,
                            color: selected ? dmColors.brand : dmColors.text,
                          }}
                        >
                          {d.label}
                        </button>
                      )
                    })}
                  </div>
                </div>
              )}

              {rowScopeOptions.length > 1 && (
                <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <span style={labelStyle}>Rows to include</span>
                  <select
                    value={rowScope}
                    onChange={(e) => setRowScope(e.target.value as DatamartChartRowScope)}
                    style={selectStyle}
                  >
                    {rowScopeOptions.map((o) => (
                      <option key={o.id} value={o.id}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                  <span style={{ fontSize: 11, color: dmColors.textSubtle, lineHeight: 1.4 }}>
                    {rowScopeOptions.find((o) => o.id === rowScope)?.description}
                  </span>
                </label>
              )}

              <div
                style={{
                  padding: '12px 14px',
                  borderRadius: dmRadius.md,
                  border: `1px solid ${dmColors.border}`,
                  background: dmColors.surfaceMuted,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 12,
                }}
              >
                <p style={{ margin: 0, fontSize: 12, fontWeight: 600, color: dmColors.text }}>
                  {multiScenario && activeDataset
                    ? `Columns from “${activeDataset.label}”`
                    : 'Columns from this response'}
                </p>

                <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <span style={labelStyle}>{axisLabels.categoryLabel}</span>
                  <span style={{ fontSize: 11, color: dmColors.textSubtle }}>{axisLabels.categoryHint}</span>
                  <select
                    value={categoryColumn}
                    onChange={(e) => setCategoryColumn(e.target.value)}
                    style={selectStyle}
                    disabled={!categoryOptions.length}
                  >
                    {!categoryOptions.length && <option value="">No suitable columns</option>}
                    {categoryOptions.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </label>

                <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <span style={labelStyle}>{axisLabels.valueLabel}</span>
                  <span style={{ fontSize: 11, color: dmColors.textSubtle }}>{axisLabels.valueHint}</span>
                  <select
                    value={valueColumn}
                    onChange={(e) => setValueColumn(e.target.value)}
                    style={selectStyle}
                    disabled={!valueOptions.length}
                  >
                    {!valueOptions.length && <option value="">No numeric columns</option>}
                    {valueOptions.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <span style={labelStyle}>Chart title (optional)</span>
                <input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder={previewTitle || 'e.g. Leave days by branch'}
                  maxLength={200}
                  style={{
                    fontSize: 13,
                    padding: '8px 10px',
                    borderRadius: 8,
                    border: `1px solid ${dmColors.border}`,
                  }}
                />
              </label>

              <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={showLegend}
                  onChange={(e) => setShowLegend(e.target.checked)}
                />
                <span style={{ fontSize: 13, color: dmColors.textMuted }}>Show legend</span>
              </label>

              {!canSave && activeRows.length > 0 && (
                <p style={{ margin: 0, fontSize: 12, color: '#b45309' }}>
                  Choose two different columns — one for labels and one for numeric values.
                </p>
              )}
              {activeRows.length === 0 && (
                <p style={{ margin: 0, fontSize: 12, color: dmColors.danger }}>
                  Run the query first so column names and sample values are available.
                </p>
              )}
            </>
          )}

          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, marginTop: 4, paddingTop: 4 }}>
            <button
              type="button"
              onClick={handleBack}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                fontSize: 13,
                fontWeight: 500,
                padding: '8px 12px',
                borderRadius: 8,
                border: `1px solid ${dmColors.border}`,
                background: dmColors.surface,
                color: dmColors.textMuted,
                cursor: 'pointer',
              }}
            >
              <ChevronLeft size={16} />
              {step === 'configure' && !initialDraft ? 'Back' : 'Cancel'}
            </button>

            {step === 'type' ? (
              <button
                type="button"
                onClick={() => handleSelectChartType(chartType)}
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  padding: '8px 16px',
                  borderRadius: 8,
                  border: 'none',
                  background: dmColors.brand,
                  color: '#fff',
                  cursor: 'pointer',
                }}
              >
                Next
              </button>
            ) : (
              <button
                type="button"
                disabled={!canSave}
                onClick={handleSave}
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  padding: '8px 16px',
                  borderRadius: 8,
                  border: 'none',
                  background: canSave ? dmColors.brand : '#cbd5e1',
                  color: '#fff',
                  cursor: canSave ? 'pointer' : 'default',
                }}
              >
                Add chart
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default GenerateChartModal