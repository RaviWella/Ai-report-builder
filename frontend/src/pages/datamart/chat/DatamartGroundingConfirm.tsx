/**
 * Modal to confirm grounded tables before sending a new datamart question.
 */
import React, { useEffect, useMemo, useRef, useState } from 'react'
import type { GroundingPreviewResponse } from '../../../services/datamartService'
import { dmColors, dmRadius } from '../lib/tokens'

export interface DatamartGroundingConfirmProps {
  open: boolean
  preview: GroundingPreviewResponse | null
  loading?: boolean
  onCancel: () => void
  onConfirm: (confirmedTables: string[]) => void
}

const DatamartGroundingConfirm: React.FC<DatamartGroundingConfirmProps> = ({
  open,
  preview,
  loading = false,
  onCancel,
  onConfirm,
}) => {
  const tables = preview?.tables_selected ?? []
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const panelRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (open && tables.length) {
      setSelected(new Set(tables))
    }
  }, [open, preview?.question, tables.join(',')])

  useEffect(() => {
    if (!open) return undefined
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !loading) onCancel()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, loading, onCancel])

  useEffect(() => {
    if (open) {
      const t = window.setTimeout(() => panelRef.current?.focus(), 50)
      return () => window.clearTimeout(t)
    }
    return undefined
  }, [open])

  const status = preview?.retrieval?.status ?? 'sufficient'
  const canProceed = preview?.can_proceed ?? true
  const warnings = preview?.retrieval?.warnings ?? []
  const hints = preview?.retrieval?.clarification_hints ?? []

  const selectedList = useMemo(() => Array.from(selected), [selected])

  if (!open || !preview) return null

  const toggle = (t: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(t)) next.delete(t)
      else next.add(t)
      return next
    })
  }

  return (
    <div
      className="datamart-grounding-overlay"
      role="presentation"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget && !loading) onCancel()
      }}
    >
      <div
        ref={panelRef}
        className="datamart-grounding-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="datamart-grounding-title"
        tabIndex={-1}
        style={{
          background: '#fff',
          borderRadius: dmRadius.lg,
          boxShadow: '0 12px 40px rgba(15,23,42,0.18)',
          maxWidth: 480,
          width: '100%',
          padding: 20,
        }}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <h3 id="datamart-grounding-title" style={{ margin: '0 0 8px', fontSize: 16, fontWeight: 600 }}>
          Confirm data sources
        </h3>
        <p style={{ margin: '0 0 12px', fontSize: 13, color: dmColors.textMuted }}>
          We matched your question to these warehouse tables. Uncheck any you do not want used for SQL generation.
        </p>
        <p style={{ margin: '0 0 12px', fontSize: 12 }}>
          Retrieval: <strong>{status}</strong>
          {!canProceed && (
            <span style={{ color: '#b45309', marginLeft: 8 }}>May need rephrasing</span>
          )}
        </p>
        <ul style={{ listStyle: 'none', margin: '0 0 12px', padding: 0, maxHeight: 200, overflow: 'auto' }}>
          {tables.map((t) => (
            <li key={t} style={{ marginBottom: 6 }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={selected.has(t)}
                  onChange={() => toggle(t)}
                />
                <code>{t}</code>
              </label>
            </li>
          ))}
        </ul>
        {warnings.length > 0 && (
          <ul style={{ fontSize: 12, color: '#b45309', margin: '0 0 8px', paddingLeft: 18 }}>
            {warnings.slice(0, 3).map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        )}
        {hints.length > 0 && (
          <p style={{ fontSize: 12, color: dmColors.textMuted, margin: '0 0 12px' }}>
            {hints[0]}
          </p>
        )}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <button type="button" className="datamart-btn-secondary" onClick={onCancel} disabled={loading}>
            Cancel
          </button>
          <button
            type="button"
            className="datamart-btn-primary"
            disabled={loading || selectedList.length === 0}
            onClick={() => onConfirm(selectedList)}
          >
            {loading ? 'Sending…' : 'Run query'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default DatamartGroundingConfirm
