/**
 * Stacked view: show every scenario table in one report (no tab switching required).
 */
import React from 'react'
import { Loader2 } from 'lucide-react'
import type { DatamartResultBlock } from '../../../services/datamartService'
import DatamartExtraBlockCard from '../components/DatamartExtraBlockCard'
import DatamartResultPanel from '../components/DatamartResultPanel'
import type { ScenarioDescriptor } from '../lib/reportLayout'
import { dmColors, dmSpace } from '../lib/tokens'

export interface DatamartStackedScenariosProps {
  scenarios: ScenarioDescriptor[]
  tableColumns: string[]
  tableRows: unknown[][]
  tableRowCount: number
  rawColumns?: string[] | null
  rawRows?: unknown[][] | null
  rawRowCount?: number | null
  postProcessConfig: Array<Record<string, unknown>> | null | undefined
  extraBlocks: DatamartResultBlock[] | null | undefined
  blockDatasets: Record<
    string,
    {
      finalColumns: string[]
      finalRows: unknown[][]
      rawColumns?: string[] | null
      rawRows?: unknown[][] | null
    }
  >
  messageId?: string
  sessionId?: string
  templateId?: string
  versionId?: string
  running: boolean
  onBlockData: (blockId: string, payload: import('../../../services/datamartService').SqlExecuteResponse) => void
}

const DatamartStackedScenarios: React.FC<DatamartStackedScenariosProps> = ({
  scenarios,
  tableColumns,
  tableRows,
  tableRowCount,
  rawColumns,
  rawRows,
  rawRowCount,
  postProcessConfig,
  extraBlocks,
  blockDatasets,
  messageId,
  sessionId,
  templateId,
  versionId,
  running,
  onBlockData,
}) => {
  const canExecuteBlock =
    (!!templateId && !!versionId) || (!!messageId && !!sessionId)

  return (
  <div style={{ display: 'flex', flexDirection: 'column', gap: dmSpace.lg }}>
    {scenarios.map((scenario) => {
      const isPrimary = scenario.panelId === 'primary'
      const block = extraBlocks?.find((b) => b.block_id === scenario.panelId)
      const ds = isPrimary ? null : blockDatasets[scenario.panelId]
      const cols = isPrimary ? tableColumns : (ds?.finalColumns ?? [])
      const rows = isPrimary ? tableRows : (ds?.finalRows ?? [])
      const hasTable = cols.length > 0 && rows.length > 0

      return (
        <section
          key={scenario.panelId}
          aria-label={scenario.label}
          style={{
            borderTop: `1px solid ${dmColors.border}`,
            paddingTop: dmSpace.md,
          }}
        >
          <h3
            style={{
              margin: `0 0 ${dmSpace.sm}px`,
              fontSize: 13,
              fontWeight: 600,
              color: dmColors.text,
              letterSpacing: '-0.01em',
            }}
          >
            {scenario.label}
          </h3>

          {isPrimary && running && !hasTable && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: dmColors.textMuted }}>
              <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} />
              Loading results…
            </div>
          )}

          {hasTable && (
            <DatamartResultPanel
              columns={cols}
              rows={rows}
              rowCount={isPrimary ? tableRowCount : rows.length}
              rawColumns={isPrimary ? rawColumns : ds?.rawColumns}
              rawRows={isPrimary ? rawRows : ds?.rawRows}
              rawRowCount={isPrimary ? rawRowCount : null}
              postProcessConfig={isPrimary ? postProcessConfig : (block?.post_process_config ?? null)}
            />
          )}

          {!isPrimary && !hasTable && canExecuteBlock && block && (
            <DatamartExtraBlockCard
              block={block}
              sessionId={sessionId}
              messageId={messageId}
              templateId={templateId}
              versionId={versionId}
              onBlockData={onBlockData}
            />
          )}

          {!isPrimary && !hasTable && !block && (
            <p style={{ fontSize: 13, color: dmColors.textMuted, margin: 0 }}>
              No data for this scenario yet.
            </p>
          )}
        </section>
      )
    })}
  </div>
  )
}

export default DatamartStackedScenarios
