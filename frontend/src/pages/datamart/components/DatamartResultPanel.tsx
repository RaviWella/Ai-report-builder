/**
 * DatamartResultPanel
 * ====================
 * Structured “analytics canvas” for SQL + optional post-processing:
 * lists transformation steps, then shows raw SQL output vs final dataset when both exist.
 */
import React, { useMemo } from 'react'
import { Layers, Table2 } from 'lucide-react'
import DatamartTable from '../tables/DatamartTable'
import DatamartGroupedResultMetrics from './DatamartGroupedResultMetrics'
import DatamartPostProcessSummaries from './DatamartPostProcessSummaries'
import { buildGroupedResultMetricsView } from '../lib/groupedResultMetrics'
import { splitAppendSummaryFromFinal } from './datamartResultSplit'
import { describePostProcessSteps } from './postProcessSummary'

export interface DatamartResultPanelProps {
  columns: string[]
  rows: unknown[][]
  rowCount: number
  rawColumns?: string[] | null
  rawRows?: unknown[][] | null
  rawRowCount?: number | null
  postProcessConfig?: Array<Record<string, unknown>> | null
  /** When true, show raw SQL rows vs transformed (debug). Default: final table only. */
  showRawSqlTable?: boolean
}

const DatamartResultPanel: React.FC<DatamartResultPanelProps> = ({
  columns,
  rows,
  rowCount,
  rawColumns,
  rawRows,
  rawRowCount,
  postProcessConfig,
  showRawSqlTable = false,
}) => {
  const hasPp = (postProcessConfig?.length ?? 0) > 0
  const hasRaw =
    !!(rawColumns?.length && rawRows?.length && (rawRowCount ?? rawRows.length) > 0)
  const showDual = showRawSqlTable && hasPp && hasRaw
  const stepLines = describePostProcessSteps(postProcessConfig ?? null)
  const showSteps = hasPp

  const appendSplit = useMemo(
    () => splitAppendSummaryFromFinal(rows, rawRows ?? null, postProcessConfig ?? null),
    [rows, rawRows, postProcessConfig],
  )
  const detailRows = appendSplit ? appendSplit.detailRows : rows
  const detailRowCount = appendSplit ? appendSplit.sqlDetailCount : rowCount
  const summaryRows = appendSplit?.summaryRows ?? []
  const groupedMetrics = useMemo(
    () =>
      appendSplit
        ? null
        : buildGroupedResultMetricsView(columns, rows, postProcessConfig ?? null),
    [appendSplit, columns, rows, postProcessConfig],
  )

  return (
    <div
      style={{
        border: '1px solid #e2e8f0',
        borderRadius: 14,
        overflow: 'hidden',
        marginBottom: 12,
        background: '#fafbfc',
        minWidth: 0,
        maxWidth: '100%',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '11px 16px',
          background: '#ffffff',
          borderBottom: '1px solid #e8ecf1',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Layers size={15} color="#0d9488" />
          <span
            style={{
              fontSize: 11,
              fontWeight: 700,
              color: '#64748b',
              letterSpacing: '0.07em',
              textTransform: 'uppercase',
            }}
          >
            Analytics output
          </span>
        </div>
        {hasPp && (
          <span
            style={{
              fontSize: 11,
              fontWeight: 500,
              color: '#6d28d9',
              padding: '2px 9px',
              borderRadius: 20,
              border: '1px solid #e9d5ff',
              background: '#faf5ff',
            }}
          >
            Includes transformations
          </span>
        )}
      </div>

      {showSteps && (
        <div
          style={{
            padding: '12px 16px 14px',
            borderBottom: '1px solid #eef2f6',
            background: '#f8fafc',
          }}
        >
          <div style={{ fontSize: 12, fontWeight: 600, color: '#334155', marginBottom: 8 }}>
            {showDual ? 'Transformations applied' : 'Transformations on this result'}
          </div>
          <ul
            style={{
              margin: 0,
              paddingLeft: 18,
              fontSize: 13,
              color: '#475569',
              lineHeight: 1.65,
            }}
          >
            {stepLines.length > 0 ? (
              stepLines.map((line, idx) => <li key={idx}>{line}</li>)
            ) : (
              <li style={{ listStyle: 'disc', color: '#64748b' }}>
                Post-processing is configured for this message.
              </li>
            )}
          </ul>
          {!showDual && (
            <p style={{ margin: '10px 0 0', fontSize: 12, color: '#64748b', lineHeight: 1.5 }}>
              {appendSplit
                ? 'SQL detail rows are in the table below; appended averages/totals appear in the summary section.'
                : 'Only the final dataset is shown below.'}
            </p>
          )}
        </div>
      )}

      {showDual ? (
        <div>
          <section style={{ borderBottom: '1px solid #eef2f6' }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 7,
                padding: '10px 14px',
                background: '#ffffff',
                borderBottom: '1px solid #eef2f6',
              }}
            >
              <Table2 size={14} color="#0f766e" />
              <span style={{ fontSize: 12, fontWeight: 600, color: '#0f766e' }}>
                1. SQL query result
              </span>
              <span
                style={{
                  marginLeft: 'auto',
                  fontSize: 11,
                  color: '#64748b',
                  fontWeight: 500,
                }}
              >
                {(rawRowCount ?? rawRows!.length).toLocaleString()}{' '}
                {(rawRowCount ?? rawRows!.length) === 1 ? 'row' : 'rows'}
              </span>
            </div>
            <DatamartTable
              columns={rawColumns!}
              rows={rawRows!}
              rowCount={rawRowCount ?? rawRows!.length}
              embedded
            />
          </section>
          <section>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 7,
                padding: '10px 14px',
                background: '#ffffff',
                borderBottom: '1px solid #eef2f6',
              }}
            >
              <Table2 size={14} color="#5b21b6" />
              <span style={{ fontSize: 12, fontWeight: 600, color: '#5b21b6' }}>
                2. Final dataset (after transformations)
              </span>
              <span
                style={{
                  marginLeft: 'auto',
                  fontSize: 11,
                  color: '#64748b',
                  fontWeight: 500,
                }}
              >
                {appendSplit
                  ? `${detailRowCount.toLocaleString()} detail + ${summaryRows.length.toLocaleString()} summary`
                  : `${rowCount.toLocaleString()} ${rowCount === 1 ? 'row' : 'rows'}`}
              </span>
            </div>
            <DatamartTable
              columns={columns}
              rows={appendSplit ? detailRows : rows}
              rowCount={appendSplit ? detailRowCount : rowCount}
              embedded
            />
            {appendSplit && summaryRows.length > 0 && (
              <DatamartPostProcessSummaries
                columns={columns}
                summaryRows={summaryRows}
                postProcessConfig={postProcessConfig ?? null}
              />
            )}
          </section>
        </div>
      ) : (
        <div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '10px 14px',
              background: '#f8fafc',
              borderBottom: '1px solid #e2e8f0',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
              <Table2 size={14} color="#0d9488" />
              <span style={{ fontSize: 12, fontWeight: 600, color: '#475569' }}>
                {appendSplit ? 'Query results (detail rows)' : hasPp ? 'Final results' : 'Query results'}
              </span>
            </div>
            <span
              style={{
                fontSize: 11,
                color: '#64748b',
                fontWeight: 500,
                padding: '2px 8px',
                background: '#f1f5f9',
                borderRadius: 20,
              }}
            >
              {appendSplit
                ? `${detailRowCount.toLocaleString()} rows`
                : `${rowCount.toLocaleString()} ${rowCount === 1 ? 'row' : 'rows'}`}
            </span>
          </div>
          {groupedMetrics && groupedMetrics.rows.length > 0 && (
            <DatamartGroupedResultMetrics view={groupedMetrics} />
          )}
          <DatamartTable
            columns={columns}
            rows={detailRows}
            rowCount={detailRowCount}
            embedded
          />
          {appendSplit && summaryRows.length > 0 && (
            <DatamartPostProcessSummaries
              columns={columns}
              summaryRows={summaryRows}
              postProcessConfig={postProcessConfig ?? null}
            />
          )}
        </div>
      )}
    </div>
  )
}

export default DatamartResultPanel
