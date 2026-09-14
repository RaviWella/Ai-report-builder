/**
 * Persist datamart report section open/closed state in sessionStorage.
 */

const STORAGE_PREFIX = 'dm-report-sections:'

export type SectionOpenMap = Record<string, boolean>

function storageKey(scope: string): string {
  return `${STORAGE_PREFIX}${scope}`
}

export function readSectionOpenMap(scope: string): SectionOpenMap {
  if (typeof sessionStorage === 'undefined') return {}
  try {
    const raw = sessionStorage.getItem(storageKey(scope))
    if (!raw) return {}
    const parsed = JSON.parse(raw) as unknown
    if (!parsed || typeof parsed !== 'object') return {}
    const out: SectionOpenMap = {}
    for (const [key, value] of Object.entries(parsed)) {
      if (typeof value === 'boolean') out[key] = value
    }
    return out
  } catch {
    return {}
  }
}

export function writeSectionOpenMap(scope: string, map: SectionOpenMap): void {
  if (typeof sessionStorage === 'undefined') return
  try {
    sessionStorage.setItem(storageKey(scope), JSON.stringify(map))
  } catch {
    /* quota / private mode */
  }
}

export function getSectionOpen(
  scope: string,
  sectionKey: string,
  defaultOpen: boolean,
): boolean {
  const map = readSectionOpenMap(scope)
  return sectionKey in map ? map[sectionKey]! : defaultOpen
}

export function setSectionOpen(
  scope: string,
  sectionKey: string,
  open: boolean,
): SectionOpenMap {
  const map = { ...readSectionOpenMap(scope), [sectionKey]: open }
  writeSectionOpenMap(scope, map)
  return map
}
