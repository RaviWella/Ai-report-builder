/**
 * Query section: view / edit SQL, run stored or edited SQL, ask agent to change.
 */
import React, { useState } from 'react'
import {
  Copy,
  Loader2,
  MessageSquare,
  Pencil,
  Play,
  RotateCcw,
  Eye,
} from 'lucide-react'
import { dmColors, dmFont, dmRadius, dmSpace } from '../../lib/tokens'

export interface DatamartSqlSectionProps {
  storedSql: string
  draftSql: string
  isDirty: boolean
  running: boolean
  canExecute: boolean
  /** True when the last successful run used the draft editor SQL. */
  lastRunUsedDraft: boolean
  onDraftChange: (sql: string) => void
  onResetDraft: () => void
  onRunStored: () => void
  onRunDraft: () => void
  onAskAgent?: (instruction: string) => void
}

type EditorMode = 'view' | 'edit'

const actionBtn: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 5,
  fontSize: 11,
  fontWeight: 600,
  borderRadius: dmRadius.sm,
  padding: '5px 10px',
  cursor: 'pointer',
  border: `1px solid ${dmColors.border}`,
  background: dmColors.surface,
  color: dmColors.textMuted,
}

const DatamartSqlSection: React.FC<DatamartSqlSectionProps> = ({
  storedSql,
  draftSql,
  isDirty,
  running,
  canExecute,
  lastRunUsedDraft,
  onDraftChange,
  onResetDraft,
  onRunStored,
  onRunDraft,
  onAskAgent,
}) => {
  const [mode, setMode] = useState<EditorMode>('view')
  const [copied, setCopied] = useState(false)
  const [agentNote, setAgentNote] = useState('')
  const [showAgentForm, setShowAgentForm] = useState(false)

  const displaySql = mode === 'edit' ? draftSql : storedSql

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(displaySql)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      /* ignore */
    }
  }

  const submitAgent = () => {
    if (!onAskAgent) return
    onAskAgent(agentNote)
    setAgentNote('')
    setShowAgentForm(false)
  }

  return (
    <div>
      {isDirty && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            marginBottom: dmSpace.md,
            padding: '8px 10px',
            borderRadius: dmRadius.sm,
            background: '#fffbeb',
            border: '1px solid #fde68a',
            fontSize: 12,
            color: '#b45309',
          }}
        >
          <Pencil size={13} aria-hidden />
          <span>
            Edited locally — not saved to the conversation.
            {lastRunUsedDraft ? ' Last run used your edited SQL.' : ''}
          </span>
        </div>
      )}

      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 8,
          marginBottom: dmSpace.md,
          alignItems: 'center',
        }}
      >
        <div
          style={{
            display: 'inline-flex',
            borderRadius: dmRadius.sm,
            border: `1px solid ${dmColors.border}`,
            overflow: 'hidden',
          }}
        >
          <button
            type="button"
            onClick={() => setMode('view')}
            style={{
              ...actionBtn,
              border: 'none',
              borderRadius: 0,
              background: mode === 'view' ? dmColors.brandMuted : dmColors.surface,
              color: mode === 'view' ? dmColors.brand : dmColors.textMuted,
            }}
          >
            <Eye size={12} />
            Stored
          </button>
          <button
            type="button"
            onClick={() => setMode('edit')}
            style={{
              ...actionBtn,
              border: 'none',
              borderRadius: 0,
              background: mode === 'edit' ? dmColors.brandMuted : dmColors.surface,
              color: mode === 'edit' ? dmColors.brand : dmColors.textMuted,
            }}
          >
            <Pencil size={12} />
            Edit
          </button>
        </div>

        <button type="button" onClick={() => void handleCopy()} style={actionBtn}>
          <Copy size={12} />
          {copied ? 'Copied' : 'Copy'}
        </button>

        {canExecute && (
          <button
            type="button"
            disabled={running}
            onClick={onRunStored}
            style={{
              ...actionBtn,
              color: dmColors.brand,
              borderColor: dmColors.brandBorder,
              background: dmColors.brandMuted,
              opacity: running ? 0.6 : 1,
            }}
          >
            {running && !isDirty ? (
              <Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} />
            ) : (
              <Play size={12} />
            )}
            Run stored SQL
          </button>
        )}

        {canExecute && isDirty && (
          <button
            type="button"
            disabled={running}
            onClick={onRunDraft}
            style={{
              ...actionBtn,
              color: '#1d4ed8',
              borderColor: '#93c5fd',
              background: '#eff6ff',
              opacity: running ? 0.6 : 1,
            }}
          >
            {running ? (
              <Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} />
            ) : (
              <Play size={12} />
            )}
            Run edited SQL
          </button>
        )}

        {isDirty && (
          <button type="button" onClick={onResetDraft} disabled={running} style={actionBtn}>
            <RotateCcw size={12} />
            Reset
          </button>
        )}

        {onAskAgent && (
          <button
            type="button"
            onClick={() => setShowAgentForm((v) => !v)}
            style={{
              ...actionBtn,
              marginLeft: 'auto',
              color: dmColors.purple,
              borderColor: dmColors.purpleBorder,
              background: dmColors.purpleBg,
            }}
          >
            <MessageSquare size={12} />
            Ask assistant
          </button>
        )}
      </div>

      {showAgentForm && onAskAgent && (
        <div
          style={{
            marginBottom: dmSpace.md,
            padding: dmSpace.md,
            borderRadius: dmRadius.md,
            border: `1px solid ${dmColors.purpleBorder}`,
            background: dmColors.purpleBg,
          }}
        >
          <p style={{ margin: '0 0 8px', fontSize: 12, color: dmColors.text, lineHeight: 1.5 }}>
            Describe the change. A new assistant reply will update the stored SQL (audited in chat
            history).
          </p>
          <textarea
            value={agentNote}
            onChange={(e) => setAgentNote(e.target.value)}
            placeholder="e.g. Remove the leave_days column and keep the same joins"
            rows={2}
            style={{
              width: '100%',
              boxSizing: 'border-box',
              fontSize: 13,
              fontFamily: 'inherit',
              border: `1px solid ${dmColors.purpleBorder}`,
              borderRadius: dmRadius.sm,
              padding: '8px 10px',
              resize: 'vertical',
              marginBottom: 8,
            }}
          />
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              type="button"
              onClick={submitAgent}
              disabled={!agentNote.trim()}
              style={{
                ...actionBtn,
                color: '#fff',
                background: dmColors.purple,
                borderColor: dmColors.purple,
              }}
            >
              Send to assistant
            </button>
            <button
              type="button"
              onClick={() => {
                setShowAgentForm(false)
                setAgentNote('')
              }}
              style={actionBtn}
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {mode === 'edit' ? (
        <textarea
          value={draftSql}
          onChange={(e) => onDraftChange(e.target.value)}
          spellCheck={false}
          style={{
            width: '100%',
            minHeight: 200,
            boxSizing: 'border-box',
            margin: 0,
            fontSize: 12,
            lineHeight: 1.6,
            fontFamily: dmFont.mono,
            color: dmColors.sqlText,
            background: dmColors.sqlBg,
            border: `1px solid ${dmColors.border}`,
            borderRadius: dmRadius.md,
            padding: '14px 16px',
            resize: 'vertical',
          }}
        />
      ) : (
        <pre
          style={{
            margin: 0,
            fontSize: 12,
            color: dmColors.sqlText,
            fontFamily: dmFont.mono,
            lineHeight: 1.6,
            whiteSpace: 'pre',
            background: dmColors.sqlBg,
            borderRadius: dmRadius.md,
            padding: '14px 16px',
            overflowX: 'auto',
          }}
        >
          {storedSql}
        </pre>
      )}
    </div>
  )
}

export default DatamartSqlSection
