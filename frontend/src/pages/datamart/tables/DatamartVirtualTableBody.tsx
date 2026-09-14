/**
 * Virtualized table body for large datamart result sets (react-window v2).
 */
import React from 'react'
import { List, type RowComponentProps } from 'react-window'
import {
  TABLE_ROW_HEIGHT,
  formatCell,
  isNumeric,
  normalizeTableRow,
  tableBodyHeight,
} from '../lib/tableFormat'

export interface VirtualTableRowProps {
  rows: unknown[][]
  columns: string[]
  columnWidths: number[]
  minWidth: number
}

function VirtualTableRow({
  index,
  style,
  rows,
  columns,
  columnWidths,
  minWidth,
  ariaAttributes,
}: RowComponentProps<VirtualTableRowProps>) {
  const row = normalizeTableRow(rows[index], columns.length)
  const isEven = index % 2 === 0
  const baseBg = isEven ? '#ffffff' : '#f8fafc'

  return (
    <div
      {...ariaAttributes}
      style={{
        ...style,
        display: 'flex',
        width: '100%',
        minWidth,
        boxSizing: 'border-box',
      }}
    >
      {row.map((cell, cellIdx) => {
        const display = formatCell(cell)
        const numeric = isNumeric(cell)
        const isNull = cell === null || cell === undefined
        const width = columnWidths[cellIdx] ?? 140

        return (
          <div
            key={cellIdx}
            role="cell"
            title={!isNull && display !== '—' ? display : undefined}
            style={{
              width,
              minWidth: width,
              maxWidth: width,
              flexShrink: 0,
              boxSizing: 'border-box',
              padding: '9px 14px',
              borderBottom: '1px solid #f1f5f9',
              background: baseBg,
              color: isNull ? '#cbd5e1' : '#334155',
              textAlign: numeric ? 'right' : 'left',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              fontSize: 13,
              fontVariantNumeric: numeric ? 'tabular-nums' : 'normal',
              whiteSpace: 'nowrap',
            }}
          >
            {display}
          </div>
        )
      })}
    </div>
  )
}

export interface DatamartVirtualTableBodyProps {
  columns: string[]
  rows: unknown[][]
  columnWidths: number[]
  minWidth: number
}

const DatamartVirtualTableBody: React.FC<DatamartVirtualTableBodyProps> = ({
  columns,
  rows,
  columnWidths,
  minWidth,
}) => {
  const height = tableBodyHeight(rows.length)
  const rowProps = React.useMemo(
    () => ({ rows, columns, columnWidths, minWidth }),
    [rows, columns, columnWidths, minWidth],
  )

  return (
    <List
      rowCount={rows.length}
      rowHeight={TABLE_ROW_HEIGHT}
      rowComponent={VirtualTableRow}
      rowProps={rowProps}
      overscanCount={8}
      style={{ height, width: '100%', minWidth }}
      tagName="div"
      role="rowgroup"
    />
  )
}

export default DatamartVirtualTableBody
