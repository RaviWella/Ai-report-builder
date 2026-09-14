import { describe, expect, it } from 'vitest'
import {
  buildModifyScenarioContextKey,
  buildTargetScenarioPayload,
  canSendWithModifyTargets,
  defaultModifyTargetIds,
  isMultiScenarioReport,
} from './modifyScenarioTargets'
import type { ScenarioDescriptor } from './reportLayout'

const twoScenarios: ScenarioDescriptor[] = [
  { panelId: 'primary', label: 'Main', isPrimary: true },
  { panelId: 'block-b', label: 'Branch view', isPrimary: false },
]

describe('modifyScenarioTargets', () => {
  it('detects multi-scenario reports', () => {
    expect(isMultiScenarioReport(twoScenarios)).toBe(true)
    expect(isMultiScenarioReport([twoScenarios[0]])).toBe(false)
  })

  it('requires selection in continue_last multi-scenario mode', () => {
    expect(canSendWithModifyTargets(true, 'continue_last', [])).toBe(false)
    expect(canSendWithModifyTargets(true, 'continue_last', ['primary'])).toBe(true)
    expect(canSendWithModifyTargets(true, 'add_scenario', [])).toBe(true)
  })

  it('builds stable context key from panel ids', () => {
    const key = buildModifyScenarioContextKey('msg-1', twoScenarios)
    expect(key).toBe('msg-1|block-b|primary')
    expect(buildModifyScenarioContextKey('msg-1', [...twoScenarios])).toBe(key)
  })

  it('builds API payload only when needed', () => {
    expect(
      buildTargetScenarioPayload(true, 'continue_last', defaultModifyTargetIds(twoScenarios)),
    ).toEqual(['primary', 'block-b'])
    expect(buildTargetScenarioPayload(false, 'continue_last', ['primary'])).toBeUndefined()
  })
})
