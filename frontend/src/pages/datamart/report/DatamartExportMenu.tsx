/**
 * Export dropdown: CSV or PDF.
 */
import React, { useEffect, useRef, useState } from 'react'
import { ChevronDown, Download, FileSpreadsheet, FileText, LayoutGrid } from 'lucide-react'
import { dmColors, dmRadius } from '../lib/tokens'
import { dmCopy } from '../lib/copy'

export interface DatamartExportMenuProps {
  disabled?: boolean
  onCustomizeExport?: () => void
  onExportCsv: () => void | Promise<void>
  onExportPdf: () => void | Promise<void>
}

const itemStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  width: '100%',
  padding: '8px 12px',
  fontSize: 12,
  fontWeight: 500,
  color: dmColors.text,
  background: 'transparent',
  border: 'none',
  cursor: 'pointer',
  textAlign: 'left',
}

const DatamartExportMenu: React.FC<DatamartExportMenuProps> = ({
  disabled,
  onCustomizeExport,
  onExportCsv,
  onExportPdf,
}) => {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return undefined
    const onDoc = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [open])

  return (
    <div ref={rootRef} style={{ position: 'relative' }}>
      <button
        type="button"
        disabled={disabled}
        aria-label={dmCopy.toolbar.export}
        aria-expanded={open}
        aria-haspopup="menu"
        data-testid="datamart-export-menu"
        onClick={() => setOpen((v) => !v)}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 5,
          fontSize: 12,
          fontWeight: 500,
          borderRadius: dmRadius.sm,
          padding: '5px 12px',
          color: disabled ? dmColors.textSubtle : dmColors.textMuted,
          background: dmColors.surface,
          border: `1px solid ${dmColors.border}`,
          cursor: disabled ? 'default' : 'pointer',
          opacity: disabled ? 0.6 : 1,
        }}
      >
        <Download size={12} />
        {dmCopy.toolbar.export}
        <ChevronDown size={12} />
      </button>

      {open && !disabled && (
        <div
          role="menu"
          style={{
            position: 'absolute',
            top: 'calc(100% + 4px)',
            right: 0,
            zIndex: 20,
            minWidth: 200,
            background: dmColors.surface,
            border: `1px solid ${dmColors.border}`,
            borderRadius: dmRadius.md,
            boxShadow: '0 8px 24px rgba(15, 23, 42, 0.12)',
            overflow: 'hidden',
          }}
        >
          {onCustomizeExport && (
            <button
              type="button"
              role="menuitem"
              data-testid="datamart-export-customize"
              style={itemStyle}
              onClick={() => {
                onCustomizeExport()
                setOpen(false)
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = dmColors.surfaceMuted
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent'
              }}
            >
              <LayoutGrid size={14} color={dmColors.brand} />
              {dmCopy.exportComposer.customizeExport}
            </button>
          )}
          <button
            type="button"
            role="menuitem"
            data-testid="datamart-export-csv"
            style={itemStyle}
            onClick={() => {
              onExportCsv()
              setOpen(false)
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = dmColors.surfaceMuted
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent'
            }}
          >
            <FileSpreadsheet size={14} color={dmColors.brand} />
            {dmCopy.exportComposer.quickCsv}
          </button>
          <button
            type="button"
            role="menuitem"
            data-testid="datamart-export-pdf"
            style={itemStyle}
            onClick={() => {
              setOpen(false)
              void onExportPdf()
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = dmColors.surfaceMuted
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent'
            }}
          >
            <FileText size={14} color="#dc2626" />
            {dmCopy.exportComposer.quickPdf}
          </button>
        </div>
      )}
    </div>
  )
}

export default DatamartExportMenu
