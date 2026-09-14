/**
 * One additional SQL result block (extra_result_blocks) with manual Run query.
 */
import React, { useEffect, useState } from 'react'
import { ChevronDown, ChevronRight, Play, Loader2, AlertCircle } from 'lucide-react'
import type { DatamartResultBlock, SqlExecuteResponse } from '../../../services/datamartService'
import { datamartService } from '../../../services/datamartService'
import DatamartResultPanel from './DatamartResultPanel'
import DatamartExtraBlockValidation from '../report/DatamartExtraBlockValidation'

export interface DatamartExtraBlockCardProps {
  block: DatamartResultBlock
  sessionId?: string
  messageId?: string
  templateId?: string
  versionId?: string
  /** When block data is loaded via Run query, parent can merge for charts. */
  onBlockData?: (blockId: string, payload: SqlExecuteResponse) => void
}

const DatamartExtraBlockCard: React.FC<DatamartExtraBlockCardProps> = ({
  block,
  sessionId,
  messageId,
  templateId,
  versionId,
  onBlockData,
}) => {
  const canExecute =
    (!!templateId && !!versionId) || (!!sessionId && !!messageId)
  const [sqlExpanded, setSqlExpanded] = useState(false)
  const [runResult, setRunResult] = useState<SqlExecuteResponse | null>(null)
  const [running, setRunning] = useState(false)
  const [runError, setRunError] = useState<string | null>(null)

  const hasLive = block.columns.length > 0 && block.rows.length > 0
  const effective = hasLive
    ? {
        columns: block.columns,
        rows: block.rows,
        row_count: block.row_count,
        raw_columns: block.raw_columns,
        raw_rows: block.raw_rows,
        raw_row_count: block.raw_row_count,
        post_process_config: block.post_process_config,
      }
    : runResult
  const tableColumns = effective?.columns ?? []
  const tableRows = effective?.rows ?? []
  const tableRowCount = effective?.row_count ?? 0
  const rawColumns = effective?.raw_columns ?? null
  const rawRows = effective?.raw_rows ?? null
  const rawRowCount = effective?.raw_row_count ?? null
  const postProcessConfig = effective?.post_process_config ?? block.post_process_config
  const showTable = tableColumns.length > 0
  const title = block.title?.trim() || `Additional result (${block.block_id.slice(0, 8)}…)`

  useEffect(() => {
    setRunResult(null)
    setRunError(null)
  }, [messageId, versionId, block.block_id])

  useEffect(() => {
    if (runResult && !runResult.error && runResult.columns.length > 0) {
      onBlockData?.(block.block_id, runResult)
    }
  }, [runResult, block.block_id, onBlockData])

  const handleRun = async () => {
    if (!canExecute) return
    setRunning(true)
    setRunError(null)
    setRunResult(null)
    try {
      const result =
        templateId && versionId
          ? await datamartService.executeTemplateVersionBlock(
              templateId,
              versionId,
              block.block_id,
            )
          : await datamartService.executeMessageBlock(
              sessionId!,
              messageId!,
              block.block_id,
            )
      if (result.error) setRunError(result.error)
      else {
        setRunResult(result)
        onBlockData?.(block.block_id, result)
      }
    } catch (err: unknown) {
      setRunError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Failed to execute query.',
      )
    } finally {
      setRunning(false)
    }
  }

  return (
    <div
      style={{
        marginTop: 20,
        paddingTop: 16,
        borderTop: '1px solid #e2e8f0',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <span
          style={{
            fontSize: 11,
            fontWeight: 700,
            color: '#64748b',
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
          }}
        >
          Additional dataset
        </span>
        <span style={{ fontSize: 13, fontWeight: 600, color: '#334155' }}>{title}</span>
      </div>

      {block.validation && typeof block.validation === 'object' && (
        <DatamartExtraBlockValidation validation={block.validation} />
      )}

      {block.error && !showTable && (
        <div
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: 8,
            padding: '10px 12px',
            background: '#fef2f2',
            border: '1px solid #fecaca',
            borderRadius: 8,
            marginBottom: 10,
          }}
        >
          <AlertCircle size={14} color="#dc2626" style={{ flexShrink: 0, marginTop: 2 }} />
          <span style={{ fontSize: 12, color: '#b91c1c', lineHeight: 1.5 }}>{block.error}</span>
        </div>
      )}

      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 8 }}>
        {!hasLive && block.sql && canExecute && (
          <button
            type="button"
            onClick={handleRun}
            disabled={running}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 5,
              fontSize: 12,
              fontWeight: 500,
              color: running ? '#94a3b8' : '#0d9488',
              background: running ? '#f8fafc' : '#f0fdfa',
              border: `1px solid ${running ? '#e2e8f0' : '#99f6e4'}`,
              borderRadius: 6,
              padding: '5px 12px',
              cursor: running ? 'default' : 'pointer',
            }}
          >
            {running ? <Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} /> : <Play size={12} />}
            {running ? 'Running…' : 'Run Query'}
          </button>
        )}
        {block.sql && (
          <button
            type="button"
            onClick={() => setSqlExpanded((v) => !v)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              fontSize: 12,
              fontWeight: 500,
              color: '#64748b',
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              padding: '5px 0',
            }}
          >
            {sqlExpanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
            {sqlExpanded ? 'Hide SQL' : 'View SQL'}
          </button>
        )}
      </div>

      {runError && (
        <div
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: 8,
            padding: '8px 12px',
            background: '#fef2f2',
            border: '1px solid #fecaca',
            borderRadius: 8,
            marginBottom: 8,
          }}
        >
          <AlertCircle size={14} color="#dc2626" style={{ flexShrink: 0, marginTop: 2 }} />
          <span style={{ fontSize: 12, color: '#dc2626' }}>{runError}</span>
        </div>
      )}

      {showTable && (
        <DatamartResultPanel
          columns={tableColumns}
          rows={tableRows}
          rowCount={tableRowCount}
          rawColumns={rawColumns}
          rawRows={rawRows}
          rawRowCount={rawRowCount}
          postProcessConfig={postProcessConfig}
        />
      )}

      {sqlExpanded && block.sql && (
        <div
          style={{
            marginTop: 8,
            background: '#0f172a',
            borderRadius: 10,
            padding: '12px 14px',
            overflowX: 'auto',
          }}
        >
          <pre
            style={{
              margin: 0,
              fontSize: 11,
              color: '#e2e8f0',
              fontFamily: 'ui-monospace, Menlo, Monaco, "Cascadia Code", monospace',
              lineHeight: 1.55,
              whiteSpace: 'pre',
            }}
          >
            {block.sql}
          </pre>
        </div>
      )}
    </div>
  )
}

export default DatamartExtraBlockCard
