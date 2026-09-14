/**
 * Structured report artifact for one datamart assistant turn.
 * Expandable sections: Summary, Query, Transformations, Results, Charts.
 */
import React, { useCallback, useMemo, useState } from 'react'
import { AlertCircle, BookmarkPlus, Check, Loader2, RotateCcw } from 'lucide-react'
import type { DatamartReportModel } from '../hooks/useDatamartReportModel'
import { useReportLayout } from '../hooks/useReportLayout'
import DatamartResultPanel from '../components/DatamartResultPanel'
import GenerateChartModal from '../charts/GenerateChartModal'
import DatamartExtraBlockCard from '../components/DatamartExtraBlockCard'
import DatamartScenarioBar from './DatamartScenarioBar'
import DatamartReportCanvas from './DatamartReportCanvas'
import { chartsForPanel, type ReportLayoutWidget, type ReportPanelId } from '../lib/reportLayout'
import { describePostProcessSteps } from '../components/postProcessSummary'
import DatamartTransformationsSection from './sections/DatamartTransformationsSection'
import DatamartChartsSection from './sections/DatamartChartsSection'
import { useReportSectionPersist } from '../hooks/useReportSectionPersist'
import { dmCopy } from '../lib/copy'
import { formatApiError } from '../lib/formatApiError'
import {
  buildExportReportInput,
  type ExportScenarioSlice,
} from '../lib/exportReportContext'
import type { ExportReportInput } from '../lib/exportReportModel'
import { exportReportToCsv } from '../lib/exportReportCsv'
import { exportReportToPdf } from '../lib/exportReportPdf'
import ExportComposerModal from './ExportComposerModal'
import { dmColors, dmRadius, dmSpace } from '../lib/tokens'
import { useToast } from '../../../components/ui/Toast'
import DatamartReportSection from './DatamartReportSection'
import DatamartReportToolbar from './DatamartReportToolbar'
import DatamartSqlSection from './sections/DatamartSqlSection'
import DatamartStackedScenarios from './DatamartStackedScenarios'
import DatamartValidationPanel from './DatamartValidationPanel'
import { pipelineMetaFromResponse } from '../lib/pipelineMeta'
import DatamartPipelineSteps from './DatamartPipelineSteps'
import {
  primaryScenarioUnchangedNote,
  resolvePanelNarrative,
  resolvePanelPipelineTrace,
  resolvePanelValidation,
} from '../lib/scenarioPanelContext'

export interface DatamartReportCardProps {
  model: DatamartReportModel
}

const DatamartReportCard: React.FC<DatamartReportCardProps> = ({ model }) => {
  const toast = useToast()
  const {
    data,
    messageId,
    sessionId,
    templateId,
    versionId,
    sectionPersistScope,
    hasPipelineError,
    canRunQuery,
    reportRun,
    statusBadge,
    tableColumns,
    tableRows,
    tableRowCount,
    rawColumns,
    rawRows,
    rawRowCount,
    postProcessConfig,
    showTable,
    chartsEffective,
    blockDatasets,
    chartModalDatasets,
    canGenerateChart,
    chartSuggestionsByPanel,
    chartModalOpen,
    chartModalDraft,
    chartModalInitialDatasetKey,
    chartSaving,
    promoting,
    promoteName,
    setPromoteName,
    promoteLoading,
    promoteSuccess,
    promoteError,
    setPromoting,
    setPromoteError,
    running,
    runError,
    handleRunQuery,
    handleRunStoredSql,
    handleRunDraftSql,
    canExecuteSql,
    sqlDraft,
    lastRunUsedDraft,
    onAskAgent,
    handlePromote,
    openChartModal,
    closeChartModal,
    handleAddChart,
    handleRemoveChart,
    handleChangeChartType,
    handleUpdateChart,
    handleApplyChartSuggestion,
    handleCustomizeChartSuggestion,
    mergeBlockData,
  } = model

  const [showTextOnlyHelp, setShowTextOnlyHelp] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [exportComposerOpen, setExportComposerOpen] = useState(false)
  const sectionPersist = useReportSectionPersist(sectionPersistScope)

  const ppConfig = postProcessConfig ?? data.post_process_config
  const hasPipelineErrorEarly = !!data.error && !data.sql
  const isTextOnlyEarly = !!data.narrative && !data.sql && !hasPipelineErrorEarly
  const hasSummaryBlock = !!(data.narrative || isTextOnlyEarly)
  const reportLayoutState = useReportLayout({
    data,
    messageId,
    sessionId,
    templateId,
    versionId,
    hasSummary: hasSummaryBlock,
    disablePersist: model.runSqlFromData,
    onLocalLayoutChange: model.onDraftLayoutChange,
  })
  const {
    scenarios,
    layout,
    canvasLayout,
    multiScenario,
    activePanelId,
    setActivePanel,
    updateLayout,
    setViewMode,
    renameScenario,
    canvasMode,
  } = reportLayoutState

  const activePanel = activePanelId as ReportPanelId
  const isPrimaryPanel = activePanel === 'primary'

  const openChartForActivePanel = useCallback(() => {
    openChartModal(null, activePanel)
  }, [openChartModal, activePanel])
  const activeExtraBlock = useMemo(
    () => data.extra_result_blocks?.find((b) => b.block_id === activePanel),
    [activePanel, data.extra_result_blocks],
  )
  const activeBlockDataset = !isPrimaryPanel ? blockDatasets[activePanel] : undefined

  const panelTableColumns = isPrimaryPanel ? tableColumns : (activeBlockDataset?.finalColumns ?? [])
  const panelTableRows = isPrimaryPanel ? tableRows : (activeBlockDataset?.finalRows ?? [])
  const panelShowTable = panelTableColumns.length > 0
  const panelCharts = useMemo(
    () => chartsForPanel(chartsEffective, activePanel),
    [chartsEffective, activePanel],
  )
  const panelChartSuggestions = chartSuggestionsByPanel[activePanel] ?? []
  const scenarioHasChartableData = useCallback(
    (panelId: ReportPanelId) => {
      if (panelId === 'primary') return showTable
      const ds = blockDatasets[panelId]
      return (ds?.finalColumns?.length ?? 0) > 0 && (ds?.finalRows?.length ?? 0) > 0
    },
    [blockDatasets, showTable],
  )
  const panelPpConfig = isPrimaryPanel
    ? (ppConfig ?? data.post_process_config)
    : (activeExtraBlock?.post_process_config ?? activeBlockDataset ? postProcessConfig : null)
  const panelHasTransformations = !!(panelPpConfig && panelPpConfig.length > 0)
  const panelSql = isPrimaryPanel ? data.sql : (activeExtraBlock?.sql ?? null)
  const panelHasSql = !!panelSql

  const showPanelSections = !canvasMode
  const showStackedAllScenarios = multiScenario && !canvasMode

  const ppSteps = describePostProcessSteps(ppConfig)
  const hasSql =
    !!data.sql || (data.extra_result_blocks ?? []).some((b) => !!b.sql)
  const isTextOnly = !!data.narrative && !hasSql && !hasPipelineError
  const showToolbar = hasSql || (data.extra_result_blocks ?? []).length > 0
  const canPersistCharts = !!(messageId && sessionId) || !!(templateId && versionId)
  const canExecuteBlocks = canPersistCharts
  const layoutEditable = !!(messageId || (templateId && versionId))
  const showChartsSection = useMemo(() => {
    if (!showPanelSections || !hasSql) return false
    if (showStackedAllScenarios) {
      return scenarios.some(
        (s) =>
          chartsForPanel(chartsEffective, s.panelId).length > 0 ||
          (canGenerateChart && scenarioHasChartableData(s.panelId)),
      )
    }
    return panelCharts.length > 0 || (panelShowTable && canGenerateChart)
  }, [
    showPanelSections,
    hasSql,
    showStackedAllScenarios,
    scenarios,
    chartsEffective,
    canGenerateChart,
    scenarioHasChartableData,
    panelCharts.length,
    panelShowTable,
  ])

  const panelLabels = useMemo(
    () => Object.fromEntries(scenarios.map((s) => [s.panelId, s.label])),
    [scenarios],
  )

  const displayCanvasLayout = useMemo(() => {
    return {
      ...canvasLayout,
      widgets: canvasLayout.widgets.map((w) => {
        if (w.kind === 'charts' && chartsForPanel(chartsEffective, w.panel_id).length > 0) {
          return { ...w, visible: true, h: Math.max(w.h, 6) }
        }
        return w
      }),
    }
  }, [canvasLayout, chartsEffective])

  const chartsDefaultOpen =
    chartsEffective.length > 0 ||
    (showStackedAllScenarios
      ? scenarios.some(
          (s) =>
            chartsForPanel(chartsEffective, s.panelId).length > 0 ||
            (scenarioHasChartableData(s.panelId) &&
              (chartSuggestionsByPanel[s.panelId]?.length ?? 0) > 0),
        )
      : panelCharts.length > 0 ||
        (panelShowTable && panelChartSuggestions.length > 0))

  const hasPostProcess = (ppConfig?.length ?? 0) > 0
  const panelNarrative = useMemo(
    () => resolvePanelNarrative(data, activePanel),
    [data, activePanel],
  )
  const validation = useMemo(
    () => resolvePanelValidation(data, activePanel),
    [data, activePanel],
  )
  const pipelineTrace = useMemo(
    () => resolvePanelPipelineTrace(data, activePanel),
    [data, activePanel],
  )
  const pipelineMeta = useMemo(() => pipelineMetaFromResponse(data), [data])
  const primaryUnchangedNote = primaryScenarioUnchangedNote(multiScenario, activePanel)

  const scenarioHasSql = useCallback(
    (panelId: ReportPanelId) => {
      if (panelId === 'primary') return !!data.sql
      return !!(data.extra_result_blocks?.find((b) => b.block_id === panelId)?.sql)
    },
    [data.extra_result_blocks, data.sql],
  )

  const scenarioPostProcessConfig = useCallback(
    (panelId: ReportPanelId) => {
      if (panelId === 'primary') return ppConfig ?? data.post_process_config
      return data.extra_result_blocks?.find((b) => b.block_id === panelId)?.post_process_config ?? null
    },
    [data.extra_result_blocks, data.post_process_config, ppConfig],
  )

  const stackedHasTransformations = useMemo(
    () =>
      scenarios.some((s) => (scenarioPostProcessConfig(s.panelId as ReportPanelId)?.length ?? 0) > 0),
    [scenarioPostProcessConfig, scenarios],
  )

  const showQuerySection = showPanelSections && hasSql && (showStackedAllScenarios || (panelHasSql && !!panelSql))

  const showTransformationsSection =
    showPanelSections &&
    (showStackedAllScenarios ? stackedHasTransformations : panelHasTransformations)

  const anyScenarioChartable = useMemo(
    () => scenarios.some((s) => scenarioHasChartableData(s.panelId as ReportPanelId)),
    [scenarioHasChartableData, scenarios],
  )

  const scenarioSlices = useMemo((): ExportScenarioSlice[] => {
    return scenarios.map((s) => {
      if (s.panelId === 'primary') {
        return {
          panelId: 'primary',
          label: s.label,
          sql: data.sql,
          postProcessConfig: ppConfig ?? data.post_process_config,
          tableColumns,
          tableRows,
          rawColumns,
          rawRows,
        }
      }
      const blk = data.extra_result_blocks?.find((b) => b.block_id === s.panelId)
      const ds = blockDatasets[s.panelId]
      return {
        panelId: s.panelId,
        label: s.label,
        sql: blk?.sql ?? null,
        postProcessConfig: blk?.post_process_config ?? null,
        tableColumns: ds?.finalColumns ?? blk?.columns ?? [],
        tableRows: ds?.finalRows ?? blk?.rows ?? [],
        rawColumns: ds?.rawColumns ?? blk?.raw_columns,
        rawRows: ds?.rawRows ?? blk?.raw_rows,
      }
    })
  }, [
    blockDatasets,
    data.extra_result_blocks,
    data.post_process_config,
    data.sql,
    ppConfig,
    rawColumns,
    rawRows,
    scenarios,
    tableColumns,
    tableRows,
  ])

  const canExportReport =
    scenarioSlices.some((s) => s.tableColumns.length > 0) ||
    chartsEffective.length > 0 ||
    hasPostProcess ||
    !!(data.narrative?.trim())

  const getExportInput = useCallback(
    (
      layoutDraft: typeof layout,
      widgetScope: 'quick' | 'composer' = 'quick',
    ): ExportReportInput | null =>
      buildExportReportInput({
        title: data.question?.trim() || 'Datamart report',
        narrative: data.narrative,
        primarySql: data.sql,
        scenarios: scenarioSlices,
        charts: chartsEffective,
        layout: layoutDraft,
        filenameBase: 'datamart-report',
        widgetScope,
      }),
    [
      chartsEffective,
      data.narrative,
      data.question,
      data.sql,
      layout,
      scenarioSlices,
    ],
  )

  const handleExportLayoutChange = useCallback(
    (next: typeof layout) => {
      updateLayout(next.widgets)
    },
    [updateLayout],
  )

  const runExportCsv = useCallback(
    async (input: ExportReportInput) => {
      if (exporting) return
      setExporting(true)
      toast.info(dmCopy.report.exportPreparingTitle, dmCopy.report.exportPreparingBody)
      try {
        await exportReportToCsv(input)
        const hasCharts = chartsEffective.length > 0
        const hasPp = (input.postProcessConfig?.length ?? 0) > 0
        toast.success(
          dmCopy.report.exportSuccessTitle,
          hasCharts || hasPp
            ? dmCopy.report.exportSuccessBodyWithCharts
            : dmCopy.report.exportSuccessBody,
        )
        setExportComposerOpen(false)
      } catch (err) {
        toast.error(
          dmCopy.report.exportFailedTitle,
          formatApiError(err, 'Could not export report.'),
        )
      } finally {
        setExporting(false)
      }
    },
    [chartsEffective.length, exporting, toast],
  )

  const runExportPdf = useCallback(
    async (input: ExportReportInput) => {
      if (exporting) return
      setExporting(true)
      toast.info(dmCopy.report.exportPreparingTitle, dmCopy.report.exportPreparingBody)
      try {
        await exportReportToPdf(input)
        const hasExtras =
          chartsEffective.length > 0 || (input.postProcessConfig?.length ?? 0) > 0
        toast.success(
          dmCopy.report.exportSuccessTitle,
          hasExtras ? dmCopy.report.exportPdfSuccessBodyFull : dmCopy.report.exportPdfSuccessBody,
        )
        setExportComposerOpen(false)
      } catch (err) {
        toast.error(
          dmCopy.report.exportFailedTitle,
          formatApiError(err, 'Could not export report.'),
        )
      } finally {
        setExporting(false)
      }
    },
    [chartsEffective.length, exporting, toast],
  )

  const handleExportCsv = useCallback(async () => {
    const input = getExportInput(layout)
    if (!input || exporting) return
    await runExportCsv(input)
  }, [exporting, getExportInput, layout, runExportCsv])

  const handleExportPdf = useCallback(async () => {
    const input = getExportInput(layout)
    if (!input || exporting) return
    await runExportPdf(input)
  }, [exporting, getExportInput, layout, runExportPdf])

  return (
    <article
      aria-label={dmCopy.report.ariaLabel}
      data-testid="datamart-report-card"
      style={{
        border: `1px solid ${dmColors.border}`,
        borderRadius: dmRadius.lg,
        overflow: 'hidden',
        background: dmColors.surface,
        boxShadow: '0 1px 3px rgba(15, 23, 42, 0.06)',
        animation: 'dmFadeUp 0.35s ease-out',
      }}
    >
      {hasSql && layoutEditable && (
        <DatamartScenarioBar
          scenarios={scenarios}
          activePanelId={activePanel}
          canvasMode={canvasMode}
          onSelectPanel={setActivePanel}
          onRename={renameScenario}
          onViewModeChange={setViewMode}
        />
      )}

      {primaryUnchangedNote && (
        <p
          style={{
            margin: `${dmSpace.md}px ${dmSpace.lg}px 0`,
            fontSize: 12,
            color: dmColors.textMuted,
            lineHeight: 1.55,
          }}
        >
          {primaryUnchangedNote}
        </p>
      )}
      {pipelineTrace && <DatamartPipelineSteps trace={pipelineTrace} />}
      {validation && (
        <>
          {multiScenario && !isPrimaryPanel && (
            <p
              style={{
                margin: `${dmSpace.sm}px ${dmSpace.lg}px 0`,
                fontSize: 12,
                color: dmColors.textMuted,
              }}
            >
              Validation for: {panelLabels[activePanel] ?? 'Added scenario'}
            </p>
          )}
          <DatamartValidationPanel
            validation={validation}
            pipelineMeta={pipelineMeta}
          />
        </>
      )}

      {showToolbar && (
        <DatamartReportToolbar
          statusBadge={statusBadge}
          canRunQuery={canRunQuery}
          running={running}
          hasUserRun={reportRun.hasUserRun}
          canExport={canExportReport}
          canGenerateChart={
            canGenerateChart && (showStackedAllScenarios ? anyScenarioChartable : showTable || panelShowTable)
          }
          chartSaving={chartSaving}
          exporting={exporting}
          showPromote={!!(hasSql && messageId && sessionId)}
          promoteSuccess={promoteSuccess}
          onRunQuery={handleRunQuery}
          onCustomizeExport={() => setExportComposerOpen(true)}
          onExportCsv={handleExportCsv}
          onExportPdf={handleExportPdf}
          onGenerateChart={
            showStackedAllScenarios
              ? () => {
                  const target =
                    scenarios.find((s) => scenarioHasChartableData(s.panelId as ReportPanelId))
                      ?.panelId ?? 'primary'
                  openChartModal(null, target as ReportPanelId)
                }
              : openChartForActivePanel
          }
          onPromote={() => setPromoting(true)}
          canUndoModification={model.canUndoModification}
          undoingModification={model.undoingModification}
          onUndoModification={model.onUndoModification}
          onRetryTurn={model.onRetryTurn}
          retryTurnLabel={
            model.onRetryTurn
              ? hasPipelineError || !!data.error
                ? dmCopy.toolbar.tryAgain
                : dmCopy.toolbar.regenerate
              : undefined
          }
        />
      )}

      {hasPipelineError && (
        <div
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: 10,
            margin: dmSpace.lg,
            padding: '12px 14px',
            background: dmColors.dangerBg,
            border: `1px solid ${dmColors.dangerBorder}`,
            borderRadius: dmRadius.md,
          }}
        >
          <AlertCircle size={15} color={dmColors.danger} style={{ flexShrink: 0, marginTop: 2 }} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <span style={{ fontSize: 13, color: dmColors.danger, lineHeight: 1.55 }}>
              {data.narrative?.trim() || data.error}
            </span>
            {model.onRetryTurn && (
              <button
                type="button"
                onClick={model.onRetryTurn}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  marginTop: dmSpace.sm,
                  fontSize: 12,
                  fontWeight: 600,
                  color: dmColors.danger,
                  background: dmColors.surface,
                  border: `1px solid ${dmColors.dangerBorder}`,
                  borderRadius: dmRadius.sm,
                  padding: '6px 10px',
                  cursor: 'pointer',
                }}
              >
                <RotateCcw size={12} />
                Try again
              </button>
            )}
          </div>
        </div>
      )}

      {canvasMode && hasSql && (
        <DatamartReportCanvas
          layout={displayCanvasLayout}
          activePanelId={activePanel}
          panelLabels={panelLabels}
          editable={layoutEditable}
          onLayoutChange={updateLayout}
          renderWidget={(w: ReportLayoutWidget) => {
            const panelBlock = data.extra_result_blocks?.find((b) => b.block_id === w.panel_id)
            const panelDs =
              w.panel_id === 'primary' ? null : blockDatasets[w.panel_id]
            const panelCols =
              w.panel_id === 'primary'
                ? tableColumns
                : (panelDs?.finalColumns ?? panelBlock?.columns ?? [])
            const panelRows =
              w.panel_id === 'primary'
                ? tableRows
                : (panelDs?.finalRows ?? panelBlock?.rows ?? [])
            const panelRawCols =
              w.panel_id === 'primary' ? rawColumns : (panelDs?.rawColumns ?? panelBlock?.raw_columns)
            const panelRawRows =
              w.panel_id === 'primary' ? rawRows : (panelDs?.rawRows ?? panelBlock?.raw_rows)
            const panelPp =
              w.panel_id === 'primary'
                ? (ppConfig ?? data.post_process_config)
                : (panelBlock?.post_process_config ?? null)
            const panelShowTableData = panelCols.length > 0
            const panelHasChartableRows = panelCols.length > 0 && panelRows.length > 0

            if (w.kind === 'summary' && (data.narrative || isTextOnly)) {
              return (
                <p style={{ fontSize: 14, color: dmColors.text, lineHeight: 1.75, margin: 0 }}>
                  {data.narrative}
                </p>
              )
            }
            if (w.kind === 'sql') {
              const sqlText = w.panel_id === 'primary' ? data.sql : panelBlock?.sql
              if (!sqlText) {
                return (
                  <p style={{ fontSize: 12, color: dmColors.textMuted, margin: 0 }}>
                    No query for this scenario.
                  </p>
                )
              }
              return (
                <pre
                  style={{
                    margin: 0,
                    fontSize: 11,
                    color: '#e2e8f0',
                    background: '#0f172a',
                    padding: 12,
                    borderRadius: dmRadius.md,
                    overflow: 'auto',
                    maxHeight: 220,
                  }}
                >
                  {sqlText}
                </pre>
              )
            }
            if (w.kind === 'transformations') {
              const steps = describePostProcessSteps(panelPp)
              if (!steps.length) {
                return (
                  <p style={{ fontSize: 12, color: dmColors.textMuted, margin: 0 }}>
                    No transformations for this scenario.
                  </p>
                )
              }
              return (
                <DatamartTransformationsSection
                  humanSteps={steps}
                  rawConfig={panelPp}
                  resultsLoaded={panelShowTableData}
                />
              )
            }
            if (w.kind === 'table' && w.panel_id === 'primary' && showTable) {
              return (
                <DatamartResultPanel
                  columns={tableColumns}
                  rows={tableRows}
                  rowCount={tableRowCount}
                  rawColumns={rawColumns}
                  rawRows={rawRows}
                  rawRowCount={rawRowCount}
                  postProcessConfig={ppConfig}
                />
              )
            }
            if (w.kind === 'table' && w.panel_id !== 'primary') {
              if (!panelShowTableData && panelBlock?.sql && canExecuteBlocks) {
                return (
                  <DatamartExtraBlockCard
                    block={panelBlock}
                    sessionId={sessionId}
                    messageId={messageId}
                    templateId={templateId}
                    versionId={versionId}
                    onBlockData={mergeBlockData}
                  />
                )
              }
              if (!panelShowTableData) {
                return (
                  <p style={{ fontSize: 12, color: dmColors.textMuted, margin: 0 }}>
                    Run this scenario&apos;s query to load results.
                  </p>
                )
              }
              return (
                <DatamartResultPanel
                  columns={panelCols}
                  rows={panelRows}
                  rowCount={panelRows.length}
                  rawColumns={panelRawCols}
                  rawRows={panelRawRows}
                  postProcessConfig={panelBlock?.post_process_config ?? null}
                />
              )
            }
            if (w.kind === 'charts') {
              const canvasPanelCharts = chartsForPanel(chartsEffective, w.panel_id)
              const canvasPanelSuggestions = chartSuggestionsByPanel[w.panel_id] ?? []
              const hasSavedCharts = canvasPanelCharts.length > 0
              if (!hasSavedCharts && !(panelShowTableData && canGenerateChart)) {
                return (
                  <p style={{ fontSize: 12, color: dmColors.textMuted, margin: 0 }}>
                    Run this scenario&apos;s query to unlock chart suggestions.
                  </p>
                )
              }
              return (
                <DatamartChartsSection
                  chartCount={canvasPanelCharts.length}
                  showTable={panelShowTableData || hasSavedCharts}
                  canGenerateChart={canGenerateChart && panelHasChartableRows}
                  canPersistCharts={canPersistCharts}
                  chartSaving={chartSaving}
                  scenarioLabel={panelLabels[w.panel_id]}
                  chartSuggestions={canvasPanelSuggestions}
                  chartsEffective={canvasPanelCharts}
                  tableColumns={panelCols}
                  tableRows={panelRows}
                  rawColumns={panelRawCols}
                  rawRows={panelRawRows}
                  blockDatasets={blockDatasets}
                  onOpenChartModal={() => openChartModal(null, w.panel_id)}
                  onApplySuggestion={handleApplyChartSuggestion}
                  onCustomizeSuggestion={handleCustomizeChartSuggestion}
                  onRemoveChart={canPersistCharts ? handleRemoveChart : undefined}
                  onChangeChartType={canPersistCharts ? handleChangeChartType : undefined}
                  onUpdateChart={canPersistCharts ? handleUpdateChart : undefined}
                />
              )
            }
            return (
              <p style={{ fontSize: 12, color: dmColors.textMuted, margin: 0 }}>
                {w.kind} — open stacked view or load data for this scenario.
              </p>
            )
          }}
        />
      )}

      {showPanelSections &&
        (panelNarrative || (isPrimaryPanel && isTextOnly)) &&
        !showStackedAllScenarios && (
        <DatamartReportSection
          title={dmCopy.sections.summary}
          sectionKey="summary"
          persist={sectionPersist}
          defaultOpen
        >
          {panelNarrative && (
            <p style={{ fontSize: 14, color: dmColors.text, lineHeight: 1.75, margin: 0 }}>
              {panelNarrative}
            </p>
          )}
          {isPrimaryPanel && isTextOnly && (
            <div style={{ marginTop: panelNarrative ? dmSpace.md : 0 }}>
              <p style={{ fontSize: 13, color: dmColors.textMuted, lineHeight: 1.55, margin: 0 }}>
                {dmCopy.textOnly.body}
              </p>
              <button
                type="button"
                onClick={() => setShowTextOnlyHelp((v) => !v)}
                style={{
                  marginTop: dmSpace.sm,
                  fontSize: 12,
                  fontWeight: 500,
                  color: dmColors.accent,
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  padding: 0,
                }}
              >
                {showTextOnlyHelp ? dmCopy.textOnly.hideDetails : dmCopy.textOnly.learnMore}
              </button>
              {showTextOnlyHelp && (
                <p
                  style={{
                    fontSize: 12,
                    color: dmColors.textMuted,
                    lineHeight: 1.55,
                    margin: `${dmSpace.sm}px 0 0`,
                    padding: dmSpace.md,
                    background: dmColors.surfaceMuted,
                    borderRadius: dmRadius.sm,
                    border: `1px solid ${dmColors.border}`,
                  }}
                >
                  {dmCopy.textOnly.helpBody}
                </p>
              )}
            </div>
          )}
        </DatamartReportSection>
      )}

      {showQuerySection && (
        <DatamartReportSection
          title={dmCopy.sections.query}
          sectionKey="query"
          persist={sectionPersist}
          defaultOpen={false}
          badge={
            showStackedAllScenarios
              ? String(scenarios.filter((s) => scenarioHasSql(s.panelId as ReportPanelId)).length)
              : dmCopy.sections.sqlBadge
          }
        >
          {showStackedAllScenarios ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: dmSpace.lg }}>
              {scenarios.map((scenario) => {
                const panelId = scenario.panelId as ReportPanelId
                if (!scenarioHasSql(panelId)) return null
                const isPrim = panelId === 'primary'
                const extra = data.extra_result_blocks?.find((b) => b.block_id === panelId)
                return (
                  <div key={panelId}>
                    <h3
                      style={{
                        margin: `0 0 ${dmSpace.sm}px`,
                        fontSize: 13,
                        fontWeight: 600,
                        color: dmColors.text,
                      }}
                    >
                      {scenario.label}
                    </h3>
                    {isPrim ? (
                      <DatamartSqlSection
                        storedSql={sqlDraft.storedSql}
                        draftSql={sqlDraft.draftSql}
                        isDirty={sqlDraft.isDirty}
                        running={running}
                        canExecute={canExecuteSql}
                        lastRunUsedDraft={lastRunUsedDraft}
                        onDraftChange={sqlDraft.setDraftSql}
                        onResetDraft={sqlDraft.resetDraft}
                        onRunStored={handleRunStoredSql}
                        onRunDraft={handleRunDraftSql}
                        onAskAgent={onAskAgent}
                      />
                    ) : (
                      extra?.sql && (
                        <pre
                          style={{
                            margin: 0,
                            fontSize: 11,
                            color: '#e2e8f0',
                            background: '#0f172a',
                            padding: 12,
                            borderRadius: dmRadius.md,
                            overflow: 'auto',
                          }}
                        >
                          {extra.sql}
                        </pre>
                      )
                    )}
                  </div>
                )
              })}
            </div>
          ) : isPrimaryPanel ? (
            <DatamartSqlSection
              storedSql={sqlDraft.storedSql}
              draftSql={sqlDraft.draftSql}
              isDirty={sqlDraft.isDirty}
              running={running}
              canExecute={canExecuteSql}
              lastRunUsedDraft={lastRunUsedDraft}
              onDraftChange={sqlDraft.setDraftSql}
              onResetDraft={sqlDraft.resetDraft}
              onRunStored={handleRunStoredSql}
              onRunDraft={handleRunDraftSql}
              onAskAgent={onAskAgent}
            />
          ) : (
            activeExtraBlock?.sql && (
              <pre
                style={{
                  margin: 0,
                  fontSize: 11,
                  color: '#e2e8f0',
                  background: '#0f172a',
                  padding: 12,
                  borderRadius: dmRadius.md,
                  overflow: 'auto',
                }}
              >
                {activeExtraBlock.sql}
              </pre>
            )
          )}
        </DatamartReportSection>
      )}

      {showTransformationsSection && (
        <DatamartReportSection
          title={dmCopy.sections.transformations}
          sectionKey="transformations"
          persist={sectionPersist}
          defaultOpen={!showTable}
          badge={
            showStackedAllScenarios
              ? String(scenarios.length)
              : String(ppSteps.length > 0 ? ppSteps.length : (ppConfig?.length ?? 0))
          }
        >
          {showStackedAllScenarios ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: dmSpace.lg }}>
              {scenarios.map((scenario) => {
                const panelId = scenario.panelId as ReportPanelId
                const rawCfg = scenarioPostProcessConfig(panelId)
                if (!rawCfg?.length) return null
                const steps = describePostProcessSteps(rawCfg)
                const isPrim = panelId === 'primary'
                const loaded = isPrim
                  ? showTable
                  : scenarioHasChartableData(panelId)
                return (
                  <div key={panelId}>
                    <h3
                      style={{
                        margin: `0 0 ${dmSpace.sm}px`,
                        fontSize: 13,
                        fontWeight: 600,
                        color: dmColors.text,
                      }}
                    >
                      {scenario.label}
                    </h3>
                    <DatamartTransformationsSection
                      humanSteps={steps}
                      rawConfig={rawCfg}
                      resultsLoaded={loaded}
                    />
                  </div>
                )
              })}
            </div>
          ) : (
            <DatamartTransformationsSection
              humanSteps={ppSteps}
              rawConfig={ppConfig}
              resultsLoaded={showTable}
            />
          )}
        </DatamartReportSection>
      )}

      {showPanelSections && hasSql && (
        <DatamartReportSection
          title={dmCopy.sections.results}
          sectionKey="results"
          persist={sectionPersist}
          defaultOpen
          badge={
            showStackedAllScenarios
              ? String(scenarios.length)
              : panelShowTable
                ? dmCopy.results.rowsBadge(isPrimaryPanel ? tableRowCount : panelTableRows.length)
                : dmCopy.results.notLoadedBadge
          }
        >
          {showStackedAllScenarios && (
            <DatamartStackedScenarios
              scenarios={scenarios}
              tableColumns={tableColumns}
              tableRows={tableRows}
              tableRowCount={tableRowCount}
              rawColumns={rawColumns}
              rawRows={rawRows}
              rawRowCount={rawRowCount}
              postProcessConfig={postProcessConfig}
              extraBlocks={data.extra_result_blocks}
              blockDatasets={blockDatasets}
              messageId={messageId}
              sessionId={sessionId}
              templateId={templateId}
              versionId={versionId}
              running={running}
              onBlockData={mergeBlockData}
            />
          )}

          {!showStackedAllScenarios && !isPrimaryPanel && canExecuteBlocks && activeExtraBlock && !panelShowTable && (
            <DatamartExtraBlockCard
              block={activeExtraBlock}
              sessionId={sessionId}
              messageId={messageId}
              templateId={templateId}
              versionId={versionId}
              onBlockData={mergeBlockData}
            />
          )}

          {!showStackedAllScenarios && isPrimaryPanel && !panelShowTable && !running && (
            <div
              style={{
                textAlign: 'center',
                padding: `${dmSpace.xl}px ${dmSpace.lg}px`,
                background: dmColors.surfaceMuted,
                borderRadius: dmRadius.md,
                border: `1px dashed ${dmColors.border}`,
              }}
            >
              <p style={{ fontSize: 14, color: dmColors.text, margin: '0 0 6px', fontWeight: 500 }}>
                {dmCopy.results.notLoadedTitle}
              </p>
              <p style={{ fontSize: 13, color: dmColors.textMuted, margin: 0, lineHeight: 1.5 }}>
                {dmCopy.results.notLoadedBody}
              </p>
            </div>
          )}

          {!showStackedAllScenarios && isPrimaryPanel && running && !panelShowTable && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: dmColors.textMuted }}>
              <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} />
              {dmCopy.results.running}
            </div>
          )}

          {runError && (
            <div
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 10,
                marginBottom: dmSpace.md,
                padding: '10px 14px',
                background: dmColors.dangerBg,
                border: `1px solid ${dmColors.dangerBorder}`,
                borderRadius: dmRadius.md,
              }}
            >
              <AlertCircle size={15} color={dmColors.danger} style={{ flexShrink: 0 }} />
              <span style={{ fontSize: 13, color: dmColors.danger }}>{runError}</span>
            </div>
          )}

          {!showStackedAllScenarios && panelShowTable && isPrimaryPanel && (
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
          {!showStackedAllScenarios && panelShowTable && !isPrimaryPanel && activeBlockDataset && (
            <DatamartResultPanel
              columns={panelTableColumns}
              rows={panelTableRows}
              rowCount={panelTableRows.length}
              rawColumns={activeBlockDataset.rawColumns}
              rawRows={activeBlockDataset.rawRows}
              postProcessConfig={activeExtraBlock?.post_process_config ?? null}
            />
          )}
        </DatamartReportSection>
      )}

      {!multiScenario &&
        canExecuteBlocks &&
        (data.extra_result_blocks ?? []).map((b) => (
          <DatamartExtraBlockCard
            key={b.block_id}
            block={b}
            sessionId={sessionId}
            messageId={messageId}
            templateId={templateId}
            versionId={versionId}
            onBlockData={mergeBlockData}
          />
        ))}

      {showChartsSection && (
        <DatamartReportSection
          title={dmCopy.sections.charts}
          sectionKey="charts"
          persist={sectionPersist}
          defaultOpen={chartsDefaultOpen}
          badge={
            chartsEffective.length > 0 ? String(chartsEffective.length) : undefined
          }
        >
          {showStackedAllScenarios ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: dmSpace.lg }}>
              {scenarios.map((scenario) => {
                const panelId = scenario.panelId
                const isPrim = panelId === 'primary'
                const sliceCharts = chartsForPanel(chartsEffective, panelId)
                const sliceSuggestions = chartSuggestionsByPanel[panelId] ?? []
                const ds = isPrim ? null : blockDatasets[panelId]
                const sliceCols = isPrim ? tableColumns : (ds?.finalColumns ?? [])
                const sliceRows = isPrim ? tableRows : (ds?.finalRows ?? [])
                const sliceShowTable = scenarioHasChartableData(panelId)
                const sliceHasSql = isPrim
                  ? !!data.sql
                  : !!(data.extra_result_blocks?.find((b) => b.block_id === panelId)?.sql)
                if (
                  !sliceHasSql ||
                  (sliceCharts.length === 0 &&
                    !(sliceShowTable && canGenerateChart))
                ) {
                  return null
                }
                return (
                  <section
                    key={panelId}
                    aria-label={`${scenario.label} charts`}
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
                      }}
                    >
                      {scenario.label}
                    </h3>
                    <DatamartChartsSection
                      chartCount={sliceCharts.length}
                      showTable={sliceShowTable}
                      canGenerateChart={canGenerateChart && sliceShowTable}
                      canPersistCharts={canPersistCharts}
                      chartSaving={chartSaving}
                      scenarioLabel={scenario.label}
                      chartSuggestions={sliceSuggestions}
                      chartsEffective={sliceCharts}
                      tableColumns={sliceCols}
                      tableRows={sliceRows}
                      rawColumns={isPrim ? rawColumns : ds?.rawColumns}
                      rawRows={isPrim ? rawRows : ds?.rawRows}
                      blockDatasets={blockDatasets}
                      onOpenChartModal={() => openChartModal(null, panelId)}
                      onApplySuggestion={handleApplyChartSuggestion}
                      onCustomizeSuggestion={handleCustomizeChartSuggestion}
                      onRemoveChart={canPersistCharts ? handleRemoveChart : undefined}
                      onChangeChartType={canPersistCharts ? handleChangeChartType : undefined}
                      onUpdateChart={canPersistCharts ? handleUpdateChart : undefined}
                    />
                  </section>
                )
              })}
            </div>
          ) : (
            <DatamartChartsSection
              chartCount={panelCharts.length}
              showTable={panelShowTable}
              canGenerateChart={canGenerateChart && panelShowTable}
              canPersistCharts={canPersistCharts}
              chartSaving={chartSaving}
              scenarioLabel={panelLabels[activePanel]}
              chartSuggestions={panelChartSuggestions}
              chartsEffective={panelCharts}
              tableColumns={panelTableColumns}
              tableRows={panelTableRows}
              rawColumns={isPrimaryPanel ? rawColumns : activeBlockDataset?.rawColumns}
              rawRows={isPrimaryPanel ? rawRows : activeBlockDataset?.rawRows}
              blockDatasets={blockDatasets}
              onOpenChartModal={openChartForActivePanel}
              onApplySuggestion={handleApplyChartSuggestion}
              onCustomizeSuggestion={handleCustomizeChartSuggestion}
              onRemoveChart={canPersistCharts ? handleRemoveChart : undefined}
              onChangeChartType={canPersistCharts ? handleChangeChartType : undefined}
              onUpdateChart={canPersistCharts ? handleUpdateChart : undefined}
            />
          )}
        </DatamartReportSection>
      )}

      <GenerateChartModal
        open={chartModalOpen}
        onClose={closeChartModal}
        datasets={chartModalDatasets}
        initialDraft={chartModalDraft}
        initialDatasetKey={chartModalInitialDatasetKey}
        onSave={handleAddChart}
      />

      <ExportComposerModal
        open={exportComposerOpen}
        onClose={() => setExportComposerOpen(false)}
        layout={layout}
        onLayoutChange={handleExportLayoutChange}
        scenarios={scenarios}
        hasSummary={hasSummaryBlock}
        narrative={data.narrative}
        scenarioSlices={scenarioSlices}
        charts={chartsEffective}
        getExportInput={(layoutDraft) => getExportInput(layoutDraft, 'composer')}
        exporting={exporting}
        onExportCsv={runExportCsv}
        onExportPdf={runExportPdf}
      />

      {promoting && (
        <div
          style={{
            margin: dmSpace.lg,
            padding: '12px 14px',
            background: dmColors.purpleBg,
            border: `1px solid ${dmColors.purpleBorder}`,
            borderRadius: dmRadius.md,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <BookmarkPlus size={14} color={dmColors.purple} />
            <input
              autoFocus
              value={promoteName}
              onChange={(e) => {
                setPromoteName(e.target.value)
                setPromoteError(null)
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handlePromote()
                if (e.key === 'Escape') {
                  setPromoting(false)
                  setPromoteName('')
                  setPromoteError(null)
                }
              }}
              placeholder={dmCopy.template.promotePlaceholder}
              className="dm-promote-input"
              style={{
                flex: 1,
                fontSize: 13,
                border: `1px solid ${promoteError ? '#fca5a5' : '#c4b5fd'}`,
                borderRadius: dmRadius.sm,
                padding: '6px 10px',
              }}
            />
            <button
              type="button"
              onClick={handlePromote}
              disabled={promoteLoading || !promoteName.trim()}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 5,
                fontSize: 12,
                fontWeight: 500,
                color: '#fff',
                background: promoteLoading ? '#5eead4' : dmColors.brand,
                border: 'none',
                borderRadius: dmRadius.sm,
                padding: '6px 12px',
                cursor: promoteLoading ? 'default' : 'pointer',
              }}
            >
              {promoteLoading ? (
                <Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} />
              ) : (
                <Check size={12} />
              )}
              {dmCopy.template.save}
            </button>
            <button
              type="button"
              onClick={() => {
                setPromoting(false)
                setPromoteName('')
                setPromoteError(null)
              }}
              style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 18, color: dmColors.textSubtle }}
            >
              ×
            </button>
          </div>
          {promoteError && (
            <p style={{ fontSize: 12, color: dmColors.danger, margin: `${dmSpace.sm}px 0 0` }}>{promoteError}</p>
          )}
        </div>
      )}
    </article>
  )
}

export default DatamartReportCard
