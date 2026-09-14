/**
 * ETL source database — tenant_registry via /tenants/source.
 * This is the MintHRM MySQL/Postgres source, NOT the analytics warehouse (sink).
 */
import api from './api'

export type SourceType = 'mysql' | 'postgres'

export interface TenantSourceResponse {
  tenant_id: string
  configured: boolean
  display_name?: string
  source_type: SourceType
  mysql_host?: string
  mysql_port?: number
  mysql_db?: string
  mysql_user?: string
  has_password: boolean
  is_active: boolean
  last_etl_at?: string
  extractor_profile: string
  source_connection_id?: number | null
  source_connection_name?: string | null
  source_connection_engine?: string | null
}

export interface TenantSourcePayload {
  display_name: string
  source_type: SourceType
  mysql_host: string
  mysql_port?: number
  mysql_db: string
  mysql_user: string
  mysql_password?: string
}

export interface TenantSourceTestPayload {
  source_type: SourceType
  mysql_host: string
  mysql_port?: number
  mysql_db: string
  mysql_user: string
  mysql_password: string
}

export const tenantSourceService = {
  get: () =>
    api.get<TenantSourceResponse>('/tenants/source').then(r => r.data),

  save: (data: TenantSourcePayload) =>
    api.put<TenantSourceResponse>('/tenants/source', data).then(r => r.data),

  test: (data: TenantSourceTestPayload) =>
    api
      .post<{ success: boolean; message: string }>('/tenants/source/test', data)
      .then(r => r.data),
}
