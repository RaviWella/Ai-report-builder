/**
 * Panel ids for multi-scenario modify mode (continue_last).
 */
import type { ScenarioDescriptor } from './reportLayout'

export const PRIMARY_SCENARIO_PANEL = 'primary' as const

export function isMultiScenarioReport(scenarios: ScenarioDescriptor[]): boolean {
  return scenarios.length > 1
}

export function defaultModifyTargetIds(scenarios: ScenarioDescriptor[]): string[] {
  return scenarios.map((s) => s.panelId)
}

/** Stable key — only changes when the assistant turn or scenario set changes (not every render). */
export function buildModifyScenarioContextKey(
  anchorId: string,
  scenarios: ScenarioDescriptor[] | undefined,
): string {
  if (!scenarios?.length) return `${anchorId}|`
  const ids = [...scenarios.map((s) => s.panelId)].sort().join('|')
  return `${anchorId}|${ids}`
}

export function canSendWithModifyTargets(
  multiScenario: boolean,
  followUpMode: string,
  selectedIds: string[],
): boolean {
  if (followUpMode !== 'continue_last' || !multiScenario) return true
  return selectedIds.length > 0
}

export function buildTargetScenarioPayload(
  multiScenario: boolean,
  followUpMode: string,
  selectedIds: string[],
): string[] | undefined {
  if (followUpMode !== 'continue_last' || !multiScenario || selectedIds.length === 0) {
    return undefined
  }
  return selectedIds
}
