/**
 * State and handlers for one assistant report turn (chat message).
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useToast } from '../../../components/ui/Toast'
import type { DatamartResponse, SqlExecuteResponse } from '../../../services/datamartService'
import { datamartService } from '../../../services/datamartService'
import type { DatamartChartConfigV1, DatamartChartType } from '../charts/chartConfig'
import { isDatamartChartConfigV1 } from '../charts/chartConfig'
import { convertChartType } from '../charts/chartTypeAlternatives'
import {
  buildAllChartSuggestions,
  buildChartSuggestionsForPanel,
  suggestionToChartConfig,
  type ChartSuggestion,
  type ChartSuggestionInput,
} from '../charts/chartSuggestions'
import { resolveExtraBlockDataset } from '../lib/scenarioDataset'
import type { ChartDatasetOption } from '../charts/GenerateChartModal'
import { formatApiError } from '../lib/formatApiError'
import { buildScenarioList, type ReportLayoutPersistPatch } from '../lib/reportLayout'
import { runAllScenarioQueries } from '../lib/runScenarioQueries'
import { deriveReportRunState, deriveStatusBadge } from '../report/reportState'
import { useSqlDraft } from './useSqlDraft'

export interface ReportSnapshot {
  columns: string[]
  rowCount: number
  hasLoadedResults: boolean
  canGenerateChart: boolean
}

export interface ReportChartActions {
  openChartModal: (preferredDatasetKey?: string | null) => void
}

function toChartDatasetKey(panelId: string | null | undefined): string {
  if (panelId == null || panelId === 'primary') return '__primary__'
  return panelId
}

export interface UseDatamartReportModelOptions {
  data: DatamartResponse
  messageId?: string
  sessionId?: string
  /** Saved template version — uses template execute / layout APIs instead of session message. */
  templateId?: string
  versionId?: string
  templateMode?: boolean
  /** sessionStorage key for section expand state (chat message or template scope). */
  sectionPersistScope?: string
  isLatestTurn?: boolean
  onPromotedToTemplate?: (templateId: string, templateName: string) => void
  onChartConfigsChange?: (messageId: string, chartConfigs: unknown[]) => void
  /** Template mode: chart edits stay local until saveTemplateVersion. */
  onTemplateChartsChange?: (charts: unknown[]) => void
  onAskAgent?: (instruction: string) => void
  onReportSnapshot?: (snapshot: ReportSnapshot) => void
  onRegisterChartActions?: (actions: ReportChartActions | null) => void
  canUndoModification?: boolean
  undoingModification?: boolean
  onUndoModification?: () => void
  /** Re-run the user question for this turn (latest turn only). */
  onRetryTurn?: () => void
  /** Show SQL rows from API immediately (fresh chat turn). Session reload sets false. */
  hydrateResultsFromApi?: boolean
  /** Draft preview: Run query executes data.sql against the template version execute API. */
  runSqlFromData?: boolean
  /** Draft preview: layout/scenario renames merge into pending draft instead of PATCHing saved version. */
  onDraftLayoutChange?: (patch: ReportLayoutPersistPatch) => void
}

export function useDatamartReportModel({
  data,
  messageId,
  sessionId,
  templateId,
  versionId,
  templateMode = false,
  sectionPersistScope: sectionPersistScopeProp,
  isLatestTurn,
  onPromotedToTemplate,
  onChartConfigsChange,
  onTemplateChartsChange,
  onAskAgent,
  onReportSnapshot,
  onRegisterChartActions,
  canUndoModification,
  undoingModification,
  onUndoModification,
  onRetryTurn,
  hydrateResultsFromApi = false,
  runSqlFromData = false,
  onDraftLayoutChange,
}: UseDatamartReportModelOptions) {
  const toast = useToast()
  const isTemplateReport = templateMode && !!templateId && !!versionId
  const sqlDraftKey = isTemplateReport ? versionId : messageId

  const sqlDraft = useSqlDraft(data.sql, sqlDraftKey)
  const [lastRunUsedDraft, setLastRunUsedDraft] = useState(false)

  const [runResult, setRunResult] = useState<SqlExecuteResponse | null>(null)
  const [running, setRunning] = useState(false)
  const [runError, setRunError] = useState<string | null>(null)

  const [blockSqlResults, setBlockSqlResults] = useState<Record<string, SqlExecuteResponse>>({})

  const [localCharts, setLocalCharts] = useState<unknown[]>(data.chart_configs ?? [])
  const [chartModalOpen, setChartModalOpen] = useState(false)
  const [chartModalDraft, setChartModalDraft] = useState<DatamartChartConfigV1 | null>(null)
  const [chartModalInitialDatasetKey, setChartModalInitialDatasetKey] = useState<string | null>(
    null,
  )
  const [chartSaving, setChartSaving] = useState(false)

  const [promoting, setPromoting] = useState(false)
  const [promoteName, setPromoteName] = useState('')
  const [promoteLoading, setPromoteLoading] = useState(false)
  const [promoteSuccess, setPromoteSuccess] = useState(false)
  const [promoteError, setPromoteError] = useState<string | null>(null)

  useEffect(() => {
    setLocalCharts(data.chart_configs ?? [])
    setRunResult(null)
    setRunError(null)
    setBlockSqlResults({})
    setLastRunUsedDraft(false)
  }, [messageId, versionId])

  useEffect(() => {
    if (Array.isArray(data.chart_configs) && data.chart_configs.length > 0) {
      setLocalCharts(data.chart_configs)
    }
  }, [data.chart_configs])

  const hasPipelineError = !!data.error && !data.sql
  const hasRunnableSql =
    !!data.sql?.trim() ||
    (data.extra_result_blocks ?? []).some((b) => b.sql?.trim())
  const canRunQuery =
    hasRunnableSql && (isTemplateReport || (!!messageId && !!sessionId))
  const canExecuteSql =
    !!data.sql?.trim() && (isTemplateReport || (!!messageId && !!sessionId))

  const hasApiResults =
    hydrateResultsFromApi && data.columns.length > 0

  const reportRun = useMemo(
    () =>
      deriveReportRunState({
        data,
        runResult,
        running,
        runError,
        hydrateFromApi: hydrateResultsFromApi,
      }),
    [data, runResult, running, runError, hydrateResultsFromApi],
  )

  const statusBadge = useMemo(
    () => deriveStatusBadge(data, reportRun, hasPipelineError),
    [data, reportRun, hasPipelineError],
  )

  const tableColumns = hasApiResults ? data.columns : (runResult?.columns ?? [])
  const tableRows = hasApiResults ? data.rows : (runResult?.rows ?? [])
  const tableRowCount = hasApiResults ? data.row_count : (runResult?.row_count ?? 0)
  const rawColumns = hasApiResults ? data.raw_columns : (runResult?.raw_columns ?? null)
  const rawRows = hasApiResults ? data.raw_rows : (runResult?.raw_rows ?? null)
  const rawRowCount = hasApiResults ? data.raw_row_count : (runResult?.raw_row_count ?? null)
  const postProcessConfig = hasApiResults
    ? data.post_process_config
    : (runResult?.post_process_config ?? data.post_process_config)
  const showTable = tableColumns.length > 0

  const chartsEffective = localCharts.length > 0 ? localCharts : (data.chart_configs ?? [])
  const hasRawSnapshot = !!(rawColumns?.length && rawRows?.length)

  const mergeBlockData = useCallback((blockId: string, payload: SqlExecuteResponse) => {
    setBlockSqlResults((prev) => ({ ...prev, [blockId]: payload }))
  }, [])

  const runContext = useMemo(
    () => ({
      data,
      sessionId,
      messageId,
      templateId,
      versionId,
      isTemplateReport,
    }),
    [data, isTemplateReport, messageId, sessionId, templateId, versionId],
  )

  const executeAllScenarios = useCallback(
    async (opts?: { primarySqlOverride?: { sql: string }; markDraft?: boolean }) => {
      if (!isTemplateReport && (!messageId || !sessionId)) {
        toast.error(
          'Cannot run query',
          'This answer is not saved to a session yet. Send the question again or refresh the page.',
        )
        return
      }
      if (isTemplateReport && (!templateId || !versionId)) return
      const hasAnySql =
        !!data.sql?.trim() ||
        (data.extra_result_blocks ?? []).some((b) => b.sql?.trim())
      if (!hasAnySql) return

      setRunning(true)
      setRunError(null)
      setRunResult(null)
      setBlockSqlResults({})
      setLastRunUsedDraft(!!opts?.markDraft)

      const draftOverride =
        opts?.primarySqlOverride ??
        (runSqlFromData && templateMode && data.sql?.trim()
          ? { sql: data.sql.trim() }
          : undefined)

      try {
        const { primary, blocks, firstError } = await runAllScenarioQueries({
          ...runContext,
          primarySqlOverride: draftOverride,
        })
        if (primary?.error && !(primary.columns?.length ?? 0)) {
          setRunError(primary.error)
        } else if (primary) {
          setRunResult(primary)
          setRunError(primary.error ?? null)
        }
        if (Object.keys(blocks).length > 0) setBlockSqlResults(blocks)
        if (!primary?.error && firstError && !primary) setRunError(firstError)
        else if (!primary?.error && firstError && Object.keys(blocks).length === 0) {
          setRunError(firstError)
        }
      } catch (err: unknown) {
        setRunError(formatApiError(err, 'Failed to execute query.'))
      } finally {
        setRunning(false)
      }
    },
    [
      data.extra_result_blocks,
      data.sql,
      isTemplateReport,
      messageId,
      runContext,
      runSqlFromData,
      sessionId,
      templateId,
      templateMode,
      toast,
      versionId,
    ],
  )

  const blockDatasets = useMemo(() => {
    const out: Record<string, {
      finalColumns: string[]
      finalRows: unknown[][]
      rawColumns?: string[] | null
      rawRows?: unknown[][] | null
    }> = {}
    for (const b of data.extra_result_blocks ?? []) {
      const resolved = resolveExtraBlockDataset(b, blockSqlResults)
      if (!resolved.columns.length) continue
      out[b.block_id] = {
        finalColumns: resolved.columns,
        finalRows: resolved.rows,
        rawColumns: resolved.raw_columns,
        rawRows: resolved.raw_rows,
      }
    }
    return out
  }, [data.extra_result_blocks, blockSqlResults])

  const canShowCharts =
    chartsEffective.length > 0 &&
    (tableColumns.length > 0 || Object.keys(blockDatasets).length > 0)

  const primaryScenarioLabel = (data.report_layout as { primary_label?: string | null } | null | undefined)
    ?.primary_label

  const scenarioDescriptors = useMemo(
    () =>
      buildScenarioList(
        primaryScenarioLabel,
        data.question,
        data.extra_result_blocks,
      ),
    [primaryScenarioLabel, data.question, data.extra_result_blocks],
  )

  const chartModalDatasets: ChartDatasetOption[] = useMemo(() => {
    const out: ChartDatasetOption[] = []
    const primaryLabel =
      scenarioDescriptors.find((s) => s.isPrimary)?.label ?? 'Scenario 1'
    if (tableColumns.length > 0) {
      out.push({
        result_block_id: null,
        label: primaryLabel,
        columns: tableColumns,
        rows: tableRows,
        raw_columns: rawColumns,
        raw_rows: rawRows,
        post_process_config: postProcessConfig,
        hasRawSnapshot,
      })
    }
    for (const b of data.extra_result_blocks ?? []) {
      const resolved = resolveExtraBlockDataset(b, blockSqlResults)
      const cols = resolved.columns
      const rows = resolved.rows
      if (!cols.length) continue
      const scenarioLabel =
        scenarioDescriptors.find((s) => s.panelId === b.block_id)?.label ??
        b.title?.trim() ??
        `Scenario ${out.length + 1}`
      out.push({
        result_block_id: b.block_id,
        label: scenarioLabel,
        columns: cols,
        rows,
        raw_columns: resolved.raw_columns,
        raw_rows: resolved.raw_rows,
        post_process_config: b.post_process_config,
        hasRawSnapshot: !!(
          resolved.raw_columns?.length && resolved.raw_rows?.length
        ),
      })
    }
    return out
  }, [
    tableColumns,
    tableRows,
    rawColumns,
    rawRows,
    postProcessConfig,
    hasRawSnapshot,
    data.extra_result_blocks,
    blockSqlResults,
    scenarioDescriptors,
  ])

  const canGenerateChart =
    (isTemplateReport || (!!messageId && !!sessionId)) &&
    !promoteSuccess &&
    chartModalDatasets.length > 0

  const chartSuggestionInputs = useMemo((): ChartSuggestionInput[] => {
    const out: ChartSuggestionInput[] = []
    const primaryLabel =
      scenarioDescriptors.find((s) => s.isPrimary)?.label ?? 'Scenario 1'
    if (tableColumns.length > 0 && tableRows.length > 0) {
      out.push({
        result_block_id: null,
        dataset_label: primaryLabel,
        columns: tableColumns,
        rows: tableRows,
        raw_columns: rawColumns,
        raw_rows: rawRows,
        post_process_config: postProcessConfig,
      })
    }
    for (const b of data.extra_result_blocks ?? []) {
      const resolved = resolveExtraBlockDataset(b, blockSqlResults)
      if (!resolved.hasData) continue
      const scenarioLabel =
        scenarioDescriptors.find((s) => s.panelId === b.block_id)?.label ??
        b.title?.trim() ??
        `Scenario ${out.length + 1}`
      out.push({
        result_block_id: b.block_id,
        dataset_label: scenarioLabel,
        columns: resolved.columns,
        rows: resolved.rows,
        raw_columns: resolved.raw_columns,
        raw_rows: resolved.raw_rows,
        post_process_config: b.post_process_config,
      })
    }
    return out
  }, [
    tableColumns,
    tableRows,
    rawColumns,
    rawRows,
    postProcessConfig,
    data.extra_result_blocks,
    blockSqlResults,
    scenarioDescriptors,
  ])

  const chartSuggestionsByPanel = useMemo(() => {
    const map: Record<string, ChartSuggestion[]> = {}
    for (const s of scenarioDescriptors) {
      map[s.panelId] = buildChartSuggestionsForPanel(
        s.panelId,
        chartSuggestionInputs,
        chartsEffective,
      )
    }
    return map
  }, [chartSuggestionInputs, chartsEffective, scenarioDescriptors])

  const chartSuggestions = useMemo(
    () => buildAllChartSuggestions(chartSuggestionInputs, chartsEffective),
    [chartSuggestionInputs, chartsEffective],
  )

  const openChartModal = useCallback(
    (
      draft: DatamartChartConfigV1 | null = null,
      preferredDatasetKey?: string | null,
    ) => {
      setChartModalDraft(draft)
      if (draft?.result_block_id) {
        setChartModalInitialDatasetKey(draft.result_block_id)
      } else if (preferredDatasetKey !== undefined) {
        setChartModalInitialDatasetKey(toChartDatasetKey(preferredDatasetKey))
      } else {
        setChartModalInitialDatasetKey('__primary__')
      }
      setChartModalOpen(true)
    },
    [],
  )

  const closeChartModal = useCallback(() => {
    setChartModalOpen(false)
    setChartModalDraft(null)
    setChartModalInitialDatasetKey(null)
  }, [])

  const handleRunQuery = useCallback(async () => {
    await executeAllScenarios()
  }, [executeAllScenarios])

  const handleRunStoredSql = handleRunQuery

  const handleRunDraftSql = useCallback(async () => {
    if (!sqlDraft.isDirty) return
    await executeAllScenarios({
      primarySqlOverride: { sql: sqlDraft.draftSql },
      markDraft: true,
    })
  }, [executeAllScenarios, sqlDraft.isDirty, sqlDraft.draftSql])

  const handlePromote = useCallback(async () => {
    if (!messageId || !sessionId) return
    const name = promoteName.trim()
    if (!name) return
    setPromoteLoading(true)
    setPromoteError(null)
    try {
      const template = await datamartService.promoteToTemplate(name, sessionId, messageId)
      setPromoteSuccess(true)
      setPromoting(false)
      setPromoteName('')
      onPromotedToTemplate?.(template.id, template.name)
      toast.success('Template saved', template.name)
    } catch (err: unknown) {
      setPromoteError(formatApiError(err, 'Failed to save template. Please try again.'))
    } finally {
      setPromoteLoading(false)
    }
  }, [messageId, sessionId, promoteName, onPromotedToTemplate, toast])

  const persistCharts = useCallback(
    async (next: unknown[]) => {
      if (isTemplateReport) {
        setLocalCharts(next)
        onTemplateChartsChange?.(next)
        return
      }
      if (!messageId || !sessionId) return
      setChartSaving(true)
      try {
        const res = await datamartService.putMessageCharts(sessionId, messageId, next)
        setLocalCharts(res.chart_configs)
        onChartConfigsChange?.(messageId, res.chart_configs)
      } catch (err: unknown) {
        toast.error('Chart not saved', formatApiError(err, 'Failed to save chart.'))
      } finally {
        setChartSaving(false)
      }
    },
    [
      isTemplateReport,
      messageId,
      sessionId,
      onChartConfigsChange,
      onTemplateChartsChange,
      toast,
    ],
  )

  const chartsBase = useCallback(
    () => (localCharts.length > 0 ? localCharts : (data.chart_configs ?? [])),
    [localCharts, data.chart_configs],
  )

  const handleAddChart = useCallback(
    async (chart: DatamartChartConfigV1, options?: { toastLabel?: string }) => {
      await persistCharts([...chartsBase(), chart])
      closeChartModal()
      const label = options?.toastLabel ?? chart.title?.trim() ?? 'Chart'
      toast.success('Chart saved', label)
    },
    [persistCharts, chartsBase, closeChartModal, toast],
  )

  const handleRemoveChart = useCallback(
    async (chartId: string) => {
      const next = chartsBase().filter(
        (c) => !(isDatamartChartConfigV1(c) && c.id === chartId),
      )
      await persistCharts(next)
      toast.success('Chart removed', 'The chart was removed from this report.')
    },
    [persistCharts, chartsBase, toast],
  )

  const handleChangeChartType = useCallback(
    async (chartId: string, newType: DatamartChartType) => {
      const next = chartsBase().map((c) => {
        if (!isDatamartChartConfigV1(c) || c.id !== chartId) return c
        return convertChartType(c, newType)
      })
      await persistCharts(next)
    },
    [persistCharts, chartsBase],
  )

  const handleUpdateChart = useCallback(
    async (chartId: string, updated: DatamartChartConfigV1) => {
      const next = chartsBase().map((c) => {
        if (!isDatamartChartConfigV1(c) || c.id !== chartId) return c
        return updated
      })
      await persistCharts(next)
    },
    [persistCharts, chartsBase],
  )

  const handleApplyChartSuggestion = useCallback(
    (s: ChartSuggestion) => {
      void handleAddChart(suggestionToChartConfig(s), { toastLabel: s.label })
    },
    [handleAddChart],
  )

  const handleCustomizeChartSuggestion = useCallback(
    (s: ChartSuggestion) => {
      openChartModal(suggestionToChartConfig(s))
    },
    [openChartModal],
  )

  useEffect(() => {
    const shouldPublish = (isLatestTurn || isTemplateReport) && onReportSnapshot
    if (!shouldPublish) return
    const hasChartableData =
      showTable || Object.keys(blockDatasets).length > 0
    onReportSnapshot({
      columns: tableColumns,
      rowCount: tableRowCount,
      hasLoadedResults: hasChartableData,
      canGenerateChart: canGenerateChart && hasChartableData,
    })
  }, [
    isLatestTurn,
    isTemplateReport,
    onReportSnapshot,
    blockDatasets,
    tableColumns,
    tableRowCount,
    showTable,
    canGenerateChart,
  ])

  useEffect(() => {
    const shouldRegister = (isLatestTurn || isTemplateReport) && onRegisterChartActions
    if (!shouldRegister) return undefined
    onRegisterChartActions({ openChartModal: () => openChartModal() })
    return () => onRegisterChartActions(null)
  }, [isLatestTurn, isTemplateReport, onRegisterChartActions, openChartModal])

  return {
    data,
    messageId,
    sessionId,
    templateId: isTemplateReport ? templateId : undefined,
    versionId: isTemplateReport ? versionId : undefined,
    templateMode: isTemplateReport,
    sectionPersistScope:
      sectionPersistScopeProp ?? (messageId ? `msg:${messageId}` : undefined),
    hasPipelineError,
    canRunQuery,
    canExecuteSql,
    sqlDraft,
    lastRunUsedDraft,
    onAskAgent,
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
    canShowCharts,
    chartModalDatasets,
    canGenerateChart,
    chartSuggestions,
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
    hydrateResultsFromApi,
    canUndoModification,
    undoingModification,
    onUndoModification,
    onRetryTurn,
    runSqlFromData,
    onDraftLayoutChange,
  }
}

export type DatamartReportModel = ReturnType<typeof useDatamartReportModel>
