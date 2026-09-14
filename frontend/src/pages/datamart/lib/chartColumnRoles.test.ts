import { describe, expect, it } from 'vitest'
import {
  analyzeDatasetColumns,
  getAxisFieldLabels,
  pickDefaultAxisColumns,
  isValidAxisPair,
} from './chartColumnRoles'

describe('chartColumnRoles', () => {
  const columns = ['branch', 'employee_id', 'leave_days']
  const rows = [
    ['North', 'E1', 30],
    ['South', 'E2', 15],
    ['North', 'E3', 5],
  ]

  it('detects category and value columns from response rows', () => {
    const roles = analyzeDatasetColumns(columns, rows)
    expect(roles.categoryColumns).toContain('branch')
    expect(roles.valueColumns).toContain('leave_days')
  })

  it('picks sensible default axis pair', () => {
    const roles = analyzeDatasetColumns(columns, rows)
    const defaults = pickDefaultAxisColumns(roles, columns, rows)
    expect(defaults).toEqual({ categoryColumn: 'branch', valueColumn: 'leave_days' })
  })

  it('returns chart-type-specific axis labels', () => {
    expect(getAxisFieldLabels('pie').categoryLabel).toContain('Slice')
    expect(getAxisFieldLabels('bar').categoryLabel).toContain('Y-axis')
    expect(getAxisFieldLabels('column').valueLabel).toContain('Y-axis')
  })

  it('validates axis pair', () => {
    const roles = analyzeDatasetColumns(columns, rows)
    expect(isValidAxisPair('branch', 'leave_days', roles)).toBe(true)
    expect(isValidAxisPair('branch', 'branch', roles)).toBe(false)
  })
})
