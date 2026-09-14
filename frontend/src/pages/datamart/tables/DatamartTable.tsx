/**

 * Scrollable result table (single overflow region — vertical + horizontal).

 */

import React, { useMemo } from 'react'

import { dmCopy } from '../lib/copy'

import {

  TABLE_MAX_VIEWPORT_HEIGHT,

  computeColumnWidths,

  formatCell,

  formatHeader,

  isNumeric,

  isSummaryRow,

  normalizeTableRow,

  partitionTableRows,

  tableMinWidth,

} from '../lib/tableFormat'



interface DatamartTableProps {

  columns: string[]

  rows: unknown[][]

  rowCount: number

  embedded?: boolean

}



function renderDataRow(

  row: unknown[],

  rowIdx: number,

  summary: boolean,

  columnCount: number,

  columnWidths: number[],

): React.ReactNode {

  const cells = normalizeTableRow(row, columnCount)

  const isEven = rowIdx % 2 === 0

  const baseBg = summary ? '#f0fdfa' : isEven ? '#ffffff' : '#f8fafc'

  const hoverBg = summary ? '#ccfbf1' : '#f0f9ff'



  return (

    <tr

      key={rowIdx}

      style={{ background: baseBg, transition: 'background 0.1s' }}

      onMouseEnter={(e) => {

        ;(e.currentTarget as HTMLTableRowElement).style.background = hoverBg

      }}

      onMouseLeave={(e) => {

        ;(e.currentTarget as HTMLTableRowElement).style.background = baseBg

      }}

    >

      {cells.map((cell, cellIdx) => {

        const display = formatCell(cell)

        const numeric = isNumeric(cell)

        const isNull = cell === null || cell === undefined

        const width = columnWidths[cellIdx]



        return (

          <td

            key={cellIdx}

            title={!isNull && display !== '—' ? display : undefined}

            style={{

              width,

              minWidth: width,

              maxWidth: width,

              padding: '9px 14px',

              borderBottom: '1px solid #f1f5f9',

              color: isNull ? '#cbd5e1' : summary ? '#0f766e' : '#334155',

              fontWeight: summary ? 600 : 400,

              textAlign: numeric ? 'right' : 'left',

              overflow: 'hidden',

              textOverflow: 'ellipsis',

              fontVariantNumeric: numeric ? 'tabular-nums' : 'normal',

              ...(summary && { borderTop: '2px solid #99f6e4' }),

            }}

          >

            {display}

          </td>

        )

      })}

    </tr>

  )

}



const DatamartTable: React.FC<DatamartTableProps> = ({

  columns,

  rows,

  rowCount,

  embedded = false,

}) => {

  const { detailRows, summaryRows } = useMemo(() => partitionTableRows(rows), [rows])

  const widthSample = useMemo(

    () => [...detailRows, ...summaryRows],

    [detailRows, summaryRows],

  )

  const columnWidths = useMemo(

    () => computeColumnWidths(columns, widthSample),

    [columns, widthSample],

  )

  const minTableWidth = useMemo(() => tableMinWidth(columnWidths), [columnWidths])



  if (!columns.length) return null



  const displayRows = [...detailRows, ...summaryRows]



  return (

    <div>

      <div

        className="datamart-table-scroll"

        style={{

          maxHeight: TABLE_MAX_VIEWPORT_HEIGHT,

          ...(embedded

            ? {}

            : {

                border: '1px solid #e2e8f0',

                borderRadius: 10,

              }),

        }}

      >

        <table

          className="datamart-table-grid"

          role="table"

          aria-rowcount={displayRows.length}

          style={{ width: minTableWidth }}

        >

          <colgroup>

            {columnWidths.map((width, idx) => (

              <col key={columns[idx] ?? idx} style={{ width }} />

            ))}

          </colgroup>

          <thead>

            <tr>

              {columns.map((col, idx) => (

                <th

                  key={col}

                  scope="col"

                  style={{ width: columnWidths[idx] }}

                  title={formatHeader(col)}

                >

                  {formatHeader(col)}

                </th>

              ))}

            </tr>

          </thead>

          <tbody>

            {displayRows.length === 0 ? (

              <tr>

                <td

                  colSpan={columns.length}

                  style={{

                    padding: '24px 14px',

                    textAlign: 'center',

                    color: '#94a3b8',

                    fontSize: 13,

                  }}

                >

                  {dmCopy.table.noResults}

                </td>

              </tr>

            ) : (

              displayRows.map((row, rowIdx) =>

                renderDataRow(row, rowIdx, isSummaryRow(row), columns.length, columnWidths),

              )

            )}

          </tbody>

        </table>

      </div>



      {!embedded && (

        <div style={{ marginTop: 6, display: 'flex', alignItems: 'center', gap: 6 }}>

          <span

            style={{

              display: 'inline-flex',

              alignItems: 'center',

              padding: '2px 8px',

              background: '#f1f5f9',

              borderRadius: 20,

              fontSize: 11,

              color: '#64748b',

              fontWeight: 500,

            }}

          >

            {dmCopy.table.rowLabel(rowCount)}

          </span>

          {rowCount > 500 && (

            <span style={{ color: '#f59e0b', fontSize: 11 }}>{dmCopy.table.appendWarning}</span>

          )}

          {rowCount === 500 && (

            <span style={{ color: '#f59e0b', fontSize: 11 }}>{dmCopy.table.capWarning}</span>

          )}

        </div>

      )}

    </div>

  )

}



export default DatamartTable


