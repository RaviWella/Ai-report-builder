/**
 * Supported tenant ETL source layouts (product scenarios).
 */
import type { TenantEtlSource } from '../services/etlSourcesService'

export type EtlScenarioId =
  | 'mysql_only'
  | 'one_mysql_multi_postgres'
  | 'postgres_only_multi'
  | 'postgres_only_single'
  | 'mixed_other'
  | 'legacy'
  | 'empty'

export interface EtlScenarioDefinition {
  id: EtlScenarioId
  title: string
  description: string
  /** Product scenario A/B/C — shown in the UI checklist */
  productScenario?: 'A' | 'B' | 'C'
}

export const ETL_PRODUCT_SCENARIOS: EtlScenarioDefinition[] = [
  {
    id: 'mysql_only',
    productScenario: 'A',
    title: 'MySQL only',
    description: 'One or more MySQL sources; no PostgreSQL.',
  },
  {
    id: 'one_mysql_multi_postgres',
    productScenario: 'B',
    title: '1 MySQL + 2+ PostgreSQL',
    description: 'Exactly one MySQL source and two or more PostgreSQL sources.',
  },
  {
    id: 'postgres_only_multi',
    productScenario: 'C',
    title: 'PostgreSQL only (2+)',
    description: 'Two or more PostgreSQL sources; no MySQL.',
  },
]

export interface EtlScenarioStatus {
  activeScenario: EtlScenarioId
  mysqlCount: number
  postgresCount: number
  totalRegistered: number
  hasPrimary: boolean
  matchesProductScenario: boolean
  matchedProductScenario?: 'A' | 'B' | 'C'
  hint?: string
}

export function registeredSources(sources: TenantEtlSource[]): TenantEtlSource[] {
  return sources.filter(s => s.id > 0)
}

export function analyzeEtlSources(sources: TenantEtlSource[]): EtlScenarioStatus {
  const registered = registeredSources(sources)
  const mysqlCount = registered.filter(s => s.source_type === 'mysql').length
  const postgresCount = registered.filter(s => s.source_type === 'postgres').length
  const hasPrimary = registered.some(s => s.is_primary)

  if (registered.length === 0) {
    if (sources.length > 0) {
      return {
        activeScenario: 'legacy',
        mysqlCount: 0,
        postgresCount: 0,
        totalRegistered: 0,
        hasPrimary: false,
        matchesProductScenario: false,
        hint: 'Using legacy tenant registry. Add explicit sources below.',
      }
    }
    return {
      activeScenario: 'empty',
      mysqlCount: 0,
      postgresCount: 0,
      totalRegistered: 0,
      hasPrimary: false,
      matchesProductScenario: false,
      hint: 'Add at least one source database.',
    }
  }

  let activeScenario: EtlScenarioId
  let matchedProductScenario: 'A' | 'B' | 'C' | undefined
  let matchesProductScenario = false

  if (mysqlCount >= 1 && postgresCount === 0) {
    activeScenario = 'mysql_only'
    matchedProductScenario = 'A'
    matchesProductScenario = true
  } else if (mysqlCount === 1 && postgresCount >= 2) {
    activeScenario = 'one_mysql_multi_postgres'
    matchedProductScenario = 'B'
    matchesProductScenario = true
  } else if (mysqlCount === 0 && postgresCount >= 2) {
    activeScenario = 'postgres_only_multi'
    matchedProductScenario = 'C'
    matchesProductScenario = true
  } else if (mysqlCount === 0 && postgresCount === 1) {
    activeScenario = 'postgres_only_single'
    matchesProductScenario = false
  } else {
    activeScenario = 'mixed_other'
    matchesProductScenario = false
  }

  let hint: string | undefined
  if (!hasPrimary && registered.length > 1) {
    hint = 'Mark one source as Primary so standard stg_* tables have a clear owner.'
  } else if (activeScenario === 'mixed_other') {
    if (mysqlCount > 1 && postgresCount >= 1) {
      hint =
        'You have multiple MySQL sources. Scenario B expects exactly one MySQL; ETL will still run all sources.'
    } else if (mysqlCount === 1 && postgresCount === 1) {
      hint =
        'Scenario B expects 1 MySQL + 2+ PostgreSQL. Add another PostgreSQL source or use Scenario A/C layout.'
    }
  }

  return {
    activeScenario,
    mysqlCount,
    postgresCount,
    totalRegistered: registered.length,
    hasPrimary,
    matchesProductScenario,
    matchedProductScenario,
    hint,
  }
}
