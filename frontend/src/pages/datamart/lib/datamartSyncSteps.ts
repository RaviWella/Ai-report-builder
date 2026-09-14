/**
 * Full sync steps (matches backend bootstrap sync_phase).
 */
import type { DatamartBootstrapResponse } from '../../../services/datamartService'
import { datamartService } from '../../../services/datamartService'

export type SyncStepId = 'prepare' | 'catalog' | 'metadata'

export type SyncStepStatus = 'pending' | 'running' | 'completed' | 'failed' | 'skipped'

export interface DatamartSyncStep {
  id: SyncStepId
  label: string
  detail?: string
  status: SyncStepStatus
}

export const DATAMART_SYNC_STEPS: ReadonlyArray<{ id: SyncStepId; label: string }> = [
  { id: 'prepare', label: 'Clear cached metadata' },
  { id: 'catalog', label: 'Refresh semantic catalog from warehouse' },
  { id: 'metadata', label: 'Scan schemas and update table counts' },
]

export function initialSyncSteps(): DatamartSyncStep[] {
  return DATAMART_SYNC_STEPS.map((s) => ({ ...s, status: 'pending' as const }))
}

function applyStepStatus(
  steps: DatamartSyncStep[],
  activeId: SyncStepId,
  status: SyncStepStatus,
  detail?: string,
): DatamartSyncStep[] {
  const activeIdx = steps.findIndex((s) => s.id === activeId)
  return steps.map((step, i) => {
    if (step.id === activeId) {
      return { ...step, status, detail: detail ?? step.detail }
    }
    if (activeIdx >= 0 && i < activeIdx && step.status === 'pending') {
      return { ...step, status: 'completed' }
    }
    if (activeIdx >= 0 && i < activeIdx && step.status === 'running') {
      return { ...step, status: 'completed' }
    }
    return step
  })
}

export function markStepsFailed(steps: DatamartSyncStep[], activeId: SyncStepId): DatamartSyncStep[] {
  return steps.map((s) =>
    s.id === activeId ? { ...s, status: 'failed' as const } : s,
  )
}

export async function runDatamartFullSync(
  onSteps: (steps: DatamartSyncStep[]) => void,
): Promise<DatamartBootstrapResponse> {
  let steps = initialSyncSteps()

  const runPhase = async (
    id: SyncStepId,
    fn: () => Promise<DatamartBootstrapResponse>,
    detailOnDone?: (data: DatamartBootstrapResponse) => string | undefined,
  ) => {
    steps = applyStepStatus(steps, id, 'running')
    onSteps(steps)
    const data = await fn()
    const detail = detailOnDone?.(data)
    steps = applyStepStatus(steps, id, 'completed', detail)
    onSteps(steps)
    return data
  }

  try {
    await runPhase('prepare', () => datamartService.bootstrap({ syncPhase: 'prepare' }))

    let catalogData: DatamartBootstrapResponse | undefined
    catalogData = await runPhase(
      'catalog',
      () => datamartService.bootstrap({ syncPhase: 'catalog' }),
      (data) => {
        const n = data.catalog_sync?.table_count
        const path = data.catalog_sync?.catalog_path
        if (n != null && path) {
          const short = path.split(/[/\\]/).pop()
          return `${n} tables scanned → ${short}`
        }
        return undefined
      },
    )

    if (catalogData.catalog_sync && catalogData.catalog_sync.ok === false) {
      steps = applyStepStatus(steps, 'metadata', 'skipped', 'Skipped — catalog step failed')
      onSteps(steps)
      throw new Error(catalogData.catalog_sync.error ?? 'Semantic catalog refresh failed')
    }

    const meta = await runPhase(
      'metadata',
      () => datamartService.bootstrap({ syncPhase: 'metadata' }),
      (data) => `${data.total_tables} tables in ${data.database_name}`,
    )

    return meta
  } catch (err) {
    const failedId = steps.find((s) => s.status === 'running')?.id ?? 'catalog'
    steps = markStepsFailed(steps, failedId)
    onSteps(steps)
    throw err
  }
}
