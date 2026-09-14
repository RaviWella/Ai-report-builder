import { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import axios from 'axios'
import { Database, User, ChevronUp, Loader2, MessageCircle } from 'lucide-react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { useToast } from '../../components/ui/Toast'
import {
  datamartService,
  type DatamartResponse,
  type GroundingPreviewResponse,
  type MessageResponse,
} from '../../services/datamartService'
import { DATAMART_GROUNDING_CONFIRM } from '../../env'
import DatamartGroundingConfirm from './chat/DatamartGroundingConfirm'
import { getErrorMessage } from '../../services/api'
import DatamartMessage from './components/DatamartMessage'
import DatamartComposer from './chat/DatamartComposer'
import DatamartUserMessage from './chat/DatamartUserMessage'
import DatamartErrorTurn from './chat/DatamartErrorTurn'
import DatamartLoadingTurn from './chat/DatamartLoadingTurn'
import { buildSqlChangePrompt } from './lib/askAgentPrompt'
import {
  buildLatestTurnContext,
  findLatestAssistantTurn,
} from './lib/latestTurnContext'
import { useChatLoadingStage } from './hooks/useChatLoadingStage'
import { streamDatamartChat } from './lib/chatStream'
import type { PipelineTrace } from './lib/pipelineTrace'
import type { ReportChartActions, ReportSnapshot } from './hooks/useDatamartReportModel'
import DatamartSidebar from './components/DatamartSidebar'
import { DatamartChatHeader } from './components/DatamartChatHeader'
import DatamartWorkspaceShell from './workspace/DatamartWorkspaceShell'
import { useDatamartWorkspaceSidebar } from './hooks/useDatamartWorkspaceSidebar'
import { mergeAssistantMessagesFromApi } from './lib/mergeMessageFromApi'
import { truncateMessagesFromTurn } from './lib/truncateMessagesFromTurn'
import type { DatamartFollowUpMode } from './lib/followUpMode'
import {
  isAwaitingClarification,
  resolveFollowUpModeForSend,
} from './lib/clarificationReply'
import { normalizeValidation } from './lib/validation'
import {
  buildModifyScenarioContextKey,
  buildTargetScenarioPayload,
  defaultModifyTargetIds,
} from './lib/modifyScenarioTargets'
import {
  buildRetryContextFromMessages,
  canRetryFailedAssistant,
  hasPriorSuccessfulAssistant,
  messagesAfterRemovingFailedTurn,
  type RetrySendContext,
} from './lib/chatRetry'
import { getUndoInfoFromMessages } from './lib/undoModification'
import { navigateToNewChat } from './lib/chatSessionRoute'
import { navigateToTemplate } from './lib/templateNavigation'
import { getActiveTenantId } from '../../lib/activeTenant'
import { useDatamartWorkspaceRoute } from './hooks/useDatamartWorkspaceRoute'
import DatamartSyncProgress from './components/DatamartSyncProgress'
import {
  initialSyncSteps,
  runDatamartFullSync,
  type DatamartSyncStep,
} from './lib/datamartSyncSteps'

import './datamart-page.css'

function UserAvatar() {
  return (
    <div className="dm-avatar dm-avatar--user" aria-hidden>
      <User size={18} color="white" />
    </div>
  )
}

function AgentAvatar() {
  return (
    <div className="dm-avatar dm-avatar--agent" aria-hidden>
      <Database size={17} color="white" />
    </div>
  )
}

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  text?: string
  data?: DatamartResponse
  error?: string
  messageId?: string
  sessionId?: string
  turnIndex?: number
  followUpMode?: DatamartFollowUpMode
  /** Scenario targets locked in when this user message was sent (for retry). */
  targetScenarioIds?: string[]
  /** Fresh assistant turn: show API rows immediately. Session history: manual Run only. */
  hydrateResults?: boolean
}

const PAGE_SIZE = 5

function historyToChat(msgs: MessageResponse[], sessionId: string): ChatMessage[] {
  const byTurn: Record<number, { user?: MessageResponse; assistant?: MessageResponse }> = {}
  for (const m of msgs) {
    if (!byTurn[m.turn_index]) byTurn[m.turn_index] = {}
    byTurn[m.turn_index][m.role as 'user' | 'assistant'] = m
  }
  const result: ChatMessage[] = []
  const sorted = Object.values(byTurn).sort((a, b) => (a.user?.turn_index ?? 0) - (b.user?.turn_index ?? 0))
  let seenSuccessfulReport = false
  for (const turn of sorted) {
    if (turn.user) {
      result.push({
        id: turn.user.id,
        role: 'user',
        text: turn.user.content,
        turnIndex: turn.user.turn_index,
        followUpMode:
          turn.user.follow_up_mode ??
          (seenSuccessfulReport ? undefined : 'new_question'),
      })
    }
    if (turn.assistant) {
      const sql = turn.assistant.sql_script ?? null
      const validationRaw = turn.assistant.validation as
        | (DatamartResponse['validation'] & {
            pipeline_trace?: DatamartResponse['pipeline_trace']
            pipeline_meta?: DatamartResponse['pipeline_meta']
          })
        | undefined
      const validation = validationRaw
        ? normalizeValidation(validationRaw as DatamartResponse['validation']) ?? undefined
        : undefined
      const pipelineTrace =
        validationRaw?.pipeline_trace ?? null
      const pipelineMeta = validationRaw?.pipeline_meta ?? null
      const extraBlocks = turn.assistant.extra_result_blocks?.map((blk) => ({
        block_id: String(blk.block_id ?? ''),
        title: blk.title ?? null,
        sql: blk.sql_script ?? null,
        post_process_config: Array.isArray(blk.post_process_config) ? blk.post_process_config : null,
        narrative: '',
        columns: [],
        rows: [],
        row_count: 0,
        error: null,
      })) ?? undefined
      result.push({
        id: turn.assistant.id, role: 'assistant',
        messageId: turn.assistant.id,
        sessionId,
        turnIndex: turn.assistant.turn_index,
        data: {
          question: turn.assistant.question_ref ?? '',
          narrative: turn.assistant.content,
          sql,
          post_process_config: turn.assistant.post_process_config ?? null,
          chart_configs: turn.assistant.chart_configs ?? null,
          extra_result_blocks: extraBlocks,
          report_layout: turn.assistant.report_layout ?? null,
          columns: [], rows: [], row_count: 0, error: null, session_id: sessionId, message_id: turn.assistant.id,
          validation: validation ?? null,
          pipeline_trace: pipelineTrace,
          pipeline_meta: pipelineMeta,
        },
        hydrateResults: false,
      })
      if (sql?.trim() || (extraBlocks?.some((b) => b.sql?.trim()) ?? false)) {
        seenSuccessfulReport = true
      }
    }
  }
  return result
}

// ── Main component ────────────────────────────────────────────────

type DatamartChatProps = {
  onOpenSidebar?: () => void
}

export default function DatamartChat({ onOpenSidebar }: DatamartChatProps) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { sessionId: routeSessionId } = useDatamartWorkspaceRoute()
  const toast = useToast()

  const activeTenantId = getActiveTenantId()

  const bootstrapQueryKey = ['datamart', 'bootstrap', activeTenantId] as const

  const {
    data: bootstrapMeta,
    isLoading: bootstrapLoading,
    isError: bootstrapError,
    isFetching: bootstrapRefreshing,
  } = useQuery({
    queryKey: bootstrapQueryKey,
    queryFn: () => datamartService.bootstrap(),
    staleTime: 15 * 60 * 1000,
    retry: 1,
  })

  const [fullSyncActive, setFullSyncActive] = useState(false)
  const [syncSteps, setSyncSteps] = useState<DatamartSyncStep[]>(initialSyncSteps)

  const refreshBootstrapMetadata = useCallback(() => {
    if (fullSyncActive) return
    setFullSyncActive(true)
    setSyncSteps(initialSyncSteps())
    void (async () => {
      try {
        const data = await runDatamartFullSync(setSyncSteps)
        queryClient.setQueryData(bootstrapQueryKey, data)
        const cat = data.catalog_sync
        if (cat && cat.ok === false) {
          toast.error(
            'Catalog sync failed',
            cat.error ?? 'Semantic catalog could not be refreshed.',
          )
          return
        }
        const detail = cat?.table_count
          ? `${data.total_tables} tables · catalog updated (${cat.table_count} warehouse tables scanned)`
          : `${data.total_tables} tables · catalog and metadata synced`
        if (cat?.warnings?.length) {
          toast.success('Synced with warnings', `${detail}. ${cat.warnings[0]}`)
        } else {
          toast.success('Full sync complete', detail)
        }
      } catch (err) {
        toast.error('Sync failed', getErrorMessage(err))
      } finally {
        setFullSyncActive(false)
      }
    })()
  }, [queryClient, bootstrapQueryKey, fullSyncActive, toast])

  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [composerHint, setComposerHint] = useState<string | null>(null)
  const [hideEditingPill, setHideEditingPill] = useState(false)
  const [editingTurn, setEditingTurn] = useState<{ turnIndex: number; draft: string } | null>(null)
  const [followUpMode, setFollowUpMode] = useState<DatamartFollowUpMode>('continue_last')
  const [modifyTargetIds, setModifyTargetIds] = useState<string[]>([])
  const [undoingModification, setUndoingModification] = useState(false)
  const [latestSnapshot, setLatestSnapshot] = useState<ReportSnapshot | null>(null)
  const [loading, setLoading] = useState(false)
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [loadingOlder, setLoadingOlder] = useState(false)
  const [currentPage, setCurrentPage] = useState(1)
  const [hasMorePages, setHasMorePages] = useState(false)
  const [groundingPending, setGroundingPending] = useState<{
    question: string
    preview: GroundingPreviewResponse
    sendOptions?: {
      skipUserBubble?: boolean
      editFromTurnIndex?: number
      followUpMode?: DatamartFollowUpMode
    }
  } | null>(null)

  const inputRef = useRef<HTMLTextAreaElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const chatAreaRef = useRef<HTMLDivElement>(null)
  const lastSendContextRef = useRef<RetrySendContext | null>(null)
  const latestChartActionsRef = useRef<ReportChartActions | null>(null)
  const [pipelineFinishing, setPipelineFinishing] = useState(false)
  const [livePipelineTrace, setLivePipelineTrace] = useState<PipelineTrace | null>(
    null,
  )
  const loadingStage = useChatLoadingStage(loading || pipelineFinishing, {
    finishing: pipelineFinishing,
  })

  const { data: suggestionsData } = useQuery({
    queryKey: ['datamart-suggestions'],
    queryFn: () => datamartService.getSuggestions(),
    staleTime: Infinity,
  })
  const suggestions = suggestionsData?.questions ?? []

  const latestAssistantTurn = useMemo(
    () => findLatestAssistantTurn(messages),
    [messages],
  )

  const awaitingClarification = useMemo(() => {
    const data = latestAssistantTurn?.data
    if (!data) return false
    return isAwaitingClarification(data.validation ?? undefined, data.sql)
  }, [latestAssistantTurn])

  const clarificationAnchor =
    latestAssistantTurn?.data?.validation?.anchor_question ??
    latestAssistantTurn?.data?.question ??
    null

  const turnContext = useMemo(
    () => buildLatestTurnContext(latestAssistantTurn, latestSnapshot),
    [latestAssistantTurn, latestSnapshot],
  )

  const editingContext = useMemo(() => {
    if (hideEditingPill) return null
    return turnContext
  }, [turnContext, hideEditingPill])

  const modifyContextKey = useMemo(
    () =>
      buildModifyScenarioContextKey(
        latestAssistantTurn?.messageId ?? '',
        turnContext?.scenarios,
      ),
    [
      latestAssistantTurn?.messageId,
      turnContext?.scenarios?.map((s) => s.panelId).join('|'),
      turnContext?.multiScenario,
    ],
  )

  useEffect(() => {
    if (!turnContext?.multiScenario) {
      setModifyTargetIds([])
      return
    }
    setModifyTargetIds(defaultModifyTargetIds(turnContext.scenarios))
    // Re-init only when the assistant turn or scenario ids change — not on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- modifyContextKey encodes scenario set
  }, [modifyContextKey])

  const showFollowUpMode =
    !loadingHistory &&
    !editingTurn &&
    messages.length > 0 &&
    !!latestAssistantTurn?.data &&
    !awaitingClarification

  const showQuickActions =
    showFollowUpMode &&
    followUpMode === 'continue_last' &&
    !!turnContext?.sql

  const undoInfo = useMemo(() => {
    const turnRows = messages.flatMap((m) => {
      if (m.turnIndex == null) return []
      if (m.role === 'user') {
        return [{
          role: 'user',
          turn_index: m.turnIndex,
          follow_up_mode: m.followUpMode ?? null,
        }]
      }
      return [{ role: 'assistant', turn_index: m.turnIndex }]
    })
    return getUndoInfoFromMessages(turnRows)
  }, [messages])

  useEffect(() => {
    const area = chatAreaRef.current
    if (!area) return
    const scrollToEnd = () => {
      area.scrollTo({ top: area.scrollHeight, behavior: 'smooth' })
    }
    requestAnimationFrame(scrollToEnd)
  }, [messages, loading, livePipelineTrace])

  useEffect(() => {
    setTimeout(() => inputRef.current?.focus(), 100)
  }, [activeSessionId])

  const loadSession = useCallback(async (sessionId: string) => {
    setLoadingHistory(true)
    setActiveSessionId(sessionId)
    setMessages([])
    setLatestSnapshot(null)
    setHideEditingPill(false)
    setFollowUpMode('continue_last')
    setCurrentPage(1)
    setHasMorePages(false)
    try {
      const resp = await datamartService.getSessionMessages(sessionId, 1, PAGE_SIZE)
      const chatMsgs = historyToChat(resp.messages, sessionId)
      setMessages(chatMsgs)
      setHasMorePages(resp.has_more)
      const lastUser = [...chatMsgs].reverse().find((m) => m.role === 'user' && m.followUpMode)
      if (lastUser?.followUpMode) {
        setFollowUpMode(lastUser.followUpMode)
      }
    } catch { setMessages([]) }
    finally { setLoadingHistory(false) }
  }, [])

  const loadOlderMessages = useCallback(async () => {
    if (!activeSessionId || loadingOlder || !hasMorePages) return
    setLoadingOlder(true)
    const nextPage = currentPage + 1
    const area = chatAreaRef.current
    const prevScrollHeight = area?.scrollHeight ?? 0
    try {
      const resp = await datamartService.getSessionMessages(activeSessionId, nextPage, PAGE_SIZE)
      const older = historyToChat(resp.messages, activeSessionId)
      setMessages((prev) => [...older, ...prev])
      setHasMorePages(resp.has_more)
      setCurrentPage(nextPage)
      requestAnimationFrame(() => {
        if (area) area.scrollTop = area.scrollHeight - prevScrollHeight
      })
    } catch { /* ignore */ }
    finally { setLoadingOlder(false) }
  }, [activeSessionId, currentPage, hasMorePages, loadingOlder])

  const startNewSession = useCallback(() => {
    setActiveSessionId(null)
    setMessages([])
    setInput('')
    setComposerHint(null)
    setHideEditingPill(false)
    setEditingTurn(null)
    setFollowUpMode('continue_last')
    setLatestSnapshot(null)
    setCurrentPage(1)
    setHasMorePages(false)
    setTimeout(() => inputRef.current?.focus(), 100)
  }, [])

  const sidebarProps = useDatamartWorkspaceSidebar({
    activeSessionId,
    activeTemplateId: null,
    navigate,
    onSessionDeleted: startNewSession,
  })

  const sidebar = {
    ...sidebarProps,
    onNewSession: () => {
      startNewSession()
      navigateToNewChat(
        navigate,
        typeof window !== 'undefined' ? window.location.search : '',
      )
    },
  }

  // Load session from URL (browser search is source of truth — avoids stale searchParams race).
  useEffect(() => {
    if (!routeSessionId) return
    if (routeSessionId !== activeSessionId) {
      void loadSession(routeSessionId)
    }
  }, [routeSessionId, activeSessionId, loadSession])

  const handleChartConfigsChange = useCallback((messageId: string, chartConfigs: unknown[]) => {
    setMessages((prev) => prev.map((m) => {
      if (m.messageId !== messageId || !m.data) return m
      return { ...m, data: { ...m.data, chart_configs: chartConfigs } }
    }))
  }, [])

  const handleAskAgent = useCallback((instruction: string) => {
    setFollowUpMode('continue_last')
    const prompt = buildSqlChangePrompt(instruction)
    setInput(prompt)
    setComposerHint('SQL change — review the message below, then send')
    requestAnimationFrame(() => {
      const el = inputRef.current
      if (!el) return
      el.focus()
      el.style.height = 'auto'
      el.style.height = `${Math.min(el.scrollHeight, 200)}px`
    })
  }, [])

  const cancelEditTurn = useCallback(() => {
    setEditingTurn(null)
  }, [])

  const startEditTurn = useCallback((turnIndex: number, question: string) => {
    if (loading) return
    setEditingTurn({ turnIndex, draft: question })
  }, [loading])

  const send = useCallback(async (
    question: string,
    options?: {
      skipUserBubble?: boolean
      editFromTurnIndex?: number
      followUpMode?: DatamartFollowUpMode
      targetScenarioIds?: string[]
      confirmedTables?: string[]
      skipGroundingConfirm?: boolean
      isRetry?: boolean
      /** Retry already truncated in-memory state; only append the user bubble. */
      skipTurnTruncate?: boolean
    },
  ) => {
    const q = question.trim()
    if (!q) return
    if (loading) {
      toast.info('Still generating', 'Wait for the current reply to finish, then send again.')
      return
    }
    const editTurnIndex = options?.editFromTurnIndex
    const isEditResend = editTurnIndex != null && !!activeSessionId
    const modeForRequest = options?.followUpMode ?? followUpMode
    const hasPriorReport = hasPriorSuccessfulAssistant(messages, messages.length)
    const sendFollowUpMode: DatamartFollowUpMode | undefined = (() => {
      if (isEditResend) return options?.followUpMode
      if (awaitingClarification) {
        return resolveFollowUpModeForSend(modeForRequest, true)
      }
      if (options?.followUpMode !== undefined) return options.followUpMode
      if (!activeSessionId || !hasPriorReport) return 'new_question'
      if (activeSessionId && latestAssistantTurn?.data) return modeForRequest
      return undefined
    })()
    const targetScenarioIds =
      options?.targetScenarioIds ??
      buildTargetScenarioPayload(
        !!turnContext?.multiScenario,
        sendFollowUpMode ?? 'continue_last',
        modifyTargetIds,
      )
    lastSendContextRef.current = {
      question: q,
      followUpMode: sendFollowUpMode ?? 'new_question',
      targetScenarioIds: targetScenarioIds ?? undefined,
      editFromTurnIndex: isEditResend ? editTurnIndex : undefined,
    }
    if (
      sendFollowUpMode === 'continue_last' &&
      turnContext?.multiScenario &&
      !targetScenarioIds?.length
    ) {
      toast.error('Select scenarios', 'Choose at least one scenario to modify.')
      return
    }

    const needsGroundingConfirm =
      DATAMART_GROUNDING_CONFIRM &&
      !options?.isRetry &&
      !options?.skipGroundingConfirm &&
      !options?.confirmedTables &&
      !isEditResend &&
      sendFollowUpMode !== 'clarify_reply' &&
      (sendFollowUpMode === 'new_question' || !activeSessionId)

    if (needsGroundingConfirm) {
      try {
        const preview = await datamartService.previewGrounding({
          question: q,
          session_id: activeSessionId,
          follow_up_mode: sendFollowUpMode ?? (!activeSessionId ? 'new_question' : undefined),
        })
        setGroundingPending({ question: q, preview, sendOptions: options })
        return
      } catch (err) {
        toast.error('Source preview failed', getErrorMessage(err))
        return
      }
    }

    const tempId = `temp-${Date.now()}`
    setInput('')
    setComposerHint(null)
    setHideEditingPill(false)
    setEditingTurn(null)
    if (isEditResend && options?.skipTurnTruncate) {
      setMessages((prev) => [
        ...prev,
        {
          id: tempId,
          role: 'user',
          text: q,
          turnIndex: editTurnIndex,
          followUpMode: sendFollowUpMode,
          targetScenarioIds: targetScenarioIds ?? undefined,
        },
      ])
    } else if (isEditResend) {
      setMessages((prev) => [
        ...truncateMessagesFromTurn(prev, editTurnIndex),
        {
          id: tempId,
          role: 'user',
          text: q,
          turnIndex: editTurnIndex,
          followUpMode: sendFollowUpMode,
          targetScenarioIds: targetScenarioIds ?? undefined,
        },
      ])
    } else if (!options?.skipUserBubble) {
      setMessages((prev) => [
        ...prev,
        {
          id: tempId,
          role: 'user',
          text: q,
          followUpMode: sendFollowUpMode ?? 'new_question',
          targetScenarioIds: targetScenarioIds ?? undefined,
        },
      ])
    }
    setLoading(true)
    setLivePipelineTrace(null)
    setLatestSnapshot(null)
    if (inputRef.current) inputRef.current.style.height = 'auto'

    try {
      let result: DatamartResponse
      try {
        result = await streamDatamartChat(
          {
            question: q,
            session_id: activeSessionId,
            edit_from_turn_index: isEditResend ? editTurnIndex : undefined,
            follow_up_mode: sendFollowUpMode,
            target_scenario_ids: targetScenarioIds,
            confirmed_tables: options?.confirmedTables ?? null,
          },
          {
            onPipeline: (trace) => setLivePipelineTrace(trace),
          },
        )
      } catch (streamErr) {
        console.warn('[datamart] stream failed, falling back to /chat', streamErr)
        setLivePipelineTrace(null)
        result = await datamartService.chat({
          question: q,
          session_id: activeSessionId,
          edit_from_turn_index: isEditResend ? editTurnIndex : undefined,
          follow_up_mode: sendFollowUpMode,
          target_scenario_ids: targetScenarioIds,
          confirmed_tables: options?.confirmedTables ?? null,
        })
      }
      if (result.session_id && result.session_id !== activeSessionId) {
        setActiveSessionId(result.session_id)
        queryClient.invalidateQueries({ queryKey: ['datamart-sessions'] })
      }
      const turnIdx = result.turn_index ?? editTurnIndex
      setMessages((prev) => {
        const withUserTurn = prev.map((m) =>
          m.id === tempId && turnIdx != null ? { ...m, turnIndex: turnIdx } : m,
        )
        return [
          ...withUserTurn,
          {
            id: result.message_id ?? `resp-${Date.now()}`,
            role: 'assistant' as const,
            data: result,
            messageId: result.message_id ?? undefined,
            sessionId: result.session_id ?? undefined,
            turnIndex: turnIdx,
            hydrateResults: true,
          },
        ]
      })

      if (sendFollowUpMode === 'add_scenario') {
        setFollowUpMode('continue_last')
      }

      setHideEditingPill(false)
      setPipelineFinishing(true)
      await new Promise((resolve) => window.setTimeout(resolve, 480))
      setLoading(false)
      setPipelineFinishing(false)

      const sid = result.session_id ?? activeSessionId
      if (sid) {
        void (async () => {
          try {
            const resp = await datamartService.getSessionMessages(sid, 1, PAGE_SIZE)
            if (isEditResend) {
              setMessages(historyToChat(resp.messages, sid))
              setCurrentPage(1)
              setHasMorePages(resp.has_more)
            } else {
              setMessages((prev) => {
                let merged = mergeAssistantMessagesFromApi(prev, resp.messages)
                if (result.message_id && result.extra_result_blocks?.length) {
                  merged = merged.map((m) => {
                    if (m.messageId !== result.message_id || !m.data) return m
                    return {
                      ...m,
                      data: {
                        ...m.data,
                        ...result,
                        chart_configs: m.data.chart_configs ?? result.chart_configs,
                      },
                      hydrateResults: m.hydrateResults,
                    }
                  })
                }
                return merged
              })
            }
          } catch {
            /* keep in-memory result if background refresh fails */
          }
        })()
      }
    } catch (err: unknown) {
      let message = getErrorMessage(err)
      if (axios.isAxiosError(err) && err.code === 'ECONNABORTED') {
        message =
          'This request timed out (the AI or database took too long). Try a shorter question or check the backend and warehouse are healthy.'
      }
      setMessages((prev) => [...prev, { id: `err-${Date.now()}`, role: 'assistant', error: message }])
    } finally {
      setLoading(false)
      setPipelineFinishing(false)
      setLivePipelineTrace(null)
      setTimeout(() => inputRef.current?.focus(), 100)
    }
  }, [
    loading,
    activeSessionId,
    followUpMode,
    awaitingClarification,
    latestAssistantTurn,
    messages,
    turnContext,
    modifyTargetIds,
    toast,
    queryClient,
  ])

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    if (composerHint) setComposerHint(null)
    setInput(e.target.value)
    e.target.style.height = 'auto'
    e.target.style.height = Math.min(e.target.scrollHeight, 200) + 'px'
  }

  const retryFailedTurn = useCallback(
    (failedMessageId: string, opts?: { removePersistedAssistant?: boolean }) => {
      if (loading) return
      const ctx =
        buildRetryContextFromMessages(messages, failedMessageId) ??
        lastSendContextRef.current
      if (!ctx?.question.trim()) return

      if (ctx.followUpMode) setFollowUpMode(ctx.followUpMode)
      if (ctx.targetScenarioIds?.length) setModifyTargetIds(ctx.targetScenarioIds)

      let prepared = messagesAfterRemovingFailedTurn(messages, failedMessageId, {
        removePersistedAssistantWithError: opts?.removePersistedAssistant,
      })
      const replacePersistedTurn =
        ctx.editFromTurnIndex != null && !!activeSessionId
      if (replacePersistedTurn) {
        prepared = truncateMessagesFromTurn(prepared, ctx.editFromTurnIndex!)
      }
      setMessages(prepared)

      if (replacePersistedTurn) {
        void send(ctx.question, {
          editFromTurnIndex: ctx.editFromTurnIndex,
          followUpMode: ctx.followUpMode,
          targetScenarioIds: ctx.targetScenarioIds,
          skipUserBubble: false,
          skipTurnTruncate: true,
          skipGroundingConfirm: true,
          isRetry: true,
        })
        return
      }

      void send(ctx.question, {
        skipUserBubble: true,
        followUpMode: ctx.followUpMode,
        targetScenarioIds: ctx.targetScenarioIds,
        skipGroundingConfirm: true,
        isRetry: true,
      })
    },
    [activeSessionId, loading, messages, send],
  )

  const handleRetryErrorBubble = useCallback(
    (failedMessageId: string) => {
      retryFailedTurn(failedMessageId)
    },
    [retryFailedTurn],
  )

  const handleResendTurn = useCallback(
    (assistantMessageId: string) => {
      retryFailedTurn(assistantMessageId, { removePersistedAssistant: true })
    },
    [retryFailedTurn],
  )

  const handleQuickActionFollowUp = useCallback(
    (prompt: string) => {
      void send(prompt, { followUpMode: 'continue_last' })
    },
    [send],
  )

  const handleOpenLatestChart = useCallback(() => {
    latestChartActionsRef.current?.openChartModal()
  }, [])

  const handleFollowUpModeChange = useCallback((mode: DatamartFollowUpMode) => {
    setFollowUpMode(mode)
    if (mode === 'add_scenario') {
      setComposerHint(
        'Add scenario — describe the new analysis; the previous table stays in this report.',
      )
    } else if (composerHint?.startsWith('Add scenario')) {
      setComposerHint(null)
    }
    requestAnimationFrame(() => inputRef.current?.focus())
  }, [composerHint])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (
        showFollowUpMode &&
        e.altKey &&
        !e.ctrlKey &&
        !e.metaKey &&
        !e.shiftKey
      ) {
        if (e.key === '1') {
          e.preventDefault()
          handleFollowUpModeChange('continue_last')
          return
        }
        if (e.key === '2') {
          e.preventDefault()
          handleFollowUpModeChange('add_scenario')
          return
        }
        if (e.key === '3') {
          e.preventDefault()
          handleFollowUpModeChange('new_question')
          return
        }
      }
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        void send(input)
      }
    },
    [handleFollowUpModeChange, input, send, showFollowUpMode],
  )

  const handleUndoLastModification = useCallback(async () => {
    if (!activeSessionId || undoingModification || loading) return
    setUndoingModification(true)
    try {
      await datamartService.undoLastModification(activeSessionId)
      const resp = await datamartService.getSessionMessages(activeSessionId, 1, PAGE_SIZE)
      setMessages(historyToChat(resp.messages, activeSessionId))
      setCurrentPage(1)
      setHasMorePages(resp.has_more)
      setLatestSnapshot(null)
      setHideEditingPill(false)
      toast.success('Undone', 'Restored the previous version of this result.')
    } catch (err: unknown) {
      toast.error('Undo failed', getErrorMessage(err))
    } finally {
      setUndoingModification(false)
    }
  }, [activeSessionId, loading, toast, undoingModification])

  return (
    <div
      className="datamart-chat-page"
      data-testid="datamart-chat-root"
      data-session-id={activeSessionId ?? ''}
    >
    <DatamartWorkspaceShell
      fillHeight
      sidebar={<DatamartSidebar {...sidebar} />}
      main={
        <div className="datamart-chat-main">
            <DatamartChatHeader
              bootstrap={bootstrapMeta}
              isLoading={bootstrapLoading}
              isError={bootstrapError}
              onRefresh={refreshBootstrapMetadata}
              isRefreshing={fullSyncActive || bootstrapRefreshing}
              onOpenSidebar={onOpenSidebar}
            />

            <div className="datamart-chat-body">
            {fullSyncActive && <DatamartSyncProgress steps={syncSteps} />}
            {loadingHistory && (
              <div className="dm-chat-loading">
                {[0, 1, 2].map((i) => (
                  <div
                    key={i}
                    className="dm-chat-loading__dot"
                    style={{ animationDelay: `${i * 0.2}s` }}
                  />
                ))}
              </div>
            )}

            {!loadingHistory && messages.length === 0 && !loading && (
              <div className="datamart-empty-state">
                <div className="dm-hero-icon">
                  <Database size={32} color="white" />
                </div>
                <h1 className="dm-hero-title">What would you like to explore?</h1>
                <p className="dm-hero-sub">
                  Ask about headcount, payroll, attendance, or leave — the assistant writes SQL
                  against your tenant warehouse and builds reports for you.
                </p>
                {suggestions.length > 0 && (
                  <div className="datamart-suggestions-grid">
                    {suggestions.map((q, i) => (
                      <button
                        key={q}
                        type="button"
                        className="dm-suggestion-card"
                        style={{ animationDelay: `${i * 0.06}s` }}
                        onClick={() => send(q)}
                      >
                        <MessageCircle size={16} className="dm-suggestion-card__icon" />
                        <span>{q}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}

            {!loadingHistory && (messages.length > 0 || loading) && (
              <div
                ref={chatAreaRef}
                className="datamart-chat-scroll"
              >
                {hasMorePages && (
                  <div style={{ display: 'flex', justifyContent: 'center', padding: '12px 20px', flexShrink: 0 }}>
                    <button
                      type="button"
                      className="dm-load-older"
                      onClick={loadOlderMessages}
                      disabled={loadingOlder}
                    >
                      {loadingOlder ? (
                        <Loader2 size={13} style={{ animation: 'spin 1s linear infinite' }} />
                      ) : (
                        <ChevronUp size={13} />
                      )}
                      {loadingOlder ? 'Loading…' : 'Load older messages'}
                    </button>
                  </div>
                )}

                <div className="datamart-chat-thread">
                {messages.map((msg) => {
                  const isLatestAssistant =
                    msg.role === 'assistant' &&
                    !!msg.data &&
                    latestAssistantTurn?.id === msg.id

                  return (
                  <div key={msg.id}>
                    {msg.role === 'user' && msg.text && (
                      <DatamartUserMessage
                        text={msg.text}
                        canEdit={
                          !!activeSessionId &&
                          msg.turnIndex != null &&
                          (editingTurn == null || editingTurn.turnIndex === msg.turnIndex)
                        }
                        disabled={loading}
                        isEditing={
                          editingTurn != null &&
                          msg.turnIndex != null &&
                          editingTurn.turnIndex === msg.turnIndex
                        }
                        editDraft={
                          editingTurn != null &&
                          msg.turnIndex != null &&
                          editingTurn.turnIndex === msg.turnIndex
                            ? editingTurn.draft
                            : msg.text
                        }
                        avatar={<UserAvatar />}
                        onEditDraftChange={(draft) =>
                          setEditingTurn((prev) =>
                            prev && prev.turnIndex === msg.turnIndex ? { ...prev, draft } : prev,
                          )
                        }
                        onCopy={() => {
                          void navigator.clipboard.writeText(msg.text ?? '')
                          toast.success('Copied', 'Message copied to clipboard.')
                        }}
                        onStartEdit={() => startEditTurn(msg.turnIndex!, msg.text!)}
                        onCancelEdit={cancelEditTurn}
                        onSubmitEdit={(q) =>
                          void send(q, { editFromTurnIndex: msg.turnIndex! })
                        }
                      />
                    )}
                    {msg.role === 'assistant' && msg.data && (
                      <div className="dm-turn-row">
                        <AgentAvatar />
                        <div style={{ flex:1, minWidth:0, width:'100%' }}>
                          <DatamartMessage
                            data={msg.data}
                            messageId={msg.messageId}
                            sessionId={msg.sessionId}
                            hydrateResultsFromApi={msg.hydrateResults === true}
                            isLatestTurn={isLatestAssistant}
                            onPromotedToTemplate={(id, _templateName) => {
                              void queryClient.invalidateQueries({ queryKey: ['datamart-templates'] })
                              navigateToTemplate(
                                navigate,
                                queryClient,
                                id,
                                typeof window !== 'undefined'
                                  ? window.location.search
                                  : '',
                              )
                            }}
                            onChartConfigsChange={handleChartConfigsChange}
                            onAskAgent={handleAskAgent}
                            onReportSnapshot={isLatestAssistant ? setLatestSnapshot : undefined}
                            onRegisterChartActions={
                              isLatestAssistant
                                ? (actions) => { latestChartActionsRef.current = actions }
                                : undefined
                            }
                            canUndoModification={
                              isLatestAssistant && undoInfo.canUndo
                            }
                            undoingModification={undoingModification}
                            onUndoModification={
                              isLatestAssistant ? handleUndoLastModification : undefined
                            }
                            onRetryTurn={
                              canRetryFailedAssistant(
                                msg,
                                messages,
                                latestAssistantTurn?.id,
                              ) || isLatestAssistant
                                ? () => handleResendTurn(msg.id)
                                : undefined
                            }
                          />
                        </div>
                      </div>
                    )}
                    {msg.role === 'assistant' && msg.error && (
                      <div className="dm-turn-row" style={{ maxWidth: 760 }}>
                        <AgentAvatar />
                        <DatamartErrorTurn
                          message={msg.error}
                          onRetry={() => handleRetryErrorBubble(msg.id)}
                          retryDisabled={loading}
                        />
                      </div>
                    )}
                  </div>
                  )
                })}

                {(loading || pipelineFinishing) && (
                  <div className="dm-turn-row" style={{ maxWidth: 760 }}>
                    <AgentAvatar />
                    <DatamartLoadingTurn
                      stage={loadingStage}
                      finishing={pipelineFinishing}
                      liveTrace={livePipelineTrace}
                    />
                  </div>
                )}
                <div ref={bottomRef} className="datamart-chat-scroll-anchor" />
                </div>
              </div>
            )}
            </div>

            {!loadingHistory && (
              <DatamartComposer
                input={input}
                composerHint={composerHint}
                editingContext={editingTurn ? null : editingContext}
                toolbarContext={editingTurn ? null : turnContext}
                showFollowUpMode={showFollowUpMode}
                awaitingClarification={awaitingClarification}
                clarificationAnchor={clarificationAnchor}
                followUpMode={followUpMode}
                onFollowUpModeChange={handleFollowUpModeChange}
                loading={loading}
                loadingHistory={loadingHistory}
                inputRef={inputRef}
                onInputChange={handleInput}
                onKeyDown={handleKeyDown}
                onSubmit={() => send(input)}
                onDismissHint={() => {
                  setComposerHint(null)
                  setInput('')
                  if (inputRef.current) inputRef.current.style.height = 'auto'
                }}
                onDismissEditingContext={() => setHideEditingPill(true)}
                modifyTargetIds={modifyTargetIds}
                onModifyTargetIdsChange={setModifyTargetIds}
                showQuickActions={showQuickActions}
                onSendFollowUp={handleQuickActionFollowUp}
                onAddChart={handleOpenLatestChart}
              />
            )}
        </div>
      }
    />
      <DatamartGroundingConfirm
        open={groundingPending != null}
        preview={groundingPending?.preview ?? null}
        loading={loading}
        onCancel={() => setGroundingPending(null)}
        onConfirm={(tables) => {
          const pending = groundingPending
          setGroundingPending(null)
          if (!pending) return
          void send(pending.question, {
            ...pending.sendOptions,
            confirmedTables: tables,
            skipGroundingConfirm: true,
          })
        }}
      />
    </div>
  )
}
