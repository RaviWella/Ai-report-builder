import api from './api'

/** Unified ETL source database (connection + ETL metadata). */
export interface SourceDatabase {
  id: number
  tenant_id: string
  source_key: string
  display_name: string
  source_type: 'mysql' | 'postgres'
  connection_id: number
  source_schema?: string | null
  extractor_profile: string
  mapping_variant?: string | null
  is_primary: boolean
  is_active: boolean
  priority: number
  staging_suffix: string
  host: string
  port: number
  database_name: string
  username: string
  connection_name: string
  is_healthy: boolean
}

export interface SourceDatabaseCreate {
  source_key: string
  display_name: string
  source_type: 'mysql' | 'postgres'
  host: string
  port?: number
  database_name: string
  username: string
  password: string
  source_schema?: string
  extractor_profile?: string
  mapping_variant?: string | null
  is_primary?: boolean
  priority?: number
}

export interface SourceDatabaseTest {
  source_type: 'mysql' | 'postgres'
  host: string
  port?: number
  database_name: string
  username: string
  password: string
  source_schema?: string
}

export interface EtlScenarioResponse {
  active_scenario: string
  mysql_count: number
  postgres_count: number
  total_registered: number
  has_primary: boolean
  primary_source_key?: string | null
  matches_product_scenario: boolean
  product_scenario?: 'A' | 'B' | 'C' | null
  etl_ready: boolean
}

/** @deprecated Use SourceDatabase */
export type TenantEtlSource = SourceDatabase

/** @deprecated Use SourceDatabaseCreate */
export type TenantEtlSourceCreate = SourceDatabaseCreate

export const etlSourcesService = {
  list: () => api.get<SourceDatabase[]>('/tenants/etl-sources/').then(r => r.data),

  scenario: () =>
    api.get<EtlScenarioResponse>('/tenants/etl-sources/scenario').then(r => r.data),

  test: (data: SourceDatabaseTest) =>
    api
      .post<{ success: boolean; message: string }>('/tenants/etl-sources/test', data)
      .then(r => r.data),

  create: (data: SourceDatabaseCreate) =>
    api.post<SourceDatabase>('/tenants/etl-sources/', data).then(r => r.data),

  remove: (id: number) => api.delete(`/tenants/etl-sources/${id}`),
}
