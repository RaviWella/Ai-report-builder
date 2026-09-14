/**
 * Sticky header row for virtualized tables (must match body column widths).
 */
import React from 'react'
import { formatHeader } from '../lib/tableFormat'

export interface DatamartTableHeaderRowProps {
  columns: string[]
  columnWidths: number[]
  minWidth: number
  sticky?: boolean
}

const DatamartTableHeaderRow: React.FC<DatamartTableHeaderRowProps> = ({
  columns,
  columnWidths,
  minWidth,
  sticky = true,
}) => (
  <div
    role="row"
    style={{
      display: 'flex',
      width: '100%',
      minWidth,
      boxSizing: 'border-box',
      ...(sticky
        ? {
            position: 'sticky',
            top: 0,
            zIndex: 2,
          }
        : {}),
    }}
  >
    {columns.map((col, idx) => (
      <div
        key={col}
        role="columnheader"
        style={{
          width: columnWidths[idx],
          minWidth: columnWidths[idx],
          maxWidth: columnWidths[idx],
          flexShrink: 0,
          boxSizing: 'border-box',
          padding: '9px 14px',
          textAlign: 'left',
          fontWeight: 600,
          fontSize: 11,
          color: '#64748b',
          background: '#f8fafc',
          borderBottom: '2px solid #e2e8f0',
          letterSpacing: '0.04em',
          textTransform: 'uppercase',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
        title={formatHeader(col)}
      >
        {formatHeader(col)}
      </div>
    ))}
  </div>
)

export default DatamartTableHeaderRow
