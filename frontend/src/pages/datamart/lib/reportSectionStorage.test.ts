import { beforeEach, describe, expect, it } from 'vitest'
import {
  getSectionOpen,
  readSectionOpenMap,
  setSectionOpen,
  writeSectionOpenMap,
} from './reportSectionStorage'

describe('reportSectionStorage', () => {
  const scope = 'test-scope'

  beforeEach(() => {
    sessionStorage.clear()
  })

  it('reads and writes section open map', () => {
    writeSectionOpenMap(scope, { results: true, query: false })
    expect(readSectionOpenMap(scope)).toEqual({ results: true, query: false })
  })

  it('returns default when key missing', () => {
    expect(getSectionOpen(scope, 'charts', false)).toBe(false)
    setSectionOpen(scope, 'charts', true)
    expect(getSectionOpen(scope, 'charts', false)).toBe(true)
  })
})
