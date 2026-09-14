/**
 * Datamart Chat Service
 * =====================
 * Communicates with the /api/v1/datamart endpoints.
 * Uses the shared axios instance so auth headers are applied automatically.
 */
import api from './api'

// ── Chat types ────────────────────────────────────────────────────

export type DatamartFollowUpMode =
  | 'continue_last'
  | 'add_scenario'
  | 'new_question'
  | 'clarify_reply'

export interface DatamartChatRequest {
  question: string
  session_id?: string | null
  /** Replace this turn and all later turns, then append the new question. */
  edit_from_turn_index?: number | null
  /**
   * When the session has a prior assistant reply: continue_last refines that result;
   * new_question runs a fresh query without editing the last SQL.
   */
  follow_up_mode?: DatamartFollowUpMode | null
  /** With continue_last on multi-scenario reports: 'primary' and/or extra block_id values. */
  target_scenario_ids?: string[] | null
  /** Table short names confirmed after grounding preview (limits broker selection). */
  confirmed_tables?: string[] | null
  history?: Array<{ role: 'user' | 'assistant'; content: string }>
}

export interface GroundingPreviewRequest {
  question: string
  session_id?: string | null
  follow_up_mode?: DatamartFollowUpMode | null
  confirmed_tables?: string[] | null
}

export interface GroundingPreviewResponse {
  question: string
  retrieval: RetrievalValidation
  tables_selected: string[]
  schema_links?: SchemaLink[]
  can_proceed: boolean
  prompt_preview_chars: number
}

export interface DatamartResultBlock {
  block_id: string
  title?: string | null
  narrative?: string
  sql?: string | null
  post_process_config: Array<Record<string, unknown>> | null
  columns: string[]
  rows: unknown[][]
  row_count: number
  raw_columns?: string[] | null
  raw_rows?: unknown[][] | null
  raw_row_count?: number | null
  error?: string | null
  validation?: Record<string, unknown> | null
  pipeline_trace?: PipelineTrace | null
}

export type ValidationStatus = 'sufficient' | 'ambiguous' | 'insufficient'
export type TrustLevel = 'verified' | 'plausible' | 'needs_review' | 'blocked'

export interface SchemaLink {
  term: string
  qualified_column: string
  confidence: 'high' | 'medium' | 'low'
  source: 'catalog_dimension' | 'catalog_metric' | 'inferred'
}

export interface RetrievalValidation {
  status: ValidationStatus
  source?: string
  tables_selected: string[]
  topics_matched?: string[]
  metrics_matched?: string[]
  schema_links?: SchemaLink[]
  missing_tables?: string[]
  extra_tables?: string[]
  warnings?: string[]
  clarification_hints?: string[]
  message?: string | null
  /** Per-table columns included in the LLM grounding packet (* = join-only). */
  columns_in_context?: Record<string, string[]>
}

export interface GenerationValidation {
  binding: 'passed' | 'failed' | 'skipped'
  warnings?: string[]
  truncated?: boolean
  grounding_expanded?: boolean
  evidence?: Record<string, unknown> | null
}

export type PipelineStepStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'warning'
  | 'failed'
  | 'skipped'
  | 'blocked'

export interface PipelineStep {
  id: string
  label: string
  status: PipelineStepStatus
  detail?: string | null
  duration_ms?: number | null
}

export interface RecoveryEvent {
  attempt: number
  phase: string
  issue: string
  action: string
  detail: string
  user_message: string
}

export interface PipelineTrace {
  steps: PipelineStep[]
  repair_attempts_used: number
  repair_attempts_max: number
  recovery_events?: RecoveryEvent[]
}

/** S5: domain, SQL tier, and source for one turn (mirrors backend PipelineTurnMeta). */
export interface PipelineTurnMeta {
  domain?: string | null
  sql_tier?: 'A' | 'B' | 'C' | null
  sql_source?: string | null
  tables_linked?: string[]
}

export interface DatamartValidation {
  retrieval: RetrievalValidation
  generation?: GenerationValidation | null
  overall: TrustLevel
  awaiting_clarification?: boolean
  anchor_question?: string | null
  /** Persisted with validation JSON when reloading a session. */
  pipeline_trace?: PipelineTrace | null
}

export interface DatamartResponse {
  question: string
  narrative: string
  sql: string | null
  post_process_config: Array<Record<string, unknown>> | null
  columns: string[]
  rows: unknown[][]
  row_count: number
  raw_columns?: string[] | null
  raw_rows?: unknown[][] | null
  raw_row_count?: number | null
  error: string | null
  session_id: string | null
  message_id: string | null
  turn_index?: number | null
  chart_configs?: unknown[] | null
  extra_result_blocks?: DatamartResultBlock[] | null
  report_layout?: Record<string, unknown> | null
  validation?: DatamartValidation | null
  pipeline_trace?: PipelineTrace | null
  pipeline_meta?: PipelineTurnMeta | null
}

export interface PatchMessageReportMetaRequest {
  report_layout?: Record<string, unknown> | null
  primary_label?: string | null
  block_labels?: Record<string, string> | null
}

export interface PatchMessageReportMetaResponse {
  message_id: string
  report_layout?: Record<string, unknown> | null
  extra_result_blocks?: Array<{
    block_id: string
    title?: string | null
    sql_script: string
    post_process_config?: Array<Record<string, unknown>> | null
  }> | null
}

export interface PatchTemplateVersionReportMetaRequest {
  report_layout?: Record<string, unknown> | null
  primary_label?: string | null
  block_labels?: Record<string, string> | null
}

export interface PatchTemplateVersionReportMetaResponse {
  version_id: string
  report_layout?: Record<string, unknown> | null
  extra_result_blocks?: Array<{
    block_id: string
    title?: string | null
    sql_script: string
    post_process_config?: Array<Record<string, unknown>> | null
  }> | null
}

/** Metadata-only extra blocks stored on template versions (same shape as chat messages). */
export type TemplateExtraBlockMeta = {
  block_id: string
  title?: string | null
  sql_script: string
  post_process_config?: Array<Record<string, unknown>> | null
}

// ── Session types ─────────────────────────────────────────────────

export interface SessionListItem {
  id: string
  title: string
  created_at: string
  updated_at: string
  message_count: number
  group_id: string | null
}

export interface SessionListResponse {
  sessions: SessionListItem[]
}

export interface UndoLastModificationResponse {
  session_id: string
  removed_turn_index: number
  restored_turn_index: number
  restored_assistant_message_id?: string | null
}

export interface MessageResponse {
  id: string
  role: 'user' | 'assistant'
  content: string
  sql_script: string | null
  question_ref: string | null
  post_process_config: Array<Record<string, unknown>> | null
  chart_configs?: unknown[] | null
  extra_result_blocks?: Array<{
    block_id: string
    title?: string | null
    sql_script: string
    post_process_config?: Array<Record<string, unknown>> | null
  }> | null
  turn_index: number
  is_summarised: boolean
  created_at: string
  follow_up_mode?: DatamartFollowUpMode | null
  report_layout?: Record<string, unknown> | null
  validation?: DatamartValidation | null
}

export interface SessionMessagesResponse {
  session_id: string
  messages: MessageResponse[]
  total_turns: number
  page: number
  page_size: number
  has_more: boolean
}

export interface SqlExecuteResponse {
  message_id: string
  block_id?: string | null
  sql: string
  post_process_config: Array<Record<string, unknown>> | null
  columns: string[]
  rows: unknown[][]
  row_count: number
  raw_columns?: string[] | null
  raw_rows?: unknown[][] | null
  raw_row_count?: number | null
  error: string | null
}

// ── Session group types ───────────────────────────────────────────

export interface SessionGroupResponse {
  id: string
  name: string
  position: number
  created_at: string
  updated_at: string
}

export interface SessionGroupListResponse {
  groups: SessionGroupResponse[]
}

// ── Template types ────────────────────────────────────────────────

export interface TemplateVersionResponse {
  id: string
  template_id: string
  version_num: number
  label: string | null
  sql_script: string
  post_process_config: Array<Record<string, unknown>> | null
  chart_configs?: unknown[] | null
  extra_result_blocks?: TemplateExtraBlockMeta[] | null
  report_layout?: Record<string, unknown> | null
  narrative: string | null
  source_session_id: string | null
  source_message_id: string | null
  is_latest: boolean
  created_at: string
}

export interface TemplateResponse {
  id: string
  name: string
  group_id: string | null
  is_pinned: boolean
  created_at: string
  updated_at: string
  latest_version: TemplateVersionResponse | null
}

export interface TemplateListResponse {
  templates: TemplateResponse[]
}

export interface TemplateVersionListResponse {
  versions: TemplateVersionResponse[]
}

export interface TemplateGroupResponse {
  id: string
  name: string
  position: number
  created_at: string
  updated_at: string
}

export interface TemplateGroupListResponse {
  groups: TemplateGroupResponse[]
}

// ── Misc ──────────────────────────────────────────────────────────

export interface PutMessageChartsResponse {
  message_id: string
  chart_configs: unknown[]
}

export interface SuggestionsResponse {
  questions: string[]
}

export interface CatalogSyncSummary {
  ok: boolean
  catalog_path?: string | null
  table_count?: number
  topics_tables_added?: Record<string, string[]>
  topics_tables_removed?: Record<string, string[]>
  joins_added?: number
  dimension_stubs_added?: string[]
  removed_dimensions?: string[]
  warehouse_only_tables?: string[]
  warnings?: string[]
  error?: string | null
}

export interface DatamartBootstrapResponse {
  tenant_id: string
  profile: string
  database_name: string
  query_schemas: string[]
  primary_schema: string
  table_counts: Record<string, number>
  total_tables: number
  ready: boolean
  synced_at: string
  fingerprint: string
  catalog_sync?: CatalogSyncSummary | null
}

/** Full sync (catalog YAML + table counts) can take 30–90s on large warehouses. */
const DATAMART_BOOTSTRAP_FULL_SYNC_TIMEOUT_MS = 180_000

// LLM + warehouse work can exceed default axios timeouts; keep in sync with proxy/read timeouts.
const DATAMART_CHAT_TIMEOUT_MS = 240_000

// ── Service ───────────────────────────────────────────────────────

export const datamartService = {
  bootstrap: (opts?: {
    refresh?: boolean
    syncPhase?: 'prepare' | 'catalog' | 'metadata' | 'full'
  }): Promise<DatamartBootstrapResponse> => {
    const staged = Boolean(opts?.syncPhase)
    const full = opts?.refresh || opts?.syncPhase === 'full'
    const params: Record<string, string | boolean> = {}
    if (opts?.syncPhase) params.sync_phase = opts.syncPhase
    else if (opts?.refresh) params.refresh = true
    return api
      .get<DatamartBootstrapResponse>('/datamart/bootstrap', {
        params: Object.keys(params).length ? params : undefined,
        timeout: staged || full ? DATAMART_BOOTSTRAP_FULL_SYNC_TIMEOUT_MS : undefined,
      })
      .then((r) => r.data)
  },

  // Chat
  previewGrounding: (req: GroundingPreviewRequest): Promise<GroundingPreviewResponse> =>
    api.post<GroundingPreviewResponse>('/datamart/grounding/preview', req).then((r) => r.data),

  chat: (req: DatamartChatRequest): Promise<DatamartResponse> =>
    api
      .post<DatamartResponse>('/datamart/chat', req, { timeout: DATAMART_CHAT_TIMEOUT_MS })
      .then((r) => r.data),

  // Sessions
  listSessions: (): Promise<SessionListResponse> =>
    api.get<SessionListResponse>('/datamart/sessions').then((r) => r.data),

  createSession: (title = 'New conversation'): Promise<SessionListItem> =>
    api.post<SessionListItem>('/datamart/sessions', { title }).then((r) => r.data),

  getSessionMessages: (sessionId: string, page = 1, pageSize = 5): Promise<SessionMessagesResponse> =>
    api.get<SessionMessagesResponse>(`/datamart/sessions/${sessionId}/messages`,
      { params: { page, page_size: pageSize } }).then((r) => r.data),

  undoLastModification: (sessionId: string): Promise<UndoLastModificationResponse> =>
    api
      .post<UndoLastModificationResponse>(
        `/datamart/sessions/${sessionId}/undo-last-modification`,
      )
      .then((r) => r.data),

  executeMessageSql: (
    sessionId: string,
    messageId: string,
    body?: { sql?: string },
  ): Promise<SqlExecuteResponse> =>
    api.post<SqlExecuteResponse>(
      `/datamart/sessions/${sessionId}/messages/${messageId}/execute`,
      body?.sql ? { sql: body.sql } : undefined,
    ).then((r) => r.data),

  executeMessageBlock: (
    sessionId: string,
    messageId: string,
    blockId: string,
  ): Promise<SqlExecuteResponse> =>
    api.post<SqlExecuteResponse>(
      `/datamart/sessions/${sessionId}/messages/${messageId}/blocks/${encodeURIComponent(blockId)}/execute`
    ).then((r) => r.data),

  putMessageCharts: (
    sessionId: string,
    messageId: string,
    charts: unknown[],
  ): Promise<PutMessageChartsResponse> =>
    api
      .put<PutMessageChartsResponse>(
        `/datamart/sessions/${sessionId}/messages/${messageId}/charts`,
        { charts },
      )
      .then((r) => r.data),

  patchReportMeta: (
    sessionId: string,
    messageId: string,
    body: PatchMessageReportMetaRequest,
  ): Promise<PatchMessageReportMetaResponse> =>
    api
      .patch<PatchMessageReportMetaResponse>(
        `/datamart/sessions/${sessionId}/messages/${messageId}/report-meta`,
        body,
      )
      .then((r) => r.data),

  renameSession: (sessionId: string, title: string): Promise<void> =>
    api.patch(`/datamart/sessions/${sessionId}`, { title }).then(() => undefined),

  moveSessionToGroup: (sessionId: string, groupId: string | null): Promise<void> =>
    api.patch(`/datamart/sessions/${sessionId}/group`, { group_id: groupId }).then(() => undefined),

  deleteSession: (sessionId: string): Promise<void> =>
    api.delete(`/datamart/sessions/${sessionId}`).then(() => undefined),

  // Session groups
  listSessionGroups: (): Promise<SessionGroupListResponse> =>
    api.get<SessionGroupListResponse>('/datamart/session-groups').then((r) => r.data),

  createSessionGroup: (name: string): Promise<SessionGroupResponse> =>
    api.post<SessionGroupResponse>('/datamart/session-groups', { name }).then((r) => r.data),

  renameSessionGroup: (groupId: string, name: string): Promise<void> =>
    api.patch(`/datamart/session-groups/${groupId}`, { name }).then(() => undefined),

  deleteSessionGroup: (groupId: string): Promise<void> =>
    api.delete(`/datamart/session-groups/${groupId}`).then(() => undefined),

  // Templates
  listTemplates: (): Promise<TemplateListResponse> =>
    api.get<TemplateListResponse>('/datamart/templates').then((r) => r.data),

  templateChat: (
    templateId: string,
    question: string,
    followUpMode?: 'continue_last' | 'add_scenario' | 'new_question',
    targetScenarioIds?: string[],
  ): Promise<DatamartResponse> =>
    api
      .post<DatamartResponse>(
        `/datamart/templates/${templateId}/chat`,
        {
          question,
          ...(followUpMode ? { follow_up_mode: followUpMode } : {}),
          ...(targetScenarioIds?.length
            ? { target_scenario_ids: targetScenarioIds }
            : {}),
        },
        { timeout: DATAMART_CHAT_TIMEOUT_MS },
      )
      .then((r) => r.data),

  promoteToTemplate: (name: string, sessionId: string, messageId: string): Promise<TemplateResponse> =>
    api.post<TemplateResponse>('/datamart/templates/promote',
      { name, session_id: sessionId, message_id: messageId }).then((r) => r.data),

  getTemplate: (templateId: string): Promise<TemplateResponse> =>
    api.get<TemplateResponse>(`/datamart/templates/${templateId}`).then((r) => r.data),

  renameTemplate: (templateId: string, name: string): Promise<void> =>
    api.patch(`/datamart/templates/${templateId}`, { name }).then(() => undefined),

  moveTemplateToGroup: (templateId: string, groupId: string | null): Promise<void> =>
    api.patch(`/datamart/templates/${templateId}/group`, { group_id: groupId }).then(() => undefined),

  pinTemplate: (templateId: string): Promise<{ is_pinned: boolean }> =>
    api.patch<{ is_pinned: boolean }>(`/datamart/templates/${templateId}/pin`).then((r) => r.data),

  deleteTemplate: (templateId: string): Promise<void> =>
    api.delete(`/datamart/templates/${templateId}`).then(() => undefined),

  listTemplateVersions: (templateId: string): Promise<TemplateVersionListResponse> =>
    api.get<TemplateVersionListResponse>(`/datamart/templates/${templateId}/versions`).then((r) => r.data),

  executeTemplateVersionSql: (
    templateId: string,
    versionId: string,
    body?: { sql?: string },
  ): Promise<SqlExecuteResponse> =>
    api.post<SqlExecuteResponse>(
      `/datamart/templates/${templateId}/versions/${versionId}/execute`,
      body?.sql ? { sql: body.sql } : undefined,
    ).then((r) => r.data),

  executeTemplateVersionBlock: (
    templateId: string,
    versionId: string,
    blockId: string,
  ): Promise<SqlExecuteResponse> =>
    api
      .post<SqlExecuteResponse>(
        `/datamart/templates/${templateId}/versions/${versionId}/execute-block/${encodeURIComponent(blockId)}`,
      )
      .then((r) => r.data),

  patchTemplateVersionReportMeta: (
    templateId: string,
    versionId: string,
    body: PatchTemplateVersionReportMetaRequest,
  ): Promise<PatchTemplateVersionReportMetaResponse> =>
    api
      .patch<PatchTemplateVersionReportMetaResponse>(
        `/datamart/templates/${templateId}/versions/${versionId}/report-meta`,
        body,
      )
      .then((r) => r.data),

  saveTemplateVersion: (
    templateId: string,
    payload: {
      sql_script: string
      post_process_config?: Array<Record<string, unknown>> | null
      chart_configs?: unknown[] | null
      extra_result_blocks?: TemplateExtraBlockMeta[] | null
      report_layout?: Record<string, unknown> | null
      narrative?: string | null
      label?: string | null
    },
  ): Promise<TemplateVersionResponse> =>
    api.post<TemplateVersionResponse>(`/datamart/templates/${templateId}/versions`, payload).then((r) => r.data),

  // Template groups
  listTemplateGroups: (): Promise<TemplateGroupListResponse> =>
    api.get<TemplateGroupListResponse>('/datamart/template-groups').then((r) => r.data),

  createTemplateGroup: (name: string): Promise<TemplateGroupResponse> =>
    api.post<TemplateGroupResponse>('/datamart/template-groups', { name }).then((r) => r.data),

  renameTemplateGroup: (groupId: string, name: string): Promise<void> =>
    api.patch(`/datamart/template-groups/${groupId}`, { name }).then(() => undefined),

  deleteTemplateGroup: (groupId: string): Promise<void> =>
    api.delete(`/datamart/template-groups/${groupId}`).then(() => undefined),

  // Suggestions
  getSuggestions: (): Promise<SuggestionsResponse> =>
    api.get<SuggestionsResponse>('/datamart/suggestions').then((r) => r.data),
}
