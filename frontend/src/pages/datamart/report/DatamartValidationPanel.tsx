/**
 * Sources & validation details for one assistant turn.
 */
import React, { useState } from 'react'
import { ChevronDown, ChevronRight, Database, AlertTriangle } from 'lucide-react'
import DatamartValidationBadge from './DatamartValidationBadge'
import {
  RETRIEVAL_STATUS_LABEL,
  type DatamartValidation,
} from '../lib/validation'
import type { PipelineTurnMeta } from '../../../services/datamartService'
import { formatPipelineMetaLine } from '../lib/pipelineMeta'
import { dmColors, dmRadius, dmSpace } from '../lib/tokens'
import { dmCopy } from '../lib/copy'

export interface DatamartValidationPanelProps {
  validation: DatamartValidation
  pipelineMeta?: PipelineTurnMeta | null
}

const DatamartValidationPanel: React.FC<DatamartValidationPanelProps> = ({
  validation,
  pipelineMeta,
}) => {
  const [open, setOpen] = useState(
    validation.overall === 'needs_review' || validation.overall === 'blocked',
  )
  const { retrieval: r, generation: g } = validation
  const genWarnings = g?.warnings ?? []
  const retrievalWarnings = r.warnings ?? []

  return (
    <div
      data-testid="datamart-validation-panel"
      style={{
        margin: `${dmSpace.md} ${dmSpace.lg}`,
        marginBottom: dmSpace.sm,
        border: `1px solid ${dmColors.border}`,
        borderRadius: dmRadius.md,
        background: dmColors.surfaceMuted,
        overflow: 'hidden',
      }}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '10px 14px',
          border: 'none',
          background: dmColors.surface,
          cursor: 'pointer',
          textAlign: 'left',
        }}
      >
        {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        <DatamartValidationBadge overall={validation.overall} compact />
        <span style={{ fontSize: 13, fontWeight: 600, color: dmColors.text }}>
          {dmCopy.validation.panelTitle}
        </span>
        <span style={{ fontSize: 12, color: dmColors.textMuted, marginLeft: 'auto' }}>
          {RETRIEVAL_STATUS_LABEL[r.status]}
        </span>
      </button>

      {open && (
        <div style={{ padding: '12px 14px 14px', fontSize: 13, lineHeight: 1.55 }}>
          {r.message && (
            <p style={{ margin: '0 0 10px', color: dmColors.text }}>{r.message}</p>
          )}

          <section style={{ marginBottom: 12 }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                fontWeight: 600,
                marginBottom: 6,
                color: dmColors.text,
              }}
            >
              <Database size={14} />
              {dmCopy.validation.sourcesTitle}
            </div>
            {r.source && (
              <div style={{ color: dmColors.textMuted, marginBottom: 4 }}>
                {dmCopy.validation.groundingSource}: <code>{r.source}</code>
              </div>
            )}
            {r.tables_selected.length > 0 && (
              <div style={{ marginBottom: 6 }}>
                <span style={{ color: dmColors.textMuted }}>
                  {dmCopy.validation.tablesLabel}:{' '}
                </span>
                {r.tables_selected.join(', ')}
              </div>
            )}
            {r.columns_in_context && Object.keys(r.columns_in_context).length > 0 && (
              <div style={{ marginBottom: 10 }}>
                <div style={{ color: dmColors.textMuted, marginBottom: 4 }}>
                  {dmCopy.validation.columnsLabel}
                </div>
                <ul
                  style={{
                    margin: 0,
                    paddingLeft: 18,
                    color: dmColors.text,
                    fontSize: 12,
                  }}
                >
                  {Object.entries(r.columns_in_context).map(([table, cols]) => (
                    <li key={table} style={{ marginBottom: 6 }}>
                      <strong>{table}</strong>
                      <div
                        style={{
                          marginTop: 2,
                          color: dmColors.textMuted,
                          wordBreak: 'break-word',
                        }}
                      >
                        {cols.join(', ')}
                      </div>
                    </li>
                  ))}
                </ul>
                <p
                  style={{
                    margin: '6px 0 0',
                    fontSize: 11,
                    color: dmColors.textSubtle,
                  }}
                >
                  {dmCopy.validation.columnsJoinHint}
                </p>
              </div>
            )}
            {(r.topics_matched?.length ?? 0) > 0 && (
              <div style={{ marginBottom: 4 }}>
                <span style={{ color: dmColors.textMuted }}>
                  {dmCopy.validation.topicsLabel}:{' '}
                </span>
                {r.topics_matched!.join(', ')}
              </div>
            )}
            {(r.metrics_matched?.length ?? 0) > 0 && (
              <div style={{ marginBottom: 4 }}>
                <span style={{ color: dmColors.textMuted }}>
                  {dmCopy.validation.metricsLabel}:{' '}
                </span>
                {r.metrics_matched!.join(', ')}
              </div>
            )}
            {(r.schema_links?.length ?? 0) > 0 && (
              <ul
                style={{
                  margin: '6px 0 0',
                  paddingLeft: 18,
                  color: dmColors.text,
                }}
              >
                {r.schema_links!.map((link) => (
                  <li key={`${link.term}-${link.qualified_column}`}>
                    <strong>{link.term}</strong>
                    {link.qualified_column ? (
                      <>
                        {' '}
                        → <code>{link.qualified_column}</code>
                      </>
                    ) : null}
                    <span style={{ color: dmColors.textMuted, fontSize: 11 }}>
                      {' '}
                      ({link.confidence})
                    </span>
                  </li>
                ))}
              </ul>
            )}
            {(r.missing_tables?.length ?? 0) > 0 && (
              <div
                style={{
                  marginTop: 8,
                  padding: '8px 10px',
                  background: dmColors.dangerBg,
                  borderRadius: dmRadius.sm,
                  color: dmColors.danger,
                  fontSize: 12,
                }}
              >
                {dmCopy.validation.missingTables}: {r.missing_tables!.join(', ')}
              </div>
            )}
          </section>

          {(retrievalWarnings.length > 0 || genWarnings.length > 0) && (
            <section>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  fontWeight: 600,
                  marginBottom: 6,
                  color: dmColors.text,
                }}
              >
                <AlertTriangle size={14} color="#b45309" />
                {dmCopy.validation.warningsTitle}
              </div>
              <ul style={{ margin: 0, paddingLeft: 18, color: dmColors.text }}>
                {[...retrievalWarnings, ...genWarnings].map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            </section>
          )}

          {g && (
            <div
              style={{
                marginTop: 10,
                fontSize: 12,
                color: dmColors.textMuted,
              }}
            >
              {dmCopy.validation.bindingLabel}: {g.binding}
              {g.truncated ? ` · ${dmCopy.validation.truncatedHint}` : ''}
              {g.grounding_expanded ? ` · ${dmCopy.validation.expandedHint}` : ''}
            </div>
          )}

          {pipelineMeta &&
            (pipelineMeta.domain ||
              pipelineMeta.sql_tier ||
              pipelineMeta.sql_source) && (
              <section
                data-testid="datamart-pipeline-meta"
                style={{
                  marginTop: 12,
                  padding: '10px 12px',
                  background: dmColors.surface,
                  borderRadius: dmRadius.sm,
                  border: `1px solid ${dmColors.border}`,
                }}
              >
                <div
                  style={{
                    fontWeight: 600,
                    marginBottom: 6,
                    color: dmColors.text,
                  }}
                >
                  {dmCopy.validation.pipelineTitle}
                </div>
                <div style={{ fontSize: 12, color: dmColors.textMuted }}>
                  {formatPipelineMetaLine(pipelineMeta)}
                </div>
                {(pipelineMeta.tables_linked?.length ?? 0) > 0 && (
                  <div
                    style={{
                      marginTop: 6,
                      fontSize: 12,
                      color: dmColors.textMuted,
                      wordBreak: 'break-word',
                    }}
                  >
                    {dmCopy.validation.pipelineLinkedTables}:{' '}
                    {pipelineMeta.tables_linked!.join(', ')}
                  </div>
                )}
              </section>
            )}

          <p
            style={{
              margin: '12px 0 0',
              fontSize: 11,
              color: dmColors.textSubtle,
            }}
          >
            {dmCopy.validation.disclaimer}
          </p>
        </div>
      )}
    </div>
  )
}

export default DatamartValidationPanel
