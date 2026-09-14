// Typed API client (README §3.3). Wraps axios; injects JWT + acting-tenant header.
import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";
import { getAccessToken, setAccessToken, tokenSupportsRefresh } from "../auth/session";
import { handleAuthFailure, refreshAccessToken } from "../auth/refresh";
import type {
  DataSpec, PresentationSpec, SemanticFieldMeta, QueryResult, ExportFormat, CalculatedField,
} from "../types/spec";
import type {
  DocumentDraft, DocumentSpec, DocumentListItem, DocumentDesign, DocType, DocumentCategory, Letterhead,
  ManualFieldPoolItem,
} from "../types/document";
import type { MetricDef } from "../types/metric";
import type { GlossaryTerm } from "../types/glossary";

const api = axios.create({ baseURL: import.meta.env.VITE_API_BASE ?? "/api/v1" });

api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  const actAs = sessionStorage.getItem("act_as_tenant");
  if (actAs) config.headers["X-Act-As-Tenant"] = actAs;
  return config;
});

type RetryConfig = InternalAxiosRequestConfig & { _retry?: boolean };

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as RetryConfig | undefined;
    const url = original?.url ?? "";
    if (
      error.response?.status !== 401
      || !original
      || original._retry
      || url.includes("/auth/refresh")
    ) {
      if (error.response?.status === 401) {
        await handleAuthFailure();
      }
      return Promise.reject(error);
    }

    if (!tokenSupportsRefresh()) {
      await handleAuthFailure();
      return Promise.reject(error);
    }

    original._retry = true;
    try {
      const token = await refreshAccessToken();
      original.headers.Authorization = `Bearer ${token}`;
      return api(original);
    } catch {
      await handleAuthFailure();
      return Promise.reject(error);
    }
  },
);

export async function login(username: string, password: string): Promise<void> {
  const body = new URLSearchParams({ username, password });
  const { data } = await api.post("/auth/token", body);
  setAccessToken(data.access_token);
}

export interface CoverageField {
  ref: string; label: string; entity: string; table: string; column: string;
  total: number | null; populated: number | null; coverage: number | null; status: string;
}
export interface CoverageReport {
  results: CoverageField[];
  summary: { fields: number; ok: number; empty: number; missing: number; errored: number; data_capture_gaps: string[] };
}
export interface FieldRequest {
  id: string; header: string; note: string | null; status: string; hits: number;
  created_at: string | null; last_requested_at: string | null; resolved_at: string | null;
}
export const validationsApi = {
  // Data-capture coverage audit — how populated is each catalogue field's column.
  coverage: () => api.post<CoverageReport>("/validations/coverage").then((r) => r.data),
  // Data-capture gap list: request a not-yet-available field, list, resolve, remove.
  requestField: (header: string, note?: string) =>
    api.post<FieldRequest>("/validations/field-requests", { header, note }).then((r) => r.data),
  fieldRequests: () =>
    api.get<{ requests: FieldRequest[] }>("/validations/field-requests").then((r) => r.data.requests),
  resolveFieldRequest: (id: string) =>
    api.post<FieldRequest>(`/validations/field-requests/${id}/resolve`).then((r) => r.data),
  deleteFieldRequest: (id: string) =>
    api.delete(`/validations/field-requests/${id}`).then((r) => r.data),
};

export interface Me {
  user_id: string; email: string | null; name: string;
  role: string; designation: string; tenant_id: string; tenant_name: string;
  logo_url?: string | null;
  /** Full true/false map of gated sidebar sections (Templates always visible). */
  nav_sections?: Record<string, boolean>;
}
export const authApi = {
  me: () => api.get<Me>("/auth/me").then((r) => r.data),
};

export interface PlatformTenant {
  subdomain: string;
  pg_schema: string;
  datamart_key: string;
  status: string;
  provisioned_at: string | null;
  provisioned_by: string | null;
  nav_sections: Record<string, boolean>;
}

export interface PlatformTenantsResponse {
  tenants: PlatformTenant[];
  section_keys: string[];
  defaults: Record<string, boolean>;
}

export const platformApi = {
  listTenants: () =>
    api.get<PlatformTenantsResponse>("/platform/tenants").then((r) => r.data),
  getNavSections: (subdomain: string) =>
    api
      .get<{ subdomain: string; nav_sections: Record<string, boolean>; section_keys: string[]; defaults: Record<string, boolean> }>(
        `/platform/tenants/${encodeURIComponent(subdomain)}/nav-sections`,
      )
      .then((r) => r.data),
  patchNavSections: (subdomain: string, sections: Record<string, boolean>) =>
    api
      .patch<{ subdomain: string; nav_sections: Record<string, boolean> }>(
        `/platform/tenants/${encodeURIComponent(subdomain)}/nav-sections`,
        { sections },
      )
      .then((r) => r.data),
};

export const semanticApi = {
  fields: () => api.get<SemanticFieldMeta[]>("/semantic/fields").then((r) => r.data),
  fieldsForBuilder: () => api.get<SemanticFieldMeta[]>("/semantic/fields/builder").then((r) => r.data),
  catalog: () => api.get("/semantic/catalog").then((r) => r.data),
  rebuild: () =>
    api.post<{ version: number; entities: string[]; total_fields: number }>("/semantic/rebuild")
      .then((r) => r.data),
};

export const metricApi = {
  list: () => api.get<MetricDef[]>("/semantic/metrics").then((r) => r.data),
  define: (m: MetricDef) => api.post<MetricDef>("/semantic/metrics", m).then((r) => r.data),
  seedDefaults: () =>
    api.post<{ created: string[] }>("/semantic/metrics/seed-defaults").then((r) => r.data),
};

export const glossaryApi = {
  list: () => api.get<GlossaryTerm[]>("/semantic/glossary").then((r) => r.data),
  define: (t: GlossaryTerm) => api.post<GlossaryTerm>("/semantic/glossary", t).then((r) => r.data),
  seedDefaults: () =>
    api.post<{ created: string[] }>("/semantic/glossary/seed-defaults").then((r) => r.data),
};

// Presentation-layer config a rule report can optionally carry alongside its
// spec — never part of the governed RuleReportSpec itself. See PivotSpec
// (backend/app/domain/report_spec.py).
export interface RulePivotConfig {
  column_field: string;
  value_field: string;
  status_field?: string | null;
  column_label_format?: string | null;
  status_colors?: Record<string, string>;
}
export interface RulePresentationExtras {
  row_number_column?: string | null;
  subtotal?: Record<string, unknown> | null;
  totals?: string[];
  pivot?: RulePivotConfig | null;
}

export const templateApi = {
  list: () => api.get("/templates").then((r) => r.data),
  create: (name: string, module?: string, description?: string) =>
    api.post("/templates", { name, module, description }).then((r) => r.data),
  // Create + publish a governed rule-engine report from a JSON spec.
  // `session_id` (the AI chat session this save came from, if any) lets
  // reopening the report later resume that SAME conversation — see
  // getRuleReportChatSession below.
  createRuleReport: (name: string, spec: unknown, category?: string,
                     labels?: Record<string, string>, export_options?: Record<string, unknown>,
                     description?: string, presentation?: RulePresentationExtras,
                     session_id?: string | null) =>
    api.post<{ template_id: string; version_id: string; name: string }>(
      "/templates/rule-report",
      { name, spec, category, labels, export_options, description, ...presentation, session_id },
    ).then((r) => r.data),
  updateRuleReport: (id: string, name: string, spec: unknown, category?: string,
                     labels?: Record<string, string>,
                     opts?: { new_version?: boolean; note?: string; export_options?: Record<string, unknown>;
                              description?: string; session_id?: string | null } & RulePresentationExtras) =>
    api.put<{ template_id: string; version_id: string; name: string }>(
      `/templates/rule-report/${id}`, { name, spec, category, labels, ...opts },
    ).then((r) => r.data),
  explainRuleReport: (spec: unknown, labels?: Record<string, string>) =>
    api.post<{ sections: { title: string; lines: string[] }[] }>(
      "/templates/rule-report/explain", { spec, labels },
    ).then((r) => r.data),
  // The chat conversation linked to this report (or null — built before this
  // feature, or via raw JSON) — visible tenant-wide, not creator-only.
  getRuleReportChatSession: (id: string) =>
    api.get<{ session: RuleChatSessionDetail | null }>(
      `/templates/rule-report/${id}/chat-session`,
    ).then((r) => r.data.session),
  rename: (id: string, patch: { name?: string; module?: string; description?: string }) =>
    api.patch(`/templates/${id}`, patch).then((r) => r.data),
  saveDraft: (id: string, data_spec: DataSpec, presentation_spec: PresentationSpec) =>
    api.post(`/templates/${id}/draft`, { data_spec, presentation_spec }).then((r) => r.data),
  publish: (id: string, versionId: string) =>
    api.post(`/templates/${id}/versions/${versionId}/publish`).then((r) => r.data),
  rollback: (id: string, versionId: string) =>
    api.post(`/templates/${id}/versions/${versionId}/rollback`).then((r) => r.data),
  versions: (id: string) => api.get(`/templates/${id}/versions`).then((r) => r.data),
  getDraft: (id: string) =>
    api.get<{ name: string; module: string; description?: string | null; data_spec: DataSpec; presentation_spec: PresentationSpec }>(
      `/templates/${id}/draft`,
    ).then((r) => r.data),
  remove: (id: string) => api.delete<{ deleted: string }>(`/templates/${id}`).then((r) => r.data),
  // Source file (the uploaded Excel) — stored ENCRYPTED server-side so the exact
  // sheet can be previewed when editing the template.
  uploadSourceFile: (id: string, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return api.put<{ template_id: string; filename: string; size_bytes: number }>(
      `/templates/${id}/source-file`, fd,
    ).then((r) => r.data);
  },
  sourceFileMeta: (id: string) =>
    api.get<{ exists: boolean; filename?: string; content_type?: string; size_bytes?: number }>(
      `/templates/${id}/source-file/meta`,
    ).then((r) => r.data),
  sourceFile: (id: string) =>
    api.get(`/templates/${id}/source-file`, { responseType: "blob" }).then((r) => r.data as Blob),
  removeSourceFile: (id: string) =>
    api.delete<{ deleted: string }>(`/templates/${id}/source-file`).then((r) => r.data),
};

// Legacy SQL Converter — a standalone migration helper (isolated from the
// Rule Report chat/DSL engine, see backend/app/services/legacy_sql_converter).
// Paste an old report's SQL, get a business-logic document to paste into the
// AI Rule Report chat as a requirement. One-shot; no session history.
export const legacySqlConverterApi = {
  analyze: (sql: string) =>
    api.post<{ document: string }>("/legacy-sql/analyze", { sql }).then((r) => r.data.document),
};

// AI-assisted Rule Report chat (Claude Code) — upload a requirement doc + a
// sample sheet, then iterate to a validated RuleReportSpec JSON.
export interface RuleChatSession {
  id: string; title: string; message_count: number;
  updated_at: string | null; created_at: string | null;
}
export interface RuleChatAttachment {
  kind: "requirement_doc" | "sample_sheet" | "source_sql";
  filename: string;
}
export interface RuleChatMessage extends RulePresentationExtras {
  role: "you" | "assistant";
  text: string;
  attachments?: RuleChatAttachment[];
  spec?: Record<string, unknown> | null;
}
export interface RuleChatSessionDetail extends RuleChatSession {
  messages: RuleChatMessage[];
  working_rule_spec: Record<string, unknown> | null;
  sample_sheet_filename: string | null;
  source_sql_filename: string | null;
}
export interface RuleChatTurnResult extends RuleChatSession, RulePresentationExtras {
  reply: string;
  spec: Record<string, unknown> | null;
}
export const ruleChatApi = {
  createSession: (title?: string) =>
    api.post<RuleChatSession>("/ai/rule-chat/sessions", { title }).then((r) => r.data),
  listSessions: () =>
    api.get<{ sessions: RuleChatSession[] }>("/ai/rule-chat/sessions").then((r) => r.data.sessions),
  getSession: (id: string) =>
    api.get<RuleChatSessionDetail>(`/ai/rule-chat/sessions/${id}`).then((r) => r.data),
  deleteSession: (id: string) =>
    api.delete<{ deleted: boolean }>(`/ai/rule-chat/sessions/${id}`).then((r) => r.data),
  sendMessage: (
    id: string, message: string,
    files?: { requirementDoc?: File | null; sampleSheet?: File | null; sourceSql?: File | null },
  ) => {
    const fd = new FormData();
    fd.append("message", message);
    if (files?.requirementDoc) fd.append("requirement_doc", files.requirementDoc);
    if (files?.sampleSheet) fd.append("sample_sheet", files.sampleSheet);
    if (files?.sourceSql) fd.append("source_sql", files.sourceSql);
    return api.post<RuleChatTurnResult>(`/ai/rule-chat/sessions/${id}/messages`, fd)
      .then((r) => r.data);
  },
};

// AI-assisted Excel-mapping chat (same Claude Code technique as ruleChatApi,
// much smaller surface) — finishes mapping the columns ExcelUpload's
// automatic pass couldn't resolve. Deliberately minimal: create + send only,
// no list/get/delete — nothing browses this history outside the upload screen.
export interface ExcelMappingChatSession { id: string; title: string; }
export interface ExcelMappingProposal { header: string; ref: string | null }
export interface ExcelMappingChatMessage {
  role: "you" | "assistant";
  text: string;
  mappings?: ExcelMappingProposal[] | null;
}
export interface ExcelMappingChatTurnResult {
  reply: string;
  mappings: ExcelMappingProposal[] | null;
}
export const excelMappingChatApi = {
  createSession: (title?: string) =>
    api.post<ExcelMappingChatSession>("/ai/excel-mapping-chat/sessions", { title }).then((r) => r.data),
  sendMessage: (
    id: string, message: string, headers: string[], currentMapping: Record<string, string | null>,
  ) =>
    api.post<ExcelMappingChatTurnResult>(`/ai/excel-mapping-chat/sessions/${id}/messages`, {
      message, headers, current_mapping: currentMapping,
    }).then((r) => r.data),
};

export interface RuntimeFilter {
  param: string; ref: string | null; op: string | null; label: string;
  type: string; role: string; required: boolean; enum_values: string[] | null;
}

export interface DataQuality {
  checks?: number;
  passed?: number;
  failed?: number;
  errored?: number;
  critical_failure?: boolean;
}

export interface ViewMeta {
  kind: "report" | "document" | "rule_report";
  allowed_formats: string[]; // subset of "view" | "excel" | "pdf"
  filters: RuntimeFilter[];
  data_quality?: DataQuality; // WS-3 serve policy
  labels?: Record<string, string>; // rule reports: friendly column titles
  columns?: string[]; // rule reports: output column order
}

export const reportApi = {
  run: (id: string, params: Record<string, unknown> = {}) =>
    api.post<QueryResult>(`/reports/${id}/run`, { params }).then((r) => r.data),
  meta: (id: string) =>
    api.get<{ filters: RuntimeFilter[] }>(`/reports/${id}/meta`).then((r) => r.data.filters),
  viewMeta: (id: string) =>
    api.get<ViewMeta>(`/reports/${id}/meta`).then((r) => r.data),
  fieldValues: (id: string, ref: string) =>
    api.get<{ values: unknown[] }>(`/reports/${id}/field-values`, { params: { ref } }).then((r) => r.data.values),
  previewSpec: (data_spec: DataSpec, params: Record<string, unknown> = {}) =>
    api.post<QueryResult>("/reports/preview-spec", { data_spec, params }).then((r) => r.data),
};

export const aiApi = {
  naturalLanguage: (request: string) =>
    api.post("/ai/natural-language", { request }).then((r) => r.data),
  adjust: (instruction: string, current_spec: DataSpec) =>
    api.post("/ai/adjust", { instruction, current_spec }).then((r) => r.data),
  // Conversational turn — always 200: either a report (kind="report" + data_spec)
  // or a plain reply (kind="reply") for greetings / help / off-topic / graceful fail.
  chat: (
    message: string, current_spec?: DataSpec,
    context?: { columns: string[]; rows: Record<string, unknown>[]; prompt?: string },
  ) =>
    api.post<{
      kind: "report" | "reply" | "clarify"; message: string; data_spec?: DataSpec | null; source?: string;
      mapping?: {
        matched: { phrase: string; ref: string; label: string; score: number }[];
        unmatched: string[]; filters: string[]; confidence: number;
      } | null;
      options?: string[] | null;  // clarify: suggested follow-ups to click
      // Data gaps explained in business language (fields asked for but not in a mart).
      gaps?: { term: string; status: "in_source" | "not_captured"; message: string }[] | null;
    }>("/ai/chat", { message, current_spec, context }).then((r) => r.data),
  excelMapping: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return api.post("/ai/excel-mapping", fd).then((r) => r.data);
  },
  // Remember a header -> field mapping the user confirmed/corrected, so the same
  // heading auto-maps correctly on the next upload (ref null = remembered skip).
  rememberColumnMapping: (header: string, ref: string | null) =>
    api.post("/ai/column-mappings", { header, ref }).then((r) => r.data),
  // Rank the best candidate fields for a column that didn't auto-map.
  suggestFields: (header: string, limit = 3) =>
    api.post<{ suggestions: { ref: string; label: string; score: number; reason: string }[] }>(
      "/ai/suggest-fields", { header, limit },
    ).then((r) => r.data.suggestions),
  // Business-language explanation for unmatched headings (collected-not-in-reports
  // vs not-captured) — the same drill-down the chat uses, batched for the Excel flow.
  explainGaps: (terms: string[]) =>
    api.post<{ gaps: { term: string; status: "in_source" | "not_captured"; message: string }[] }>(
      "/ai/explain-gaps", { terms },
    ).then((r) => r.data.gaps),
  // Drill down the datamart layers to LOCATE a concept that isn't in a report mart.
  discover: (term: string) =>
    api.post<{
      term: string; in_report_layer: boolean; summary: string;
      matches: { schema: string; table: string; column: string; layer: string; score: number; guidance: string }[];
    }>("/ai/discover", { term }).then((r) => r.data),
  // Plain-language / rough formula -> a governed CalculatedField (no SQL).
  deriveField: (description: string, label?: string) =>
    api.post<{ calculated_field: CalculatedField }>("/ai/derive-field", { description, label })
      .then((r) => r.data.calculated_field),
  // Physical columns of a Rule Report spec's `source` (e.g. "mart.mart_attendance_daily")
  // — powers the Filters/Add-column pickers so a single-source spec gets a real
  // dropdown instead of blind typing (multi-source specs already list their own columns).
  sourceColumns: (source: string) =>
    api.get<{ columns: { column: string; type: string }[] }>(
      "/ai/source-columns", { params: { source } },
    ).then((r) => r.data.columns),
};

// Persisted chat history (ChatGPT-style). Stored results are immutable snapshots:
// reopening a session returns the saved rows, never a fresh query.
export interface ChatSessionHead {
  id: string; title: string; message_count: number;
  updated_at: string | null; created_at: string | null;
}
export interface StoredMsg {
  role: "you" | "assistant" | "error" | "result";
  text?: string; source?: string; mapping?: unknown;
  result?: QueryResult; tookMs?: number;
}
export const chatSessionApi = {
  create: (title?: string) =>
    api.post<ChatSessionHead>("/ai/sessions", { title }).then((r) => r.data),
  list: () =>
    api.get<{ sessions: ChatSessionHead[] }>("/ai/sessions").then((r) => r.data.sessions),
  get: (id: string) =>
    api.get<ChatSessionHead & { messages: StoredMsg[]; working_data_spec: DataSpec | null }>(
      `/ai/sessions/${id}`,
    ).then((r) => r.data),
  append: (id: string, messages: StoredMsg[], working_data_spec?: DataSpec) =>
    api.post<ChatSessionHead>(`/ai/sessions/${id}/messages`, { messages, working_data_spec })
      .then((r) => r.data),
  rename: (id: string, title: string) =>
    api.patch<ChatSessionHead>(`/ai/sessions/${id}`, { title }).then((r) => r.data),
  remove: (id: string) => api.delete(`/ai/sessions/${id}`).then((r) => r.data),
};

export interface AIConfigPublic {
  provider: string;
  model: string;
  base_url: string | null;
  enabled: boolean;
  has_api_key: boolean;
  api_key_hint: string;
  source: "tenant" | "system" | "env-default";
}

export const aiConfigApi = {
  get: () => api.get<AIConfigPublic>("/ai/config").then((r) => r.data),
  // api_key is write-only; omit it to keep the existing stored key.
  save: (body: {
    provider: string;
    model: string;
    api_key?: string;
    base_url?: string | null;
    enabled?: boolean;
  }) => api.put<AIConfigPublic>("/ai/config", body).then((r) => r.data),
  test: () => api.post<{ ok: boolean; message: string }>("/ai/config/test").then((r) => r.data),
};

export const exportApi = {
  download: async (id: string, format: ExportFormat, params: Record<string, unknown> = {}) => {
    const res = await api.post(`/exports/${id}`, { params, format }, { responseType: "blob" });
    const url = URL.createObjectURL(res.data);
    const a = document.createElement("a");
    a.href = url;
    a.download = `report_${id}.${format}`;
    a.click();
    URL.revokeObjectURL(url);
  },
};

export type DocSaveBody = {
  name: string;
  doc_type: DocType;
  category: string;
  document?: DocumentSpec | null;   // report-doc
  design?: DocumentDesign | null;   // letter / email
  subject?: string | null;          // email
  publish: boolean;
  allowed_formats?: string[];
};
type SaveResult = { template_id: string; version_id: string; version_no: number; status: string };

export interface DocDetail {
  id: string; name: string; category: string; doc_type: DocType; status: string;
  allowed_formats: string[];
  document: DocumentSpec | null;
  design: DocumentDesign | null;
  email_subject: string;
}

export interface DocPreview {
  doc_type: DocType; html: string; subject?: string; record_count: number; period?: string | null;
}

export const documentApi = {
  // Upload a per-record layout Excel -> draft spec + per-line review.
  ingest: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return api.post<DocumentDraft>("/documents/ingest", fd).then((r) => r.data);
  },
  create: (body: DocSaveBody) => api.post<SaveResult>("/documents", body).then((r) => r.data),
  // Upload a sample letter (Word/PDF/image/Excel) -> a canvas design with data lines
  // auto-mapped to {{tokens}} for review. Deterministic + instant. Only labels are read.
  designFromSample: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return api.post<{
      design: DocumentDesign;
      review: { label: string; ref: string; confidence: number }[];
      unmatched: string[];
    }>("/documents/design/from-sample", fd).then((r) => r.data);
  },
  // Deterministic: bind leftover Word «Field» names via the catalogue matcher.
  mapWordFields: (design: DocumentDesign) =>
    api.post<{
      design: DocumentDesign;
      review: { label: string; ref: string; confidence: number }[];
      unmatched: string[];
    }>("/documents/design/map-word-fields", { design }).then((r) => r.data),
  // Opt-in: map remaining dynamic values in the current design with the AI (slower).
  aiEnhance: (design: DocumentDesign) =>
    api.post<{
      design: DocumentDesign;
      review: { label: string; ref: string; confidence: number }[];
      unmatched: string[];
    }>("/documents/design/ai-enhance", { design }).then((r) => r.data),
  list: (docType?: DocType) =>
    api.get<{ documents: DocumentListItem[] }>("/documents", {
      params: docType ? { doc_type: docType } : undefined,
    }).then((r) => r.data.documents),
  get: (id: string) => api.get<DocDetail>(`/documents/${id}`).then((r) => r.data),
  update: (id: string, body: DocSaveBody) =>
    api.put<SaveResult>(`/documents/${id}`, body).then((r) => r.data),
  duplicate: (id: string) =>
    api.post<SaveResult>(`/documents/${id}/duplicate`).then((r) => r.data),
  setStatus: (id: string, status: "active" | "inactive" | "archived" | "draft") =>
    api.patch<{ id: string; status: string }>(`/documents/${id}/status`, { status }).then((r) => r.data),
  // In-browser preview for letter/email (composed HTML + substituted subject).
  preview: (
    id: string,
    body: { year?: number | null; month?: number | null; record_key?: string | null; labelled?: boolean; manual?: Record<string, string> } = {},
  ) => api.post<DocPreview>(`/documents/${id}/preview`, body).then((r) => r.data),
  // Render a document (a page per record) as PDF or editable Word, then download it.
  render: async (
    id: string,
    body: { year?: number | null; month?: number | null; record_key?: string | null; max_records?: number | null; manual?: Record<string, string>; fmt?: "pdf" | "docx" },
  ) => {
    const fmt = body.fmt === "docx" ? "docx" : "pdf";
    const res = await api.post(`/documents/${id}/render`, { ...body, fmt }, { responseType: "blob" });
    const url = URL.createObjectURL(res.data);
    const a = document.createElement("a");
    a.href = url;
    a.download = `document_${id}.${fmt}`;
    a.click();
    URL.revokeObjectURL(url);
  },
  // Per-tenant, per-type categories.
  categories: (docType: DocType) =>
    api.get<{ categories: DocumentCategory[] }>("/documents/categories", {
      params: { doc_type: docType },
    }).then((r) => r.data.categories),
  createCategory: (docType: DocType, name: string) =>
    api.post<DocumentCategory>("/documents/categories", { doc_type: docType, name }).then((r) => r.data),
  renameCategory: (id: string, name: string) =>
    api.patch<DocumentCategory>(`/documents/categories/${id}`, { name }).then((r) => r.data),
  deleteCategory: (id: string) =>
    api.delete<{ deleted: string }>(`/documents/categories/${id}`).then((r) => r.data),
  // Per-tenant letterhead presets (logo + header + footer).
  letterheads: () =>
    api.get<{ letterheads: Letterhead[] }>("/documents/letterheads").then((r) => r.data.letterheads),
  createLetterhead: (body: Omit<Letterhead, "id">) =>
    api.post<Letterhead>("/documents/letterheads", body).then((r) => r.data),
  updateLetterhead: (id: string, body: Partial<Omit<Letterhead, "id">>) =>
    api.patch<Letterhead>(`/documents/letterheads/${id}`, body).then((r) => r.data),
  deleteLetterhead: (id: string) =>
    api.delete<{ deleted: string }>(`/documents/letterheads/${id}`).then((r) => r.data),
  // Per-tenant reusable pool of manual fields (shared across letters, tenant-scoped).
  manualFields: () =>
    api.get<{ manual_fields: ManualFieldPoolItem[] }>("/documents/manual-fields").then((r) => r.data.manual_fields),
  createManualField: (label: string, key?: string) =>
    api.post<ManualFieldPoolItem>("/documents/manual-fields", { label, key }).then((r) => r.data),
  deleteManualField: (id: string) =>
    api.delete<{ deleted: string }>(`/documents/manual-fields/${id}`).then((r) => r.data),
};

export default api;
