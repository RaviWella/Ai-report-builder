/**
 * Datamart retrieval / generation validation (mirrors backend validation_models).
 */
import type {
  DatamartResponse,
  DatamartValidation,
  RetrievalValidation,
  TrustLevel,
  ValidationStatus,
} from '../../../services/datamartService'

export type {
  DatamartValidation,
  GenerationValidation,
  RetrievalValidation,
  SchemaLink,
  TrustLevel,
  ValidationStatus,
} from '../../../services/datamartService'

const DEFAULT_RETRIEVAL: RetrievalValidation = {
  status: 'sufficient',
  tables_selected: [],
}

/** Coerce persisted / partial validation JSON into a safe shape for UI. */
export function normalizeValidation(
  raw: DatamartValidation | Record<string, unknown> | null | undefined,
): DatamartValidation | null {
  if (!raw || typeof raw !== 'object') return null
  const v = raw as DatamartValidation
  const retrieval = v.retrieval
  const tables =
    retrieval && Array.isArray(retrieval.tables_selected)
      ? retrieval.tables_selected
      : []
  const status =
    retrieval?.status === 'ambiguous' ||
    retrieval?.status === 'insufficient' ||
    retrieval?.status === 'sufficient'
      ? retrieval.status
      : 'sufficient'
  return {
    ...v,
    overall:
      v.overall === 'verified' ||
      v.overall === 'plausible' ||
      v.overall === 'needs_review' ||
      v.overall === 'blocked'
        ? v.overall
        : 'needs_review',
    retrieval: {
      ...DEFAULT_RETRIEVAL,
      ...(retrieval ?? {}),
      status,
      tables_selected: tables,
    },
    generation: v.generation ?? null,
  }
}

export function validationFromResponse(
  data: DatamartResponse | null | undefined,
): DatamartValidation | null {
  if (!data?.validation) return null
  return normalizeValidation(data.validation as DatamartValidation)
}

export const TRUST_LABEL: Record<TrustLevel, string> = {
  verified: 'Verified',
  plausible: 'Plausible',
  needs_review: 'Needs review',
  blocked: 'Blocked',
}

export const TRUST_HINT: Record<TrustLevel, string> = {
  verified:
    'Retrieval and SQL checks passed with no major warnings. Review results for your business context.',
  plausible: 'Query ran successfully; minor checks flagged — skim SQL and table.',
  needs_review:
    'Some checks flagged ambiguity, warnings, or truncated rows — confirm before decisions.',
  blocked: 'Validation or execution blocked this answer.',
}

export const RETRIEVAL_STATUS_LABEL: Record<ValidationStatus, string> = {
  sufficient: 'Context sufficient',
  ambiguous: 'Context ambiguous',
  insufficient: 'Context insufficient',
}

export function trustStyles(level: TrustLevel): {
  bg: string
  border: string
  color: string
} {
  switch (level) {
    case 'verified':
      return { bg: '#ecfdf5', border: '#6ee7b7', color: '#047857' }
    case 'plausible':
      return { bg: '#eff6ff', border: '#93c5fd', color: '#1d4ed8' }
    case 'needs_review':
      return { bg: '#fffbeb', border: '#fcd34d', color: '#b45309' }
    case 'blocked':
      return { bg: '#fef2f2', border: '#fecaca', color: '#b91c1c' }
    default:
      return { bg: '#f8fafc', border: '#e2e8f0', color: '#64748b' }
  }
}
