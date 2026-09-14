import { describe, expect, it } from 'vitest'
import { resolveExtraBlockDataset } from './scenarioDataset'
import type { DatamartResultBlock } from '../../../services/datamartService'

const block: DatamartResultBlock = {
  block_id: 'blk-1',
  title: 'Scenario B',
  sql: 'SELECT 1',
  post_process_config: null,
  narrative: '',
  columns: ['a'],
  rows: [[1]],
  row_count: 1,
  raw_columns: null,
  raw_rows: null,
  raw_row_count: null,
  error: null,
}

describe('resolveExtraBlockDataset', () => {
  it('prefers API-embedded columns on the block (session reload / fresh turn)', () => {
    const r = resolveExtraBlockDataset(block, {})
    expect(r.hasData).toBe(true)
    expect(r.columns).toEqual(['a'])
    expect(r.rows).toEqual([[1]])
  })

  it('shows structure when columns exist but rows are empty', () => {
    const empty = { ...block, rows: [], row_count: 0 }
    const r = resolveExtraBlockDataset(empty, {})
    expect(r.hasData).toBe(true)
    expect(r.rows).toEqual([])
  })

  it('falls back to live blockSqlResults when block rows were stripped', () => {
    const stripped = { ...block, columns: [], rows: [] }
    const r = resolveExtraBlockDataset(stripped, {
      'blk-1': {
        columns: ['x'],
        rows: [[9]],
        row_count: 1,
        raw_columns: null,
        raw_rows: null,
        raw_row_count: null,
        post_process_config: null,
        error: null,
      },
    })
    expect(r.hasData).toBe(true)
    expect(r.columns).toEqual(['x'])
  })
})
