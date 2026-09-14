/**
 * Database Connection Service for MintHRM.
 * Ported from mint-analytics — same API shape, same endpoint paths.
 * Lets HR analysts connect to any customer database for ad-hoc queries.
 */
import api from './api'

// ── Types ────────────────────────────────────────────────────────

export interface SSHTunnelConfig {
  ssh_enabled?: boolean
  ssh_host?: string
  ssh_port?: number
  ssh_username?: string
  ssh_auth_method?: 'password' | 'key'
  ssh_password?: string
  ssh_private_key?: string
  ssh_key_passphrase?: string
}

export interface DatabaseConnectionCreate extends SSHTunnelConfig {
  name: string
  engine: 'postgres' | 'mysql' | 'sqlserver'
  host: string
  port: number
  database_name: string
  username: string
  password: string
  description?: string
  default_schema?: string
  ssl_mode?: string
  category?: string
  tags?: string[]
}

export interface DatabaseConnectionUpdate extends SSHTunnelConfig {
  name?: string
  engine?: string
  host?: string
  port?: number
  database_name?: string
  username?: string
  password?: string
  description?: string
  default_schema?: string
  ssl_mode?: string
  category?: string
  tags?: string[]
  is_active?: boolean
}

export interface DatabaseConnectionOut {
  id: number
  name: string
  engine: string
  host: string
  port: number
  database_name: string
  username: string
  description?: string
  default_schema?: string
  ssl_mode?: string
  category?: string
  tags: string[]
  is_healthy: boolean
  is_active: boolean
  health_check_error?: string
  ssh_enabled?: boolean
  ssh_host?: string
  ssh_port?: number
  ssh_username?: string
  ssh_auth_method?: string
  created_at?: string
  updated_at?: string
}

export interface TenantSourceInfo {
  tenant_id: string
  configured: boolean
  source_type: string
  mysql_host?: string
  mysql_port?: number
  mysql_db?: string
  source_connection_id?: number | null
  source_connection_name?: string | null
  source_connection_engine?: string | null
}

export interface TestConnectionRequest extends SSHTunnelConfig {
  engine: string
  host: string
  port: number
  database_name: string
  username: string
  password: string
}

export interface TableInfo {
  id: string
  name: string
  display_name: string
  schema: string
  db_id: number
  field_count: number
}

export interface FieldInfo {
  id: string
  name: string
  display_name: string
  base_type: string
  semantic_type?: string
  database_type: string
  fk_target?: string
}

export interface QueryResultColumn {
  name: string
  display_name: string
  base_type: string
}

export interface QueryResult {
  data: { cols: QueryResultColumn[]; rows: unknown[][] }
  row_count: number
  status: string
  error?: string
  truncated?: boolean
  truncation_reason?: string
}

// ── Service ──────────────────────────────────────────────────────

export const databaseConnectionService = {
  list: () =>
    api.get<DatabaseConnectionOut[]>('/connections/').then(r => r.data),

  get: (id: number) =>
    api.get<DatabaseConnectionOut>(`/connections/${id}`).then(r => r.data),

  create: (data: DatabaseConnectionCreate) =>
    api.post<DatabaseConnectionOut>('/connections/', data).then(r => r.data),

  update: (id: number, data: DatabaseConnectionUpdate) =>
    api.put<DatabaseConnectionOut>(`/connections/${id}`, data).then(r => r.data),

  delete: (id: number) =>
    api.delete(`/connections/${id}`),

  test: (data: TestConnectionRequest) =>
    api.post<{ success: boolean; message: string }>('/connections/test', data).then(r => r.data),

  checkHealth: (id: number) =>
    api.post<{ success: boolean; message: string }>(`/connections/${id}/health`).then(r => r.data),

  getSchemas: (id: number) =>
    api.get<{ schemas: string[] }>(`/connections/${id}/schemas`).then(r => r.data.schemas),

  getTables: (id: number, opts?: { schema?: string; search?: string }) =>
    api.get<{ tables: TableInfo[]; total: number }>(`/connections/${id}/tables`, { params: opts }).then(r => r.data),

  getTableFields: (id: number, tableName: string, schema?: string) =>
    api.get<{ fields: FieldInfo[] }>(`/connections/${id}/tables/${tableName}/fields`, {
      params: schema ? { schema } : {},
    }).then(r => r.data),

  getMetadata: (id: number) =>
    api.get<{ id: number; name: string; engine: string; tables: TableInfo[] }>(
      `/connections/${id}/metadata`
    ).then(r => r.data),

  executeQuery: (id: number, sql: string, opts?: { limit?: number; schema?: string }) =>
    api.post<QueryResult>(`/connections/${id}/query`, {
      sql,
      limit: opts?.limit,
      schema_name: opts?.schema,
    }).then(r => r.data),

  // ── ETL source management ──────────────────────────────────────

  /** Get the current tenant's ETL source configuration. */
  getEtlSource: () =>
    api.get<TenantSourceInfo>('/tenants/source').then(r => r.data),

  /** Point the tenant's ETL source at a saved DatabaseConnection. */
  setEtlSource: (connectionId: number | null) =>
    api.put<TenantSourceInfo>('/tenants/source/connection', { connection_id: connectionId })
      .then(r => r.data),
}
