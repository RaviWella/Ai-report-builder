/**
 * Optional sessionStorage-backed open state for report card sections.
 */
import { useCallback, useEffect, useState } from 'react'
import {
  getSectionOpen,
  readSectionOpenMap,
  setSectionOpen,
  type SectionOpenMap,
} from '../lib/reportSectionStorage'

export interface ReportSectionPersist {
  getOpen: (sectionKey: string, defaultOpen: boolean) => boolean
  setOpen: (sectionKey: string, open: boolean) => void
}

export function useReportSectionPersist(scope: string | null | undefined): ReportSectionPersist | null {
  const [map, setMap] = useState<SectionOpenMap>(() =>
    scope ? readSectionOpenMap(scope) : {},
  )

  useEffect(() => {
    setMap(scope ? readSectionOpenMap(scope) : {})
  }, [scope])

  const getOpen = useCallback(
    (sectionKey: string, defaultOpen: boolean) => {
      if (!scope) return defaultOpen
      return sectionKey in map ? map[sectionKey]! : defaultOpen
    },
    [map, scope],
  )

  const setOpen = useCallback(
    (sectionKey: string, open: boolean) => {
      if (!scope) return
      setMap(setSectionOpen(scope, sectionKey, open))
    },
    [scope],
  )

  if (!scope) return null
  return { getOpen, setOpen }
}

/** For tests: mirror production read without React. */
export function resolveSectionOpen(
  scope: string,
  sectionKey: string,
  defaultOpen: boolean,
): boolean {
  return getSectionOpen(scope, sectionKey, defaultOpen)
}
