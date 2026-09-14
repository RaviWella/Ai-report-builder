/**
 * Primary actions for a datamart report card header.
 */
import React from 'react'
import { Play, Loader2, BarChart3, BookmarkPlus, Check, Undo2, RotateCcw } from 'lucide-react'
import DatamartExportMenu from './DatamartExportMenu'
import { dmColors, dmRadius } from '../lib/tokens'
import { dmCopy } from '../lib/copy'
import { STATUS_BADGE_LABEL, type ReportStatusBadge } from './reportState'

export interface DatamartReportToolbarProps {
  statusBadge: ReportStatusBadge
  canRunQuery: boolean
  running: boolean
  hasUserRun: boolean
  canExport: boolean
  canGenerateChart: boolean
  chartSaving: boolean
  exporting?: boolean
  showPromote: boolean
  promoteSuccess: boolean
  onRunQuery: () => void
  onCustomizeExport?: () => void
  onExportCsv: () => void
  onExportPdf: () => void
  onGenerateChart: () => void
  onPromote: () => void
  canUndoModification?: boolean
  undoingModification?: boolean
  onUndoModification?: () => void
  /** Re-ask the AI with the same user question (errors or latest turn). */
  onRetryTurn?: () => void
  retryTurnLabel?: string
  retryTurnDisabled?: boolean
}

const btnBase: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 5,
  fontSize: 12,
  fontWeight: 500,
  borderRadius: dmRadius.sm,
  padding: '5px 12px',
  cursor: 'pointer',
  transition: 'background 0.15s, border-color 0.15s',
}

const DatamartReportToolbar: React.FC<DatamartReportToolbarProps> = ({
  statusBadge,
  canRunQuery,
  running,
  hasUserRun,
  canExport,
  canGenerateChart,
  chartSaving,
  exporting = false,
  showPromote,
  promoteSuccess,
  onRunQuery,
  onCustomizeExport,
  onExportCsv,
  onExportPdf,
  onGenerateChart,
  onPromote,
  canUndoModification,
  undoingModification,
  onUndoModification,
  onRetryTurn,
  retryTurnLabel,
  retryTurnDisabled = false,
}) => {
  const statusColors: Record<ReportStatusBadge, { bg: string; border: string; color: string }> = {
    ready: { bg: '#ecfdf5', border: '#99f6e4', color: '#0f766e' },
    not_loaded: { bg: '#fffbeb', border: '#fde68a', color: '#b45309' },
    running: { bg: '#f0fdfa', border: '#99f6e4', color: '#0d9488' },
    error: { bg: dmColors.dangerBg, border: dmColors.dangerBorder, color: dmColors.danger },
    text_only: { bg: dmColors.surfaceMuted, border: dmColors.border, color: dmColors.textMuted },
    no_sql: { bg: dmColors.surfaceMuted, border: dmColors.border, color: dmColors.textMuted },
    pipeline_error: { bg: dmColors.dangerBg, border: dmColors.dangerBorder, color: dmColors.danger },
  }
  const sc = statusColors[statusBadge]

  return (
    <div
      role="toolbar"
      aria-label={dmCopy.report.toolbarAriaLabel}
      data-testid="datamart-report-toolbar"
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        gap: 8,
        padding: '12px 16px',
        borderBottom: `1px solid ${dmColors.borderLight}`,
        background: dmColors.surface,
      }}
    >
      <span
        style={{
          fontSize: 11,
          fontWeight: 600,
          padding: '3px 10px',
          borderRadius: dmRadius.pill,
          background: sc.bg,
          border: `1px solid ${sc.border}`,
          color: sc.color,
        }}
      >
        {STATUS_BADGE_LABEL[statusBadge]}
      </span>

      <span style={{ flex: 1, minWidth: 8 }} />

      {onRetryTurn && (
        <button
          type="button"
          data-testid="datamart-retry-turn"
          onClick={onRetryTurn}
          disabled={retryTurnDisabled}
          title="Send the same question again to the assistant"
          style={{
            ...btnBase,
            color: retryTurnDisabled ? dmColors.textSubtle : '#b45309',
            background: retryTurnDisabled ? dmColors.surfaceMuted : '#fffbeb',
            border: `1px solid ${retryTurnDisabled ? dmColors.border : '#fde68a'}`,
            cursor: retryTurnDisabled ? 'default' : 'pointer',
          }}
        >
          <RotateCcw size={12} />
          {retryTurnLabel ?? dmCopy.toolbar.tryAgain}
        </button>
      )}

      {canUndoModification && onUndoModification && (
        <button
          type="button"
          data-testid="datamart-undo-modification"
          onClick={onUndoModification}
          disabled={undoingModification}
          title="Remove the last modification and restore the previous result"
          style={{
            ...btnBase,
            color: undoingModification ? dmColors.textSubtle : '#b45309',
            background: undoingModification ? dmColors.surfaceMuted : '#fffbeb',
            border: `1px solid ${undoingModification ? dmColors.border : '#fde68a'}`,
            cursor: undoingModification ? 'default' : 'pointer',
          }}
        >
          {undoingModification ? (
            <Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} />
          ) : (
            <Undo2 size={12} />
          )}
          {undoingModification ? dmCopy.toolbar.undoing : dmCopy.toolbar.undoModification}
        </button>
      )}

      {canRunQuery && (
        <button
          type="button"
          data-testid="datamart-run-query"
          onClick={onRunQuery}
          disabled={running}
          aria-busy={running}
          style={{
            ...btnBase,
            color: running ? dmColors.textSubtle : dmColors.brand,
            background: running ? dmColors.surfaceMuted : dmColors.brandMuted,
            border: `1px solid ${running ? dmColors.border : dmColors.brandBorder}`,
            cursor: running ? 'default' : 'pointer',
          }}
        >
          {running ? (
            <Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} />
          ) : (
            <Play size={12} />
          )}
          {running
            ? dmCopy.toolbar.running
            : hasUserRun
              ? dmCopy.toolbar.rerun
              : dmCopy.toolbar.runQuery}
        </button>
      )}

      {canExport && (
        <DatamartExportMenu
          disabled={exporting}
          onCustomizeExport={onCustomizeExport}
          onExportCsv={onExportCsv}
          onExportPdf={onExportPdf}
        />
      )}

      {canGenerateChart && (
        <button
          type="button"
          disabled={chartSaving}
          onClick={onGenerateChart}
          style={{
            ...btnBase,
            color: chartSaving ? dmColors.textSubtle : '#0f766e',
            background: chartSaving ? dmColors.surfaceMuted : '#ecfdf5',
            border: `1px solid ${dmColors.brandBorder}`,
            cursor: chartSaving ? 'default' : 'pointer',
          }}
        >
          <BarChart3 size={12} />
          {chartSaving ? dmCopy.toolbar.savingChart : dmCopy.toolbar.addChart}
        </button>
      )}

      {showPromote && !promoteSuccess && (
        <button
          type="button"
          onClick={onPromote}
          style={{
            ...btnBase,
            color: dmColors.purple,
            background: dmColors.purpleBg,
            border: `1px solid ${dmColors.purpleBorder}`,
          }}
        >
          <BookmarkPlus size={12} />
          {dmCopy.toolbar.saveAsTemplate}
        </button>
      )}

      {promoteSuccess && (
        <span style={{ ...btnBase, color: dmColors.brand, cursor: 'default', border: 'none' }}>
          <Check size={12} />
          {dmCopy.toolbar.savedToTemplates}
        </span>
      )}
    </div>
  )
}

export default DatamartReportToolbar
