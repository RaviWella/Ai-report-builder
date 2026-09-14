/**
 * User chat bubble with ChatGPT-style copy / inline edit.
 */
import React, { useEffect, useRef, useCallback, useState } from 'react'
import { Copy, Pencil } from 'lucide-react'
import { dmColors, dmRadius } from '../lib/tokens'

export interface DatamartUserMessageProps {
  text: string
  canEdit: boolean
  disabled?: boolean
  isEditing?: boolean
  editDraft?: string
  avatar?: React.ReactNode
  onEditDraftChange?: (value: string) => void
  onStartEdit: () => void
  onCancelEdit: () => void
  onSubmitEdit: (text: string) => void
  onCopy: () => void
}

const DatamartUserMessage: React.FC<DatamartUserMessageProps> = ({
  text,
  canEdit,
  disabled,
  isEditing = false,
  editDraft = '',
  avatar,
  onEditDraftChange,
  onStartEdit,
  onCancelEdit,
  onSubmitEdit,
  onCopy,
}) => {
  const [hover, setHover] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const resizeTextarea = useCallback(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 280)}px`
  }, [])

  useEffect(() => {
    if (!isEditing) return
    resizeTextarea()
    const el = textareaRef.current
    if (!el) return
    el.focus()
    const len = el.value.length
    el.setSelectionRange(len, len)
  }, [isEditing, resizeTextarea])

  const handleInlineKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      const q = editDraft.trim()
      if (q && !disabled) onSubmitEdit(q)
    }
    if (e.key === 'Escape') {
      e.preventDefault()
      onCancelEdit()
    }
  }

  if (isEditing) {
    const canSend = !!editDraft.trim() && !disabled
    return (
      <div
        style={{
          display: 'flex',
          justifyContent: 'flex-end',
          alignItems: 'flex-start',
          gap: 10,
          maxWidth: 760,
          margin: '0 auto 20px',
          padding: '0 20px',
        }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', width: '100%', maxWidth: 'min(100%, 520px)' }}>
          <div
            style={{
              width: '100%',
              background: dmColors.surface,
              border: `1.5px solid ${dmColors.border}`,
              borderRadius: dmRadius.lg,
              padding: '12px 14px',
              boxShadow: '0 2px 12px rgba(15, 23, 42, 0.08)',
            }}
          >
            <textarea
              ref={textareaRef}
              value={editDraft}
              onChange={(e) => {
                onEditDraftChange?.(e.target.value)
                resizeTextarea()
              }}
              onKeyDown={handleInlineKeyDown}
              disabled={disabled}
              rows={3}
              aria-label="Edit message"
              className="dm-user-edit-textarea"
              style={{
                width: '100%',
                minHeight: 72,
                maxHeight: 280,
                fontSize: 14,
                lineHeight: 1.6,
                color: dmColors.text,
                border: 'none',
                resize: 'none',
                background: 'transparent',
                fontFamily: 'inherit',
                padding: 0,
                boxSizing: 'border-box',
              }}
            />
            <div
              style={{
                display: 'flex',
                justifyContent: 'flex-end',
                gap: 8,
                marginTop: 10,
              }}
            >
              <button
                type="button"
                onClick={onCancelEdit}
                disabled={disabled}
                style={pillBtnStyle(false, disabled)}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => {
                  const q = editDraft.trim()
                  if (q) onSubmitEdit(q)
                }}
                disabled={!canSend}
                style={pillBtnStyle(true, !canSend)}
              >
                Send
              </button>
            </div>
          </div>
          <p style={{ margin: '6px 0 0', fontSize: 11, color: dmColors.textSubtle, textAlign: 'right' }}>
            Resending replaces this reply and any messages after it
          </p>
        </div>
        {avatar}
      </div>
    )
  }

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'flex-end',
        alignItems: 'flex-start',
        gap: 10,
        maxWidth: 760,
        margin: '0 auto 20px',
        padding: '0 20px',
        animation: 'dmFadeRight 0.4s ease-out',
      }}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', maxWidth: '72%' }}>
        <div
          className="dm-user-bubble"
          style={{
            borderRadius: '18px 18px 4px 18px',
            padding: '12px 16px',
          }}
        >
          {text}
        </div>
        {canEdit && (hover || disabled) && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              marginTop: 6,
            }}
          >
            <button
              type="button"
              disabled={disabled}
              onClick={onCopy}
              title="Copy"
              aria-label="Copy message"
              style={actionBtnStyle}
            >
              <Copy size={14} />
            </button>
            <button
              type="button"
              disabled={disabled}
              onClick={onStartEdit}
              title="Edit message"
              aria-label="Edit message"
              style={actionBtnStyle}
            >
              <Pencil size={14} />
            </button>
          </div>
        )}
      </div>
      {avatar}
    </div>
  )
}

function pillBtnStyle(primary: boolean, inactive: boolean | undefined): React.CSSProperties {
  return {
    padding: '6px 14px',
    borderRadius: 999,
    fontSize: 13,
    fontWeight: 600,
    border: primary ? 'none' : `1px solid ${dmColors.border}`,
    background: primary ? (inactive ? '#e2e8f0' : dmColors.brand) : dmColors.surface,
    color: primary ? (inactive ? '#94a3b8' : '#fff') : dmColors.text,
    cursor: inactive ? 'default' : 'pointer',
  }
}

const actionBtnStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: 30,
  height: 30,
  borderRadius: dmRadius.sm,
  border: `1px solid ${dmColors.border}`,
  background: dmColors.surface,
  color: dmColors.textMuted,
  cursor: 'pointer',
  padding: 0,
}

export default DatamartUserMessage
