// TS mirror of app/domain/document_spec.py + the ingestion review payload.
// A "document" report renders one page per record (payslip, statement, etc.).
export interface DocumentLine {
  label: string;
  ref: string | null;
}

export interface DocumentSection {
  title: string;
  lines: DocumentLine[];
  total: DocumentLine | null;
}

export interface DocumentDetailBlock {
  title: string;
  provider: string;
  enabled: boolean;
}

export interface DocumentSpec {
  title: string;
  company_name: string | null;
  logo_data_url: string | null;
  value_label: string;
  identity_fields: DocumentLine[];
  sections: DocumentSection[];
  detail_blocks: DocumentDetailBlock[];
  footer: string;
  period_year_ref: string | null;
  period_month_ref: string | null;
  record_key_ref: string | null;
}

export interface DocumentReviewItem {
  label: string;
  section: string;
  role: string;
  ref: string | null;
  confidence: number;
}

export interface DocumentDraft {
  spec: DocumentSpec;
  review: DocumentReviewItem[];
  unmatched: string[];
}

export interface DocumentListItem {
  id: string;
  name: string;
  description?: string;
  category: string;
  doc_type: DocType;
  status: string;
  version_no?: number;
  updated_at?: string | null;
}

// ── Document Studio: canvas design (letters / emails) ────────────────────────
// TS mirror of app/domain/document_design.py.
export type DocType = "letter" | "email" | "report";

export type BlockType =
  | "text" | "field" | "image" | "table" | "divider" | "spacer" | "signature";

export interface DesignColumn {
  ref: string;
  label?: string | null;
  total?: boolean;
}

export interface DesignBlock {
  id: string;
  type: BlockType;
  html?: string | null;          // text: rich HTML w/ {{ref}} tokens
  ref?: string | null;           // field: bound semantic ref
  label?: string | null;
  prefix?: string | null;
  suffix?: string | null;
  src?: string | null;           // image: data URL
  provider?: string | null;      // table: one→many provider
  columns?: DesignColumn[];
  align?: "left" | "center" | "right" | null;
  width_pct?: number | null;
  height_px?: number | null;
  style?: Record<string, string | number>;
}

export interface DesignManualField {
  key: string;
  label: string;
}

// A reusable manual field stored in the tenant's pool (shared across letters).
export interface ManualFieldPoolItem {
  id: string;
  key: string;
  label: string;
}

export interface DocumentDesign {
  page_size: string;
  orientation: "portrait" | "landscape";
  margin_mm: number;
  margin_top?: number | null;
  margin_right?: number | null;
  margin_bottom?: number | null;
  margin_left?: number | null;
  company_name?: string | null;
  header_html?: string | null;
  footer_html?: string | null;
  show_page_numbers?: boolean;
  manual_fields?: DesignManualField[];
  blocks: DesignBlock[];
  period_year_ref?: string | null;
  period_month_ref?: string | null;
  record_key_ref?: string | null;
}

export interface DocumentCategory {
  id: string;
  name: string;
  doc_type: DocType;
}

export interface Letterhead {
  id: string;
  name: string;
  logo_data_url?: string | null;
  header_html: string;
  footer_html: string;
}

export const emptyDesign = (): DocumentDesign => ({
  page_size: "A4",
  orientation: "portrait",
  margin_mm: 20,
  blocks: [],
  // Left unset — the designer picks "One per record" explicitly from the tenant's
  // own catalogue (refs aren't the same across tenants). Required before a letter
  // can be published; see document_service.py's _require_publishable.
  record_key_ref: null,
});

// Manual fields = the explicit list UNION any {{manual.key}} tokens used in the letter
// (blocks/header/footer), so they're never lost even if the saved list isn't persisted.
export function manualFieldsOf(design?: DocumentDesign | null): DesignManualField[] {
  if (!design) return [];
  const explicit = new Map((design.manual_fields ?? []).map((m) => [m.key, m.label]));
  const keys = new Set<string>(explicit.keys());
  const scan = (html?: string | null) => {
    for (const m of (html ?? "").matchAll(/\{\{\s*manual\.([a-z0-9_]+)\s*\}\}/gi)) keys.add(m[1]);
  };
  design.blocks.forEach((b) => scan(b.html));
  scan(design.header_html); scan(design.footer_html);
  const title = (k: string) => k.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  return [...keys].map((k) => ({ key: k, label: explicit.get(k) ?? title(k) }));
}
