/**
 * Template version list with SQL diff hints vs latest.
 */
import React, { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import type { TemplateVersionResponse } from '../../../services/datamartService'
import { formatSqlDiffSummary, sqlEquals } from '../lib/sqlDiff'
import { dmColors, dmFont, dmRadius, dmSpace } from '../lib/tokens'

export interface TemplateVersionTimelineProps {
  versions: TemplateVersionResponse[]
  activeVersionId: string | null
  onSelectVersion: (versionId: string) => void
}

const TemplateVersionTimeline: React.FC<TemplateVersionTimelineProps> = ({
  versions,
  activeVersionId,
  onSelectVersion,
}) => {
  const [expandedDiffId, setExpandedDiffId] = useState<string | null>(null)
  const latest = versions.find((v) => v.is_latest) ?? versions[0] ?? null
  const latestSql = latest?.sql_script ?? ''

  return (
    <aside
      style={{
        width: 200,
        flexShrink: 0,
        borderRight: `1px solid ${dmColors.border}`,
        overflowY: 'auto',
        padding: dmSpace.sm,
        background: dmColors.surfaceMuted,
      }}
    >
      <p
        style={{
          fontSize: 10,
          fontWeight: 700,
          color: dmColors.textSubtle,
          textTransform: 'uppercase',
          letterSpacing: '0.06em',
          padding: '4px 8px',
          margin: `0 0 ${dmSpace.sm}px`,
        }}
      >
        Versions
      </p>
      {versions.map((v) => {
        const active = activeVersionId === v.id
        const differsFromLatest = latest && !sqlEquals(v.sql_script, latestSql)
        const diffSummary = latest
          ? formatSqlDiffSummary(latestSql, v.sql_script)
          : ''
        const showDiff = expandedDiffId === v.id && differsFromLatest

        return (
          <div key={v.id} style={{ marginBottom: 4 }}>
            <button
              type="button"
              onClick={() => onSelectVersion(v.id)}
              style={{
                width: '100%',
                textAlign: 'left',
                padding: '8px 10px',
                borderRadius: dmRadius.md,
                border: active ? `1px solid ${dmColors.purpleBorder}` : '1px solid transparent',
                background: active ? dmColors.purpleBg : 'transparent',
                cursor: 'pointer',
              }}
            >
              <div
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  color: v.is_latest ? dmColors.purple : dmColors.textMuted,
                }}
              >
                v{v.version_num}
                {v.is_latest ? ' · latest' : ''}
              </div>
              {v.label && (
                <div style={{ fontSize: 11, color: dmColors.textSubtle, marginTop: 2 }}>{v.label}</div>
              )}
              <div style={{ fontSize: 10, color: dmColors.textSubtle, marginTop: 2 }}>
                {new Date(v.created_at).toLocaleDateString()}
              </div>
              {differsFromLatest && (
                <div style={{ fontSize: 10, color: '#b45309', marginTop: 4 }}>{diffSummary}</div>
              )}
            </button>

            {differsFromLatest && (
              <div style={{ padding: '0 6px 4px' }}>
                <button
                  type="button"
                  onClick={() => setExpandedDiffId(showDiff ? null : v.id)}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 4,
                    fontSize: 10,
                    fontWeight: 600,
                    color: dmColors.textMuted,
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    padding: '2px 4px',
                  }}
                >
                  {showDiff ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
                  SQL diff
                </button>
              </div>
            )}

            {showDiff && (
              <div
                style={{
                  margin: '0 4px 8px',
                  padding: 8,
                  borderRadius: dmRadius.sm,
                  background: dmColors.surface,
                  border: `1px solid ${dmColors.border}`,
                  fontSize: 10,
                  color: dmColors.textMuted,
                }}
              >
                <p style={{ margin: `0 0 ${dmSpace.xs}px`, fontWeight: 600 }}>{diffSummary}</p>
                <pre
                  style={{
                    margin: 0,
                    fontSize: 10,
                    fontFamily: dmFont.mono,
                    maxHeight: 120,
                    overflow: 'auto',
                    whiteSpace: 'pre',
                    color: dmColors.sqlText,
                    background: dmColors.sqlBg,
                    padding: 6,
                    borderRadius: 4,
                  }}
                >
                  {v.sql_script}
                </pre>
              </div>
            )}
          </div>
        )
      })}
    </aside>
  )
}

export default TemplateVersionTimeline
