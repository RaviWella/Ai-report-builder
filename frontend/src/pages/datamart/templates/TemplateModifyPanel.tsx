/**
 * Left panel: template modification chat + save new version.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Save } from 'lucide-react'
import type { DatamartResponse } from '../../../services/datamartService'
import { datamartService } from '../../../services/datamartService'
import { getErrorMessage } from '../../../services/api'
import { useToast } from '../../../components/ui/Toast'
import { formatApiError } from '../lib/formatApiError'
import { stripExecutedRows } from '../lib/stripExecutedRows'
import { extraBlocksToSavePayload } from './versionToReport'
import type { LatestTurnContext } from '../lib/latestTurnContext'
import type { DatamartFollowUpMode } from '../lib/followUpMode'
import {
  buildModifyScenarioContextKey,
  buildTargetScenarioPayload,
  defaultModifyTargetIds,
} from '../lib/modifyScenarioTargets'
import {
  buildRetryContextFromMessages,
  messagesAfterRemovingFailedTurn,
  type RetrySendContext,
} from '../lib/chatRetry'
import DatamartComposer from '../chat/DatamartComposer'
import DatamartErrorTurn from '../chat/DatamartErrorTurn'
import DatamartLoadingTurn from '../chat/DatamartLoadingTurn'
import TemplateModifyAssistantTurn from './TemplateModifyAssistantTurn'
import { useChatLoadingStage } from '../hooks/useChatLoadingStage'
import { dmColors, dmRadius, dmSpace } from '../lib/tokens'

interface ModifyMessage {
  id: string
  role: 'user' | 'assistant'
  text?: string
  data?: DatamartResponse
  error?: string
  followUpMode?: DatamartFollowUpMode
  targetScenarioIds?: string[]
}

export interface TemplateModifyPanelProps {
  templateId: string
  versionId: string
  chartConfigsForSave: unknown[]
  pendingDraft: DatamartResponse | null
  editingContext: LatestTurnContext | null
  composerPrefill?: string | null
  onDismissComposerPrefill?: () => void
  onVersionSaved: () => void
  onPendingResult: (data: DatamartResponse | null) => void
  onAddChart?: () => void
}

const TemplateModifyPanel: React.FC<TemplateModifyPanelProps> = ({
  templateId,
  versionId,
  chartConfigsForSave,
  pendingDraft,
  editingContext,
  composerPrefill,
  onDismissComposerPrefill,
  onVersionSaved,
  onPendingResult,
}) => {
  const toast = useToast()
  const [input, setInput] = useState('')
  const [composerHint, setComposerHint] = useState<string | null>(null)
  const [followUpMode, setFollowUpMode] = useState<DatamartFollowUpMode>('continue_last')
  const [modifyTargetIds, setModifyTargetIds] = useState<string[]>([])
  const [messages, setMessages] = useState<ModifyMessage[]>([])
  const [loading, setLoading] = useState(false)
  const [saveLabel, setSaveLabel] = useState('')
  const [saving, setSaving] = useState(false)
  const [showSaveForm, setShowSaveForm] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const lastSendContextRef = useRef<RetrySendContext | null>(null)
  const loadingStage = useChatLoadingStage(loading)

  useEffect(() => {
    setMessages([])
    setInput('')
    setComposerHint(null)
    setFollowUpMode('continue_last')
    setModifyTargetIds([])
    setShowSaveForm(false)
  }, [templateId, versionId])

  const modifyContextKey = useMemo(
    () => buildModifyScenarioContextKey(versionId, editingContext?.scenarios),
    [versionId, editingContext?.scenarios?.map((s) => s.panelId).join('|'), editingContext?.multiScenario],
  )

  useEffect(() => {
    if (!editingContext?.multiScenario) {
      setModifyTargetIds([])
      return
    }
    setModifyTargetIds(defaultModifyTargetIds(editingContext.scenarios))
    // eslint-disable-next-line react-hooks/exhaustive-deps -- modifyContextKey encodes scenario set
  }, [modifyContextKey])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  useEffect(() => {
    if (!composerPrefill?.trim()) return
    setInput(composerPrefill)
    setComposerHint('SQL change — review the message below, then send')
    requestAnimationFrame(() => {
      const el = inputRef.current
      if (!el) return
      el.focus()
      el.style.height = 'auto'
      el.style.height = `${Math.min(el.scrollHeight, 200)}px`
    })
  }, [composerPrefill])

  const submit = useCallback(
    async (
      question: string,
      options?: {
        skipUserBubble?: boolean
        followUpMode?: DatamartFollowUpMode
        targetScenarioIds?: string[]
        isRetry?: boolean
      },
    ) => {
      const q = question.trim()
      if (!q || loading) return
      const modeForRequest = options?.followUpMode ?? followUpMode
      const targetScenarioIds =
        options?.targetScenarioIds ??
        buildTargetScenarioPayload(
          !!editingContext?.multiScenario,
          modeForRequest,
          modifyTargetIds,
        )
      if (
        modeForRequest === 'continue_last' &&
        editingContext?.multiScenario &&
        !targetScenarioIds?.length
      ) {
        toast.error('Select scenarios', 'Choose at least one scenario to modify.')
        return
      }
      lastSendContextRef.current = {
        question: q,
        followUpMode: modeForRequest ?? 'continue_last',
        targetScenarioIds: targetScenarioIds ?? undefined,
      }
      if (!options?.skipUserBubble) {
        setMessages((prev) => [
          ...prev,
          {
            id: `u-${Date.now()}`,
            role: 'user',
            text: q,
            followUpMode: modeForRequest,
            targetScenarioIds: targetScenarioIds ?? undefined,
          },
        ])
      }
      setInput('')
      setComposerHint(null)
      if (inputRef.current) inputRef.current.style.height = 'auto'
      setLoading(true)
      try {
        const templateFollowUp =
          modeForRequest === 'continue_last' ||
          modeForRequest === 'add_scenario' ||
          modeForRequest === 'new_question'
            ? modeForRequest
            : undefined
        const result = stripExecutedRows(
          await datamartService.templateChat(
            templateId,
            q,
            templateFollowUp,
            targetScenarioIds,
          ),
        )
        setMessages((prev) => [...prev, { id: `a-${Date.now()}`, role: 'assistant', data: result }])
        if (modeForRequest === 'add_scenario' && pendingDraft) {
          const prevExtras = pendingDraft.extra_result_blocks ?? []
          const newExtras = result.extra_result_blocks ?? []
          const byId = new Map(prevExtras.map((b) => [b.block_id, b]))
          for (const blk of newExtras) {
            byId.set(blk.block_id, blk)
          }
          onPendingResult({
            ...pendingDraft,
            narrative: result.narrative?.trim()
              ? `${pendingDraft.narrative ?? ''}\n\n**Added scenario:** ${result.narrative}`.trim()
              : pendingDraft.narrative,
            extra_result_blocks: [...byId.values()],
          })
          setFollowUpMode('continue_last')
        } else if (result.sql || (result.extra_result_blocks?.length ?? 0) > 0) {
          onPendingResult(result)
        }
      } catch (err: unknown) {
        const msg = getErrorMessage(err) || 'Something went wrong.'
        setMessages((prev) => [...prev, { id: `e-${Date.now()}`, role: 'assistant', error: msg }])
      } finally {
        setLoading(false)
      }
    },
    [
      editingContext,
      followUpMode,
      loading,
      modifyTargetIds,
      onPendingResult,
      pendingDraft,
      templateId,
      toast,
    ],
  )

  const retryFailedTurn = useCallback(
    (failedMessageId: string, opts?: { removePersistedAssistant?: boolean }) => {
      if (loading) return
      const ctx =
        buildRetryContextFromMessages(messages, failedMessageId) ??
        lastSendContextRef.current
      if (!ctx?.question.trim()) return

      if (ctx.followUpMode) setFollowUpMode(ctx.followUpMode)
      if (ctx.targetScenarioIds?.length) setModifyTargetIds(ctx.targetScenarioIds)

      setMessages((prev) =>
        messagesAfterRemovingFailedTurn(prev, failedMessageId, {
          removePersistedAssistantWithError: opts?.removePersistedAssistant,
        }),
      )

      void submit(ctx.question, {
        skipUserBubble: true,
        followUpMode: ctx.followUpMode,
        targetScenarioIds: ctx.targetScenarioIds,
        isRetry: true,
      })
    },
    [loading, messages, submit],
  )

  const handleInput = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    if (composerHint) setComposerHint(null)
    setInput(e.target.value)
    e.target.style.height = 'auto'
    e.target.style.height = `${Math.min(e.target.scrollHeight, 200)}px`
  }, [composerHint])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        void submit(input)
      }
    },
    [input, submit],
  )

  const saveVersion = async () => {
    const dataToSave = pendingDraft
    if (!dataToSave?.sql?.trim()) {
      toast.error('Nothing to save', 'Run a modification that returns SQL first.')
      return
    }
    setSaving(true)
    try {
      await datamartService.saveTemplateVersion(templateId, {
        sql_script: dataToSave.sql.trim(),
        post_process_config: dataToSave.post_process_config ?? null,
        chart_configs: chartConfigsForSave.length
          ? chartConfigsForSave
          : dataToSave.chart_configs ?? null,
        extra_result_blocks: extraBlocksToSavePayload(dataToSave.extra_result_blocks),
        report_layout: dataToSave.report_layout ?? null,
        narrative: dataToSave.narrative ?? null,
        label: saveLabel.trim() || null,
      })
      toast.success('Version saved', saveLabel.trim() || 'New template version created')
      setShowSaveForm(false)
      setSaveLabel('')
      onPendingResult(null)
      onVersionSaved()
    } catch (err: unknown) {
      toast.error('Save failed', formatApiError(err, 'Could not save template version.'))
    } finally {
      setSaving(false)
    }
  }

  const showFollowUpMode = !!editingContext

  return (
    <div
      className="template-modify-panel"
      style={{
        display: 'flex',
        flexDirection: 'column',
        minWidth: 0,
        width: '100%',
        maxWidth: 420,
        borderRight: `1px solid ${dmColors.border}`,
        background: dmColors.surface,
      }}
    >
      <div
        style={{
          padding: `${dmSpace.md}px ${dmSpace.lg}px`,
          borderBottom: `1px solid ${dmColors.borderLight}`,
          flexShrink: 0,
        }}
      >
        <p style={{ margin: 0, fontSize: 12, fontWeight: 700, color: dmColors.textMuted, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Modify template
        </p>
        <p style={{ margin: `${dmSpace.xs}px 0 0`, fontSize: 12, color: dmColors.textSubtle, lineHeight: 1.45 }}>
          Chat changes preview on the right; save when ready.
        </p>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: dmSpace.lg, minHeight: 0 }}>
        {messages.length === 0 && !loading && (
          <p style={{ fontSize: 13, color: dmColors.textMuted, lineHeight: 1.55, margin: 0 }}>
            Ask for changes to this template&apos;s SQL, scenarios, or report layout. Use Modify, Scenario, or Free
            in the composer below — same as datamart chat.
          </p>
        )}
        {messages.map((msg) => (
          <div key={msg.id} style={{ marginBottom: dmSpace.md }}>
            {msg.role === 'user' && (
              <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                <div
                  className="dm-user-bubble"
                  style={{
                    maxWidth: '92%',
                    borderRadius: '14px 14px 4px 14px',
                    padding: '10px 12px',
                    fontSize: 13,
                    lineHeight: 1.55,
                  }}
                >
                  {msg.text}
                </div>
              </div>
            )}
            {msg.role === 'assistant' && msg.data && (
              <TemplateModifyAssistantTurn
                data={msg.data}
                onRetry={
                  msg.data.error
                    ? () => retryFailedTurn(msg.id, { removePersistedAssistant: true })
                    : undefined
                }
                retryDisabled={loading}
              />
            )}
            {msg.role === 'assistant' && msg.error && (
              <DatamartErrorTurn
                message={msg.error}
                onRetry={() => retryFailedTurn(msg.id)}
                retryDisabled={loading}
              />
            )}
          </div>
        ))}
        {loading && <DatamartLoadingTurn stage={loadingStage} />}
        <div ref={bottomRef} />
      </div>

      {pendingDraft && (
        <div
          style={{
            margin: `0 ${dmSpace.lg}px`,
            padding: dmSpace.md,
            borderRadius: dmRadius.md,
            background: dmColors.purpleBg,
            border: `1px solid ${dmColors.purpleBorder}`,
            flexShrink: 0,
          }}
        >
          {!showSaveForm ? (
            <button
              type="button"
              onClick={() => setShowSaveForm(true)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                fontSize: 12,
                fontWeight: 600,
                color: dmColors.purple,
                background: dmColors.surface,
                border: `1px solid ${dmColors.purpleBorder}`,
                borderRadius: dmRadius.sm,
                padding: '8px 12px',
                cursor: 'pointer',
                width: '100%',
                justifyContent: 'center',
              }}
            >
              <Save size={14} />
              Save as new version
            </button>
          ) : (
            <>
              <p style={{ margin: '0 0 8px', fontSize: 12, fontWeight: 600, color: dmColors.purple }}>
                New version label (optional)
              </p>
              <div style={{ display: 'flex', gap: 8 }}>
                <input
                  value={saveLabel}
                  onChange={(e) => setSaveLabel(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') void saveVersion()
                  }}
                  placeholder="e.g. Q2 headcount tweak"
                  style={{
                    flex: 1,
                    fontSize: 13,
                    border: `1px solid ${dmColors.purpleBorder}`,
                    borderRadius: dmRadius.sm,
                    padding: '6px 10px',
                  }}
                />
                <button
                  type="button"
                  onClick={() => void saveVersion()}
                  disabled={saving}
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    color: '#fff',
                    background: dmColors.purple,
                    border: 'none',
                    borderRadius: dmRadius.sm,
                    padding: '6px 12px',
                    cursor: saving ? 'default' : 'pointer',
                  }}
                >
                  {saving ? 'Saving…' : 'Save'}
                </button>
              </div>
            </>
          )}
        </div>
      )}

      <DatamartComposer
        input={input}
        composerHint={composerHint}
        editingContext={editingContext}
        showFollowUpMode={showFollowUpMode}
        followUpMode={followUpMode}
        onFollowUpModeChange={(mode) => {
          setFollowUpMode(mode)
          if (mode === 'add_scenario') {
            setComposerHint(
              'Add scenario — describe the new analysis; the previous table stays in this report.',
            )
          } else if (composerHint?.startsWith('Add scenario')) {
            setComposerHint(null)
          }
          requestAnimationFrame(() => inputRef.current?.focus())
        }}
        toolbarContext={editingContext}
        loading={loading}
        loadingHistory={false}
        inputRef={inputRef}
        onInputChange={handleInput}
        onKeyDown={handleKeyDown}
        onSubmit={() => void submit(input)}
        onDismissHint={() => {
          setComposerHint(null)
          setInput('')
          onDismissComposerPrefill?.()
          if (inputRef.current) inputRef.current.style.height = 'auto'
        }}
        onDismissEditingContext={() => {}}
        modifyTargetIds={modifyTargetIds}
        onModifyTargetIdsChange={setModifyTargetIds}
      />
    </div>
  )
}

export default TemplateModifyPanel
