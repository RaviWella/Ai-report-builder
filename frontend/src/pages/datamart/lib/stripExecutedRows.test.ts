import { describe, expect, it } from 'vitest'
import { stripExecutedRows } from './stripExecutedRows'
import type { DatamartResponse } from '../../../services/datamartService'

const sample: DatamartResponse = {
  question: 'Q',
  narrative: 'N',
  sql: 'SELECT 1',
  post_process_config: null,
  columns: ['a'],
  rows: [[1]],
  row_count: 1,
  raw_columns: ['a'],
  raw_rows: [[1]],
  raw_row_count: 1,
  error: null,
  session_id: 's1',
  message_id: 'm1',
  extra_result_blocks: [
    {
      block_id: 'b1',
      title: 'Extra',
      sql: 'SELECT 2',
      post_process_config: null,
      columns: ['x'],
      rows: [[2]],
      row_count: 1,
    },
  ],
}

describe('stripExecutedRows', () => {
  it('clears primary and extra block row payloads', () => {
    const out = stripExecutedRows(sample)
    expect(out.columns).toEqual([])
    expect(out.rows).toEqual([])
    expect(out.row_count).toBe(0)
    expect(out.sql).toBe('SELECT 1')
    expect(out.narrative).toBe('N')
    expect(out.extra_result_blocks?.[0]?.rows).toEqual([])
    expect(out.extra_result_blocks?.[0]?.columns).toEqual([])
  })
})
