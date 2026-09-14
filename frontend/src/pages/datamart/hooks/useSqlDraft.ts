/**
 * Local SQL editor draft vs stored script on the message/version.
 */
import { useCallback, useEffect, useMemo, useState } from 'react'

function normalizeSql(sql: string): string {
  return sql.replace(/\r\n/g, '\n').trim()
}

export function useSqlDraft(storedSql: string | null | undefined, resetKey?: string) {
  const stored = storedSql ?? ''
  const [draftSql, setDraftSql] = useState(stored)

  useEffect(() => {
    setDraftSql(stored)
  }, [stored, resetKey])

  const isDirty = useMemo(
    () => normalizeSql(draftSql) !== normalizeSql(stored),
    [draftSql, stored],
  )

  const resetDraft = useCallback(() => {
    setDraftSql(stored)
  }, [stored])

  return {
    storedSql: stored,
    draftSql,
    setDraftSql,
    isDirty,
    resetDraft,
  }
}
