/**
 * Charts section: saved charts, one-click suggestions, and add-chart entry.
 */
import React from 'react'
import { BarChart3, Loader2, Plus } from 'lucide-react'
import DatamartCharts from '../../charts/DatamartCharts'
import DatamartChartSuggestions from '../../charts/DatamartChartSuggestions'
import type { ChartSuggestion } from '../../charts/chartSuggestions'
import type { DatamartChartConfigV1, DatamartChartType } from '../../charts/chartConfig'
import { dmColors, dmRadius, dmSpace } from '../../lib/tokens'

export interface DatamartChartsSectionProps {
  chartCount: number
  showTable: boolean
  canGenerateChart: boolean
  canPersistCharts: boolean
  chartSaving: boolean
  chartSuggestions: ChartSuggestion[]
  chartsEffective: unknown[]
  tableColumns: string[]
  tableRows: unknown[][]
  rawColumns?: string[] | null
  rawRows?: unknown[][] | null
  blockDatasets: Record<
    string,
    {
      finalColumns: string[]
      finalRows: unknown[][]
      rawColumns?: string[] | null
      rawRows?: unknown[][] | null
    }
  >
  onOpenChartModal: () => void
  onApplySuggestion: (s: ChartSuggestion) => void
  onCustomizeSuggestion: (s: ChartSuggestion) => void
  onRemoveChart?: (chartId: string) => void
  onChangeChartType?: (chartId: string, newType: DatamartChartType) => void
  onUpdateChart?: (chartId: string, updated: DatamartChartConfigV1) => void
  /** When set, labels suggestions as belonging to this scenario only. */
  scenarioLabel?: string
}

const DatamartChartsSection: React.FC<DatamartChartsSectionProps> = ({
  chartCount,
  showTable,
  canGenerateChart,
  canPersistCharts,
  chartSaving,
  chartSuggestions,
  chartsEffective,
  tableColumns,
  tableRows,
  rawColumns,
  rawRows,
  blockDatasets,
  onOpenChartModal,
  onApplySuggestion,
  onCustomizeSuggestion,
  onRemoveChart,
  onChangeChartType,
  onUpdateChart,
  scenarioLabel,
}) => {
  const hasCharts = chartCount > 0
  const hasSuggestions = chartSuggestions.length > 0

  if (!showTable && !hasCharts) {
    return (
      <p style={{ margin: 0, fontSize: 13, color: dmColors.textMuted, lineHeight: 1.55 }}>
        Run the query in <strong>Results</strong> to unlock chart suggestions and visualizations.
      </p>
    )
  }

  return (
    <div className="dm-charts-section" style={{ position: 'relative', zIndex: 1, minWidth: 0 }}>
      {canGenerateChart && showTable && (
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            gap: 8,
            marginBottom: hasCharts || hasSuggestions ? dmSpace.md : 0,
          }}
        >
          <button
            type="button"
            onClick={onOpenChartModal}
            disabled={chartSaving || !canPersistCharts}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              fontSize: 12,
              fontWeight: 600,
              color: dmColors.purple,
              background: dmColors.purpleBg,
              border: `1px solid ${dmColors.purpleBorder}`,
              borderRadius: dmRadius.sm,
              padding: '7px 12px',
              cursor: chartSaving || !canPersistCharts ? 'default' : 'pointer',
              opacity: chartSaving || !canPersistCharts ? 0.55 : 1,
            }}
          >
            {chartSaving ? (
              <Loader2 size={13} style={{ animation: 'spin 1s linear infinite' }} />
            ) : (
              <Plus size={13} />
            )}
            Custom chart
          </button>
          <span style={{ fontSize: 12, color: dmColors.textSubtle, lineHeight: 1.45 }}>
            Suggestions add in one click; use custom chart for full control.
          </span>
        </div>
      )}

      {hasSuggestions && showTable && (
        <DatamartChartSuggestions
          suggestions={chartSuggestions}
          scenarioLabel={scenarioLabel}
          disabled={chartSaving || !canPersistCharts}
          onApply={onApplySuggestion}
          onCustomize={onCustomizeSuggestion}
        />
      )}

      {hasCharts ? (
        <div
          style={{
            marginTop: hasSuggestions ? dmSpace.lg : dmSpace.sm,
            paddingTop: hasSuggestions ? 4 : 0,
          }}
        >
          <DatamartCharts
            chartConfigs={chartsEffective}
            primaryDataset={{
              finalColumns: tableColumns,
              finalRows: tableRows,
              rawColumns,
              rawRows,
            }}
            blockDatasets={blockDatasets}
            onRemoveChart={canPersistCharts ? onRemoveChart : undefined}
            onChangeChartType={canPersistCharts ? onChangeChartType : undefined}
            onUpdateChart={canPersistCharts ? onUpdateChart : undefined}
            chartSaving={chartSaving}
          />
        </div>
      ) : (
        showTable &&
        canGenerateChart &&
        !hasSuggestions && (
          <div
            style={{
              marginTop: dmSpace.md,
              padding: dmSpace.lg,
              textAlign: 'center',
              borderRadius: dmRadius.md,
              border: `1px dashed ${dmColors.border}`,
              background: dmColors.surfaceMuted,
            }}
          >
            <BarChart3 size={22} color={dmColors.textSubtle} style={{ marginBottom: 8 }} />
            <p style={{ margin: 0, fontSize: 13, color: dmColors.textMuted }}>
              No chart suggestions for this shape of data. Use <strong>Custom chart</strong> to
              pick columns manually.
            </p>
          </div>
        )
      )}
    </div>
  )
}

export default DatamartChartsSection
