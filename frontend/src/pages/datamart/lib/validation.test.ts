import { describe, expect, it } from 'vitest'
import { normalizeValidation, TRUST_LABEL, validationFromResponse } from './validation'
import type { DatamartResponse } from '../../../services/datamartService'

describe('validationFromResponse', () => {
  it('returns null when validation absent', () => {
    expect(validationFromResponse({} as DatamartResponse)).toBeNull()
  })

  it('returns validation when present', () => {
    const data = {
      validation: {
        retrieval: { status: 'sufficient', tables_selected: ['dim_employee'] },
        overall: 'verified',
      },
    } as DatamartResponse
    expect(validationFromResponse(data)?.overall).toBe('verified')
    expect(TRUST_LABEL.verified).toBe('Verified')
  })
})

describe('normalizeValidation', () => {
  it('fills missing retrieval for persisted session JSON', () => {
    const out = normalizeValidation({ overall: 'plausible' } as never)
    expect(out?.retrieval.status).toBe('sufficient')
    expect(out?.retrieval.tables_selected).toEqual([])
    expect(out?.overall).toBe('plausible')
  })
})
