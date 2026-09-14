import { describe, expect, it } from 'vitest'
import { deriveReportRunState } from './reportState'
import type { DatamartResponse } from '../../../services/datamartService'

const baseData: DatamartResponse = {
  question: 'Q',
  narrative: 'N',
  sql: 'SELECT 1',
  post_process_config: null,
  columns: ['a'],
  rows: [[1]],
  row_count: 1,
  error: null,
  session_id: 's1',
  message_id: 'm1',
}

describe('deriveReportRunState', () => {
  it('ignores API rows when session history (no hydrate)', () => {
    const run = deriveReportRunState({
      data: baseData,
      runResult: null,
      running: false,
      runError: null,
      hydrateFromApi: false,
    })
    expect(run.status).toBe('idle')
  })

  it('shows ready when fresh turn includes API rows', () => {
    const run = deriveReportRunState({
      data: baseData,
      runResult: null,
      running: false,
      runError: null,
      hydrateFromApi: true,
    })
    expect(run.status).toBe('ready')
    expect(run.hasUserRun).toBe(true)
    expect(run.rowCount).toBe(1)
  })

  it('shows ready for fresh turn with columns but zero rows', () => {
    const run = deriveReportRunState({
      data: { ...baseData, rows: [], row_count: 0 },
      runResult: null,
      running: false,
      runError: null,
      hydrateFromApi: true,
    })
    expect(run.status).toBe('ready')
    expect(run.rowCount).toBe(0)
  })

  it('shows ready after re-run with zero rows', () => {
    const run = deriveReportRunState({
      data: { ...baseData, columns: [], rows: [], row_count: 0 },
      runResult: {
        columns: ['a'],
        rows: [],
        row_count: 0,
        error: null,
      },
      running: false,
      runError: null,
      hydrateFromApi: false,
    })
    expect(run.status).toBe('ready')
    expect(run.rowCount).toBe(0)
  })

  it('marks ready after explicit re-run on history turn', () => {
    const run = deriveReportRunState({
      data: baseData,
      runResult: {
        columns: ['a'],
        rows: [[1]],
        row_count: 1,
        error: null,
      },
      running: false,
      runError: null,
      hydrateFromApi: false,
    })
    expect(run.status).toBe('ready')
    expect(run.hasUserRun).toBe(true)
  })
})
