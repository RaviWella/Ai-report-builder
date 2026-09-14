// Author a governed rule-engine report from a JSON spec (for rule-heavy reports
// the visual builder can't express — day-type classification, thresholds, etc.).
// The spec is validated server-side; on save it runs + exports like any report.
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Alert, Autocomplete, Box, Button, Card, CardContent, Chip, CircularProgress, Collapse,
  Dialog, DialogActions, DialogContent, DialogTitle, FormControlLabel, IconButton, MenuItem,
  Stack, Switch, Tab, Tabs, TextField, Tooltip, Typography,
} from "@mui/material";
import {
  PlayArrow, DataObjectOutlined, ScienceOutlined, ViewColumnOutlined, FilterAltOutlined,
  ArrowUpward, ArrowDownward, DragIndicator, Close, Add, AutoStoriesOutlined,
  MenuBookOutlined, NoteAddOutlined, ExpandMore, ExpandLess, ContentCopyOutlined, Check,
  HistoryOutlined, ReplayOutlined, ArticleOutlined, AutoAwesome,
} from "@mui/icons-material";
import { aiApi, templateApi, type RulePivotConfig, type RuleChatMessage } from "../../api/client";
import { REPORT_MODULES } from "../../store/builderStore";
import RuleReportAIChat from "./RuleReportAIChat";

// Plain-language operators + input types — same vocabulary as the normal builder's
// filter panel, so a rule report feels like one product, not a second concept.
const OPS = [
  { v: "eq", label: "is" }, { v: "neq", label: "is not" },
  { v: "gt", label: "greater than" }, { v: "lt", label: "less than" },
  { v: "gte", label: "at least (from)" }, { v: "lte", label: "at most (to)" },
  { v: "contains", label: "contains" },
] as const;
const FTYPES = [
  { v: "date", label: "Date" }, { v: "string", label: "Text" }, { v: "number", label: "Number" },
] as const;

interface RuleFilter {
  name: string; type: string; required?: boolean; label?: string; column?: string; op?: string;
}
interface RuleSpec { output?: string[]; filters?: RuleFilter[]; [k: string]: unknown; }

const slug = (s: string) =>
  s.trim().toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "") || "filter";

/** Default heading when the builder hasn't set a custom label yet. */
const prettyColName = (key: string) =>
  key.replace(/_/g, " ").replace(/\b\w/g, (m) => m.toUpperCase());

/** Friendly titles to persist — skip blanks and keys left at the default heading. */
function columnLabelsForSave(cols: string[], labels: Record<string, string>): Record<string, string> {
  const out: Record<string, string> = {};
  for (const c of cols) {
    const title = (labels[c] ?? "").trim();
    if (title && title !== c && title !== prettyColName(c)) out[c] = title;
  }
  return out;
}

/** Text shown in the heading field — saved custom title or the default pretty name. */
function columnHeadingValue(col: string, labels: Record<string, string>): string {
  if (col in labels) return labels[col];
  return prettyColName(col);
}

/** Resolved heading per output column — used for explain/preview before save. */
function effectiveColumnLabels(cols: string[], labels: Record<string, string>): Record<string, string> {
  const out: Record<string, string> = {};
  for (const c of cols) {
    const title = (labels[c] ?? "").trim();
    out[c] = title || prettyColName(c);
  }
  return out;
}

/** Replace a bare identifier inside a governed rule expression string. */
function replaceIdentInExpr(expr: string, from: string, to: string): string {
  if (!expr || from === to) return expr;
  const re = new RegExp(`\\b${from.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`, "g");
  return expr.replace(re, to);
}

function replaceInRowValue(rv: Record<string, unknown> | undefined, from: string, to: string) {
  if (!rv) return;
  const cases = rv.cases as Array<{ when?: string; value?: string }> | undefined;
  cases?.forEach((c) => {
    if (c.when) c.when = replaceIdentInExpr(c.when, from, to);
    if (c.value) c.value = replaceIdentInExpr(c.value, from, to);
  });
  if (typeof rv.else === "string") rv.else = replaceIdentInExpr(rv.else, from, to);
  if (typeof rv.else_value === "string") rv.else_value = replaceIdentInExpr(rv.else_value, from, to);
  const define = rv.define as Record<string, string> | undefined;
  if (define) {
    for (const k of Object.keys(define)) define[k] = replaceIdentInExpr(define[k], from, to);
  }
}

function replaceStringList(list: unknown, from: string, to: string): string[] | undefined {
  if (!Array.isArray(list)) return undefined;
  return list.map((x) => (typeof x === "string" && x === from ? to : x)) as string[];
}

function replaceInDictExprs(dict: Record<string, string> | undefined, from: string, to: string) {
  if (!dict) return;
  for (const k of Object.keys(dict)) dict[k] = replaceIdentInExpr(dict[k], from, to);
}

const ROLLUP_INNER_RESERVED = new Set(["row_value", "day_value"]);

/** Rollups like `max(full_name)` — one mart field aggregated per grain group. */
function parseSimpleAttributeRollup(expr: string): { agg: string; sourceCol: string } | null {
  const m = expr.trim().match(/^(max|min|any|sum|avg|count)\(([a-z_][a-z0-9_]*)\)(?:\s+where\s+.+)?$/i);
  if (!m) return null;
  const sourceCol = m[2];
  if (ROLLUP_INNER_RESERVED.has(sourceCol)) return null;
  return { agg: m[1].toLowerCase(), sourceCol };
}

type ColumnKind = "grain" | "attribute_rollup" | "row_case" | "calculated";

function columnKind(col: string, spec: RuleSpec | null): ColumnKind {
  if (!spec) return "calculated";
  const grain = spec.grain as string[] | undefined;
  if (grain?.includes(col)) return "grain";
  const rowCases = spec.row_cases as Record<string, unknown> | undefined;
  if (rowCases && col in rowCases) return "row_case";
  const rollup = spec.rollup as Record<string, string> | undefined;
  if (rollup?.[col] && parseSimpleAttributeRollup(rollup[col])) return "attribute_rollup";
  return "calculated";
}

/** The mart field that feeds this output column (grain key or rollup inner ref). */
function martColumnForOutput(col: string, spec: RuleSpec | null): string {
  if (!spec) return col;
  if (columnKind(col, spec) === "attribute_rollup") {
    const rollup = spec.rollup as Record<string, string>;
    return parseSimpleAttributeRollup(rollup[col])!.sourceCol;
  }
  return col;
}

function usesAttributeRollupPattern(spec: RuleSpec): boolean {
  const rollup = spec.rollup as Record<string, string> | undefined;
  if (!rollup) return false;
  return Object.values(rollup).some((v) => parseSimpleAttributeRollup(v) !== null);
}

function wireSourceColumn(s: RuleSpec, col: string) {
  const srcs = s.sources as Record<string, { columns?: string[] }> | undefined;
  if (!srcs) return;
  const inSome = Object.values(srcs).some((src) => (src.columns ?? []).includes(col));
  if (!inSome) {
    const base = Object.keys(srcs)[0];
    srcs[base].columns = [...(srcs[base].columns ?? []), col];
  }
}

/** Replace a mart field everywhere it is referenced — without renaming rollup/compute keys. */
function replaceMartFieldRefs(root: Record<string, unknown>, oldMart: string, newMart: string) {
  if (oldMart === newMart) return;
  const s = root as RuleSpec;
  s.grain = replaceStringList(s.grain, oldMart, newMart) ?? (s.grain as string[]);
  s.order_by = replaceStringList(s.order_by, oldMart, newMart);
  replaceInRowValue(root.row_value as Record<string, unknown> | undefined, oldMart, newMart);
  replaceInRowValue(root.day_value as Record<string, unknown> | undefined, oldMart, newMart);
  const rowCases = root.row_cases as Record<string, Record<string, unknown>> | undefined;
  if (rowCases) for (const block of Object.values(rowCases)) replaceInRowValue(block, oldMart, newMart);
  replaceInDictExprs(s.rollup as Record<string, string> | undefined, oldMart, newMart);
  replaceInDictExprs(s.compute as Record<string, string> | undefined, oldMart, newMart);
  if (typeof s.having === "string") s.having = replaceIdentInExpr(s.having, oldMart, newMart);
  (s.filters as RuleFilter[] | undefined)?.forEach((f) => {
    if (f.column === oldMart) f.column = newMart;
  });
  const srcs = s.sources as Record<string, { columns?: string[] }> | undefined;
  if (srcs) {
    let ownerKey: string | null = null;
    for (const [alias, src] of Object.entries(srcs)) {
      if ((src.columns ?? []).includes(oldMart)) ownerKey = alias;
    }
    for (const src of Object.values(srcs)) {
      if ((src.columns ?? []).includes(oldMart)) {
        src.columns = src.columns!.map((c) => (c === oldMart ? newMart : c));
      }
    }
    const target = ownerKey ? srcs[ownerKey] : srcs[Object.keys(srcs)[0]];
    if (target && !(target.columns ?? []).includes(newMart)) {
      target.columns = [...(target.columns ?? []), newMart];
    }
  }
  if (root.row_number_column === oldMart) root.row_number_column = newMart;
  root.totals = replaceStringList(root.totals, oldMart, newMart);
  const sub = root.subtotal as { group_by?: string[]; sum_columns?: string[]; label_column?: string } | undefined;
  if (sub) {
    sub.group_by = replaceStringList(sub.group_by, oldMart, newMart);
    sub.sum_columns = replaceStringList(sub.sum_columns, oldMart, newMart);
    if (sub.label_column === oldMart) sub.label_column = newMart;
  }
  const pivot = root.pivot as RulePivotConfig | undefined;
  if (pivot) {
    if (pivot.column_field === oldMart) pivot.column_field = newMart;
    if (pivot.value_field === oldMart) pivot.value_field = newMart;
    if (pivot.status_field === oldMart) pivot.status_field = newMart;
  }
}

// The plain-language explanation is generated on the BACKEND (Python `ast` + inflect)
// so it accurately paraphrases any spec — fetched via templateApi.explainRuleReport.
interface ExplainSection { title: string; lines: string[]; }
interface VersionRow { id: string; version_no: number; status: string; created_at: string | null; note?: string; is_current?: boolean; }

// A GENERIC scaffold — the common SHAPE every rule report follows, with all sections
// and the usual filters. Everything table/field-specific is a <placeholder> to replace
// with your own table and columns — the engine reads ANY warehouse table, not one
// report's. Section names (base, row_type, total_value…) are examples you can rename.
const TEMPLATE = {
  name: "my_report",
  sources: {
    a: {
      table: "<schema.table>",
      columns: ["<id_field>", "<period_field>", "<date_field>", "<value_field>", "<flag_field>"],
    },
  },
  grain: ["<id_field>", "<period_field>"],
  constants: { example_number: 6 },
  row_value: {
    define: { base: "coalesce(<value_field>, 0)" },
    cases: [
      { when: "<flag_field> > 0", value: "0" },
    ],
    else: "base",
  },
  row_cases: {
    row_type: {
      cases: [
        { when: "<flag_field> > 0", value: "'type_a'" },
      ],
      else: "'type_b'",
    },
  },
  rollup: {
    my_total: "sum(row_value)",
    my_count: "count(row_value) where row_type == 'type_b'",
  },
  compute: {
    my_result: "my_total * example_number",
  },
  output: ["<id_field>", "<period_field>", "my_total", "my_count", "my_result"],
  filters: [
    { name: "date_from", type: "date", required: true, label: "From", column: "<date_field>", op: "gte" },
    { name: "date_to", type: "date", required: true, label: "To", column: "<date_field>", op: "lte" },
  ],
};

// The bare minimum shape — one source, one day-rule, one total. Replace the
// <placeholders> with your table and fields.
const SKELETON = {
  name: "my_report",
  sources: {
    a: { table: "<schema.table>", columns: ["<id_field>", "<period_field>", "<date_field>", "<value_field>"] },
  },
  grain: ["<id_field>", "<period_field>"],
  constants: {},
  row_value: { cases: [{ when: "<value_field> > 0", value: "<value_field>" }], else: "0" },
  rollup: { my_total: "sum(row_value)" },
  compute: {},
  output: ["<id_field>", "<period_field>", "my_total"],
  filters: [
    { name: "date_from", type: "date", required: true, label: "From", column: "<date_field>", op: "gte" },
    { name: "date_to", type: "date", required: true, label: "To", column: "<date_field>", op: "lte" },
  ],
};

// One-line, plain-language guide to each section — shown next to the editor (JSON has
// no comments, so the guidance lives here).
const GUIDE: [string, string][] = [
  ["sources", "Which warehouse tables to read — and how they join."],
  ["grain", "One row per… e.g. employee per period."],
  ["constants", "Fixed numbers you reuse in the formulas."],
  ["row_value", "For each source row: work out its value (classify it, pick a number)."],
  ["row_cases", "Optional per-row labels (e.g. a category) used for breakdown columns."],
  ["rollup", "What to add up per group — totals and counts."],
  ["compute", "The final formulas over the totals (e.g. net = total − deductions)."],
  ["output", "Which columns appear, in order."],
  ["filters", "What the user picks before running (dates, an id…)."],
];

export function RuleReportBuilder() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const { templateId } = useParams();
  const editing = Boolean(templateId);
  const [category, setCategory] = useState<string>("Attendance");
  // The template's own description (shown on the Templates list card) — distinct
  // from exportOpts.description below, which only prints on the Excel/PDF header.
  const [description, setDescription] = useState("");
  // A new report opens pre-filled with the generic template (all sections + filters);
  // editing loads the saved spec below.
  const [json, setJson] = useState(editing ? "" : JSON.stringify(TEMPLATE, null, 2));
  const [labels, setLabels] = useState<Record<string, string>>({});
  const [exportOpts, setExportOpts] = useState<{ description: string; show_company: boolean; show_meta: boolean }>(
    { description: "", show_company: false, show_meta: false });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(editing);
  const [copied, setCopied] = useState(false);
  const [newCol, setNewCol] = useState("");
  const [verDlg, setVerDlg] = useState(false);
  const [verNote, setVerNote] = useState("");
  // The AI chat session that built/last edited this report (if any) — resumed
  // in the "AI helper" tab instead of starting blank, and recorded again on
  // every save so the link survives further edits. `chatSessionId` is the
  // CURRENTLY active one (seeded from the report, then kept in sync by the
  // chat itself via onSessionChange); `initial*` seed the chat once on load.
  const [chatSessionId, setChatSessionId] = useState<string | null>(null);
  const [initialChatSessionId, setInitialChatSessionId] = useState<string | null>(null);
  const [initialChatMessages, setInitialChatMessages] = useState<RuleChatMessage[]>([]);
  const [versions, setVersions] = useState<VersionRow[]>([]);
  const [versOpen, setVersOpen] = useState(false);

  // Edit mode: load the existing rule report (spec + name + category + column titles).
  const loadReport = useCallback(async (id: string) => {
    setLoading(true);
    setErr("");
    try {
      const [session, d] = await Promise.all([
        templateApi.getRuleReportChatSession(id).catch(() => null),
        templateApi.getDraft(id),
      ]);
      if (session) {
        setChatSessionId(session.id);
        setInitialChatSessionId(session.id);
        setInitialChatMessages(session.messages);
      } else {
        setChatSessionId(null);
        setInitialChatSessionId(null);
        setInitialChatMessages([]);
      }
      const ps = d.presentation_spec as unknown as {
        spec?: Record<string, unknown>; labels?: Record<string, string>;
        export_options?: { description?: string; show_company?: boolean; show_meta?: boolean };
        row_number_column?: string; subtotal?: Record<string, unknown>;
        totals?: string[]; pivot?: RulePivotConfig;
      };
      setName(d.name ?? "");
      setCategory(d.module ?? "Attendance");
      setDescription(d.description ?? "");
      if (ps?.spec) {
        const merged: Record<string, unknown> = { ...ps.spec };
        if (ps.row_number_column) merged.row_number_column = ps.row_number_column;
        if (ps.subtotal) merged.subtotal = ps.subtotal;
        if (ps.totals?.length) merged.totals = ps.totals;
        if (ps.pivot) merged.pivot = ps.pivot;
        setJson(JSON.stringify(merged, null, 2));
      } else {
        setJson("");
      }
      setLabels(ps?.labels ?? {});
      const eo = ps?.export_options ?? {};
      setExportOpts({ description: eo.description ?? "", show_company: !!eo.show_company, show_meta: !!eo.show_meta });
      (templateApi.versions(id) as Promise<VersionRow[]>).then(setVersions).catch(() => {});
    } catch {
      setErr("Couldn’t load this report for editing.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!templateId) { setLoading(false); return; }
    loadReport(templateId);
  }, [templateId, loadReport]);

  // Browser back/forward cache can restore a stale React tree — re-fetch on show.
  useEffect(() => {
    const onPageShow = (e: PageTransitionEvent) => {
      if (e.persisted && templateId) loadReport(templateId);
    };
    window.addEventListener("pageshow", onPageShow);
    return () => window.removeEventListener("pageshow", onPageShow);
  }, [templateId, loadReport]);

  const useVersion = async (vid: string) => {
    if (!templateId) return;
    try { await templateApi.rollback(templateId, vid); navigate(`/viewer/r/${templateId}`); }
    catch { setErr("Couldn’t switch to that version."); }
  };

  // The JSON is the single source of truth. The visual Columns/Filters panels below
  // read it and write straight back into it (so the spec stays consistent and the
  // change is visible) — same idea as the normal builder, just governed by the spec.
  const spec = useMemo<RuleSpec | null>(() => {
    try { return JSON.parse(json) as RuleSpec; } catch { return null; }
  }, [json]);
  const cols: string[] = Array.isArray(spec?.output)
    ? spec!.output!.filter((c): c is string => typeof c === "string") : [];
  const displayLabels = useMemo(() => effectiveColumnLabels(cols, labels), [cols, labels]);
  const filters: RuleFilter[] = Array.isArray(spec?.filters) ? spec!.filters! : [];
  // Drop labels for columns removed via JSON edit (not only the Columns panel).
  useEffect(() => {
    setLabels((prev) => {
      const next = Object.fromEntries(Object.entries(prev).filter(([k]) => cols.includes(k)));
      return Object.keys(next).length === Object.keys(prev).length ? prev : next;
    });
  }, [cols]);
  // The physical columns a filter/output column can map to — populates the pickers so
  // the user chooses instead of guessing a name (same "pick, don't type blind" UX the
  // Excel Upload panel's field picker already has). Multi-source specs declare their
  // own columns inline; the common single-`source` shape doesn't, so those are fetched
  // live from the datamart (best-effort — while loading/on error this is just [],
  // same as before this existed, never a hard requirement to type a column).
  const singleSource = typeof spec?.source === "string" && !spec?.sources ? (spec.source as string) : null;
  const { data: liveSourceCols = [] } = useQuery({
    queryKey: ["rule-source-columns", singleSource],
    queryFn: () => aiApi.sourceColumns(singleSource!),
    enabled: !!singleSource,
    retry: false,
  });
  const sourceCols: string[] = (() => {
    const srcs = spec?.sources as Record<string, { columns?: string[] }> | undefined;
    if (srcs) return [...new Set(Object.values(srcs).flatMap((s) => s.columns ?? []))];
    if (singleSource) return liveSourceCols.map((c) => c.column);
    return [];
  })();
  const martColumnOptions = useMemo(
    () => [...new Set([...sourceCols, ...cols.map((c) => martColumnForOutput(c, spec))])]
      .sort((a, b) => a.localeCompare(b)),
    [sourceCols, cols, spec],
  );
  const addColumnOptions = useMemo(
    () => martColumnOptions.filter((c) => !cols.includes(c)),
    [martColumnOptions, cols],
  );
  const [dragI, setDragI] = useState<number | null>(null);

  const patch = (fn: (s: RuleSpec) => void) => {
    if (!spec) return;
    const next = JSON.parse(JSON.stringify(spec)) as RuleSpec;
    fn(next);
    setJson(JSON.stringify(next, null, 2));
    setErr("");
  };
  const moveCol = (from: number, to: number) => {
    if (to < 0 || to >= cols.length || from === to) return;
    patch((s) => { const o = [...(s.output ?? [])]; const [m] = o.splice(from, 1); o.splice(to, 0, m); s.output = o; });
  };
  const removeCol = (c: string) => {
    patch((s) => { s.output = (s.output ?? []).filter((x) => x !== c); });
    setLabels((m) => {
      if (!(c in m)) return m;
      const next = { ...m };
      delete next[c];
      return next;
    });
  };
  const setColumnLabel = (col: string, title: string) =>
    setLabels((m) => ({ ...m, [col]: title }));
  /** Point an output column at a different mart field — grain keys rename everywhere;
   *  attribute rollups (e.g. max(full_name)) keep the report column id and swap the
   *  underlying mart reference in the spec. */
  const remapMartColumn = (outputCol: string, newMart: string) => {
    const nextMart = newMart.trim();
    if (!outputCol || !nextMart) return;
    const kind = columnKind(outputCol, spec);
    if (kind === "row_case" || kind === "calculated") return;
    const oldMart = martColumnForOutput(outputCol, spec);
    if (oldMart === nextMart) return;
    try {
      const root = JSON.parse(json) as Record<string, unknown>;
      replaceMartFieldRefs(root, oldMart, nextMart);
      if (kind === "grain" && outputCol === oldMart && outputCol !== nextMart) {
        const s = root as RuleSpec;
        s.output = replaceStringList(s.output, outputCol, nextMart) ?? (s.output as string[]);
        setLabels((m) => {
          if (!(outputCol in m)) return m;
          const next = { ...m, [nextMart]: m[outputCol] };
          delete next[outputCol];
          return next;
        });
      }
      setJson(JSON.stringify(root, null, 2));
      setErr("");
    } catch {
      setErr("Couldn't remap that column — check the spec JSON.");
    }
  };
  // Add a field to the output. An attribute (e.g. full_name, department) is wired in
  // all three places it must live: a source's columns, the grain, and the output. A
  // name that's already a rollup/compute result just joins the output.
  const addColumn = (raw: string) => {
    const c = raw.trim();
    if (!c || cols.includes(c)) return;
    patch((s) => {
      const rollup = (s.rollup as Record<string, string> | undefined) ?? {};
      const compute = (s.compute as Record<string, string> | undefined) ?? {};
      const grain = (s.grain as string[]) ?? [];
      wireSourceColumn(s, c);
      if (c in compute) {
        // computed metric — output only
      } else if (usesAttributeRollupPattern(s) && !grain.includes(c)) {
        if (!s.rollup) s.rollup = {};
        (s.rollup as Record<string, string>)[c] = `max(${c})`;
      } else if (!(c in rollup)) {
        if (!grain.includes(c)) s.grain = [...grain, c];
      }
      const out = (s.output as string[]) ?? [];
      if (!out.includes(c)) s.output = [...out, c];
    });
    setNewCol("");
  };
  const copyJson = () => {
    navigator.clipboard?.writeText(json).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }).catch(() => {});
  };
  const addFilter = () =>
    patch((s) => {
      s.filters = [...(s.filters ?? []),
        { name: `filter_${(s.filters ?? []).length + 1}`, type: "string", op: "eq", column: "", label: "" }];
    });
  const updateFilter = (i: number, k: keyof RuleFilter, v: unknown) =>
    patch((s) => {
      const fs = [...(s.filters ?? [])];
      fs[i] = { ...fs[i], [k]: v };
      if (k === "label" && typeof v === "string") fs[i].name = slug(v);   // keep param name in sync
      s.filters = fs;
    });
  const removeFilter = (i: number) =>
    patch((s) => { s.filters = (s.filters ?? []).filter((_, j) => j !== i); });

  // Plain-language explanation — generated on the backend (Python), fetched (debounced)
  // whenever the spec or the column titles change. Shown in the "In plain words" tab.
  const [tab, setTab] = useState(editing ? 2 : 0);   // new report starts on JSON (with the guide)
  const [guideOpen, setGuideOpen] = useState(!editing);
  const [explain, setExplain] = useState<ExplainSection[]>([]);
  const [explaining, setExplaining] = useState(false);
  const [explainErr, setExplainErr] = useState("");
  const specKey = JSON.stringify(spec);       // re-fetch only when the parsed spec changes
  useEffect(() => {
    if (!spec) {
      setExplain([]);
      setExplainErr("");
      setExplaining(false);
      return;
    }
    setExplaining(true);
    const t = setTimeout(() => {
      templateApi.explainRuleReport(spec, displayLabels)
        .then((r) => { setExplain(r.sections); setExplainErr(""); })
        .catch(() => { setExplain([]); setExplainErr("Finish the spec to see the plain-language version."); })
        .finally(() => setExplaining(false));
    }, 450);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [specKey, displayLabels]);

  const loadTemplate = () => { setJson(JSON.stringify(TEMPLATE, null, 2)); setTab(0); setErr(""); };
  const loadSkeleton = () => { setJson(JSON.stringify(SKELETON, null, 2)); setTab(0); setErr(""); };

  // Editing saves update the current version IN PLACE by default (no version spam).
  // "Save as version" snapshots a new version with a note — a deliberate act.
  const doSave = async (opts?: { newVersion?: boolean; note?: string }) => {
    setErr("");
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(json);
    } catch {
      setErr("The spec isn’t valid JSON — check for a missing comma or quote.");
      return;
    }
    if (!name.trim()) { setErr("Give the report a name."); return; }
    const clean = columnLabelsForSave(cols, labels);
    // Presentation-layer config (never part of the governed spec itself — see
    // PivotSpec) rides alongside the spec's own keys in the SAME JSON blob
    // (the AI chat proposes them as siblings; the Columns/Filters panels don't
    // look at them, so they pass through patch()'s clone untouched). Strip
    // them out here so `spec` sent to the API is the calculation JSON alone.
    const { row_number_column, subtotal, totals, pivot, ...spec } = parsed;
    const presentation = {
      row_number_column: row_number_column as string | undefined,
      subtotal: subtotal as Record<string, unknown> | undefined,
      totals: totals as string[] | undefined,
      pivot: pivot as RulePivotConfig | undefined,
    };
    setBusy(true);
    try {
      const r = editing
        ? await templateApi.updateRuleReport(templateId!, name.trim(), spec, category, clean,
            { new_version: opts?.newVersion, note: opts?.note, export_options: exportOpts,
              description: description.trim() || undefined, session_id: chatSessionId, ...presentation })
        : await templateApi.createRuleReport(name.trim(), spec, category, clean, exportOpts,
            description.trim() || undefined, presentation, chatSessionId);
      navigate(`/viewer/r/${r.template_id}`);   // straight to the runnable report
    } catch (e) {
      setErr((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? "Couldn’t save the report — check the spec.");
    } finally { setBusy(false); }
  };
  const save = () => doSave();

  return (
    <Box sx={{ maxWidth: 1280, mx: "auto", pt: 3, pb: 5, px: { xs: 1, md: 2 } }}>
      <Stack direction="row" justifyContent="space-between" alignItems="flex-start" sx={{ mb: 3.5 }}>
        <Box>
          <Typography variant="h4" sx={{ mb: 0.75 }}>{editing ? "Edit rule report" : "Rule report (JSON)"}</Typography>
          <Typography variant="body2" color="text.secondary">
            For rule-heavy reports — a governed calculation spec compiled to safe SQL. No raw SQL.
          </Typography>
        </Box>
        <Stack direction="row" spacing={1}>
          <Button variant="text" onClick={() => navigate("/")}>Back</Button>
          {editing && (
            <Button variant="outlined" startIcon={<HistoryOutlined />} disabled={busy || !json.trim()}
              onClick={() => { setVerNote(""); setVerDlg(true); }}>
              Save as version…
            </Button>
          )}
          <Button variant="contained" startIcon={<PlayArrow />} disabled={busy || !json.trim()} onClick={save}>
            {editing ? "Save & open" : "Create & open"}
          </Button>
        </Stack>
      </Stack>

      <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ mb: 2 }} alignItems="flex-start">
        <TextField label="Report name" value={name} sx={{ flex: 1, width: "100%" }}
          onChange={(e) => setName(e.target.value)} placeholder="e.g. Overtime (monthly)" />
        <TextField select label="Category" value={category} sx={{ width: { xs: "100%", sm: 220 } }}
          onChange={(e) => setCategory(e.target.value)}
          helperText="Filed under this on Templates">
          {REPORT_MODULES.map((m) => <MenuItem key={m} value={m}>{m}</MenuItem>)}
        </TextField>
      </Stack>
      <TextField label="Description" value={description} fullWidth sx={{ mb: 3 }}
        onChange={(e) => setDescription(e.target.value)}
        placeholder="Shown on the Templates list, under the report name"
        helperText="Not the export header — that's set separately below." />

      {editing && loading && (
        <Box sx={{ textAlign: "center", py: 6, mb: 2 }}>
          <CircularProgress size={28} />
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1.5 }}>
            Loading report…
          </Typography>
        </Box>
      )}

      {(!editing || !loading) && (
      <>
      {/* Version history — each save is a version; restore any one and run it. */}
      {editing && versions.length > 0 && (
        <Box sx={{ mb: 2 }}>
          <Button size="small" startIcon={<HistoryOutlined />} endIcon={versOpen ? <ExpandLess /> : <ExpandMore />}
            onClick={() => setVersOpen((o) => !o)} sx={{ textTransform: "none" }}>
            Version history ({versions.length})
          </Button>
          <Collapse in={versOpen} unmountOnExit>
            <Card variant="outlined" sx={{ mt: 0.5 }}>
              <Stack divider={<Box sx={{ borderBottom: "1px solid #F1F5F9" }} />}>
                {versions.map((v) => (
                  <Stack key={v.id} direction="row" alignItems="center" spacing={1.5} sx={{ px: 2, py: 1 }}>
                    <Typography variant="body2" sx={{ fontWeight: 700, width: 44 }}>v{v.version_no}</Typography>
                    <Box sx={{ flex: 1, minWidth: 0 }}>
                      <Typography variant="body2" noWrap sx={{ fontSize: "0.82rem" }}>
                        {v.note || <span style={{ color: "#9CA3AF" }}>no note</span>}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {v.created_at ? new Date(v.created_at).toLocaleString() : "—"}
                      </Typography>
                    </Box>
                    {v.is_current && <Typography variant="caption" sx={{ color: "#007499", fontWeight: 700 }}>current</Typography>}
                    <Button size="small" startIcon={<ReplayOutlined />} onClick={() => useVersion(v.id)}
                      sx={{ textTransform: "none" }}>Restore &amp; run</Button>
                  </Stack>
                ))}
              </Stack>
            </Card>
          </Collapse>
        </Box>
      )}

      {/* Two tabs side by side: the HR-readable explanation and the governed JSON —
          same content, two lenses. Plain words is generated on the backend (Python). */}
      <Card variant="outlined" sx={{ mb: 2.5 }}>
        <Tabs value={tab} onChange={(_, v: number) => setTab(v)}
          sx={{ borderBottom: "1px solid #E5E7EB", minHeight: 42, px: 1 }}>
          <Tab icon={<DataObjectOutlined fontSize="small" />} iconPosition="start" label="JSON logic"
            sx={{ minHeight: 42, textTransform: "none", fontWeight: 600 }} />
          <Tab icon={<AutoAwesome fontSize="small" />} iconPosition="start" label="AI helper"
            sx={{ minHeight: 42, textTransform: "none", fontWeight: 600 }} />
          <Tab icon={<AutoStoriesOutlined fontSize="small" />} iconPosition="start" label="In plain words"
            sx={{ minHeight: 42, textTransform: "none", fontWeight: 600 }} />
        </Tabs>

        {/* Tab 2 — plain words */}
        <Box sx={{ display: tab === 2 ? "block" : "none", p: 2, bgcolor: "#F5FBFC" }}>
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1 }}>
            What this report does, in plain language — read it like a sentence. Auto-generated from the logic.
          </Typography>
          {explaining && explain.length === 0 && (
            <Stack alignItems="center" py={2}><CircularProgress size={22} /></Stack>
          )}
          {!explaining && explainErr && explain.length === 0 && (
            <Typography variant="body2" color="text.secondary">{explainErr}</Typography>
          )}
          {explain.length > 0 && (
            <Stack spacing={1.75}>
              {explain.map((sec) => (
                <Box key={sec.title}>
                  <Typography sx={{ fontSize: "0.72rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.5, color: "#00617A", mb: 0.5 }}>
                    {sec.title}
                  </Typography>
                  <Stack component="ul" sx={{ m: 0, pl: 2.5 }} spacing={0.5}>
                    {sec.lines.map((l, i) => (
                      <Typography component="li" key={i} variant="body2" sx={{ fontSize: "0.85rem", lineHeight: 1.6 }}>{l}</Typography>
                    ))}
                  </Stack>
                </Box>
              ))}
            </Stack>
          )}
        </Box>

        {/* Tab 0 — JSON logic (the governed spec) */}
        <Box sx={{ display: tab === 0 ? "block" : "none", p: 2, bgcolor: "#F8FAFC" }}>
          {/* Top toolbar — reset to a starting point. (Copy JSON lives on the editor.) */}
          <Stack direction="row" spacing={1} sx={{ mb: 1 }}>
            <Button size="small" variant="outlined" startIcon={<ScienceOutlined />} onClick={loadTemplate}>
              Starter template
            </Button>
            <Button size="small" variant="outlined" startIcon={<NoteAddOutlined />} onClick={loadSkeleton}>
              Blank skeleton
            </Button>
          </Stack>
          {json.includes("<") && (
            <Typography variant="caption" sx={{ display: "block", mb: 1, color: "#B45309" }}>
              Replace every <Box component="code" sx={{ fontFamily: "ui-monospace, monospace" }}>&lt;placeholder&gt;</Box> with
              your own table and field names before saving.
            </Typography>
          )}

          {/* Spec guide — one plain line per section (JSON can't hold comments). */}
          <Box sx={{ mb: 1 }}>
            <Button size="small" startIcon={<MenuBookOutlined />} endIcon={guideOpen ? <ExpandLess /> : <ExpandMore />}
              onClick={() => setGuideOpen((o) => !o)} sx={{ textTransform: "none" }}>
              Spec guide — what each section means
            </Button>
            <Collapse in={guideOpen} unmountOnExit>
              <Box sx={{ mt: 0.5, p: 1.25, borderRadius: 1.5, bgcolor: "#F1F5F9", border: "1px solid #E2E8F0" }}>
                <Stack spacing={0.4}>
                  {GUIDE.map(([k, t]) => (
                    <Typography key={k} variant="caption" sx={{ fontSize: "0.76rem", lineHeight: 1.5 }}>
                      <Box component="code" sx={{ fontFamily: "ui-monospace, monospace", fontWeight: 700, color: "#0369A1", mr: 0.75 }}>{k}</Box>
                      {t}
                    </Typography>
                  ))}
                </Stack>
              </Box>
            </Collapse>
          </Box>

          <Box sx={{ position: "relative" }}>
            <Tooltip title={copied ? "Copied" : "Copy JSON"}>
              <IconButton size="small" onClick={copyJson} disabled={!json.trim()}
                sx={{ position: "absolute", top: 6, right: 6, zIndex: 1, bgcolor: "#fff",
                      border: "1px solid #E2E8F0", "&:hover": { bgcolor: "#EAF4F7" } }}>
                {copied ? <Check fontSize="small" color="success" /> : <ContentCopyOutlined fontSize="small" />}
              </IconButton>
            </Tooltip>
            <TextField fullWidth multiline minRows={16} value={json}
              onChange={(e) => { setJson(e.target.value); setErr(""); }}
              slotProps={{ input: { sx: {
                fontFamily: "ui-monospace, monospace", fontSize: "0.8rem",
                bgcolor: "#F4F7FB", borderRadius: 1.5,
              } } }}
              sx={{ "& .MuiOutlinedInput-notchedOutline": { borderColor: "#DCE3EC" } }}
              placeholder='Paste a spec, or use "Starter template" / "Blank skeleton" above.' />
          </Box>
          {err && <Alert severity="error" sx={{ mt: 1.5 }}>{err}</Alert>}
          <Alert severity="info" icon={false} sx={{ mt: 1, py: 0.25, fontSize: "0.78rem", bgcolor: "#EEF6F9" }}>
            Governed &amp; safe: arithmetic, comparisons, and/or/not, in(), greatest/least/coalesce —
            never raw SQL. The server validates before saving.
          </Alert>
        </Box>

        {/* Tab 1 — AI helper (chat -> spec, using Claude Code) */}
        <Box sx={{ display: tab === 1 ? "block" : "none" }}>
          <RuleReportAIChat onUseSpec={(m) => {
            // Merge spec + any presentation config the AI proposed into the
            // SAME flat JSON blob doSave() later splits back apart — see its
            // comment. Never carries the chat message's own role/text/attachments.
            const merged: Record<string, unknown> = { ...(m.spec ?? {}) };
            if (m.row_number_column) merged.row_number_column = m.row_number_column;
            if (m.subtotal) merged.subtotal = m.subtotal;
            if (m.totals?.length) merged.totals = m.totals;
            if (m.pivot) merged.pivot = m.pivot;
            setJson(JSON.stringify(merged, null, 2));
            // Keep friendly titles for columns that still exist after an AI update.
            const nextOut = Array.isArray(merged.output)
              ? merged.output.filter((c): c is string => typeof c === "string") : [];
            setLabels((prev) => Object.fromEntries(
              nextOut.filter((c) => prev[c]).map((c) => [c, prev[c]]),
            ));
            setTab(0);
            setErr("");
          }}
          initialSessionId={initialChatSessionId}
          initialMessages={initialChatMessages}
          onSessionChange={setChatSessionId}
          />
        </Box>
      </Card>

      {/* Columns — order + heading, exactly like the normal builder's Selected
          Columns. Drag or use the arrows to reorder; the title is pre-filled with
          the current name so you can tweak it, or leave it to keep the field name. */}
      {cols.length > 0 && (
        <Card variant="outlined" sx={{ mt: 2 }}>
          <CardContent sx={{ py: 2 }}>
            <Stack spacing={0.5} sx={{ mb: 1.5 }}>
              <Stack direction="row" spacing={1} alignItems="center">
                <ViewColumnOutlined fontSize="small" sx={{ color: "#007499" }} />
                <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>Columns</Typography>
              </Stack>
              <Typography variant="caption" color="text.secondary" sx={{ display: "block", lineHeight: 1.45 }}>
                Drag <DragIndicator sx={{ fontSize: 13, verticalAlign: "middle" }} /> or use arrows to reorder.
                Pick the mart field each column reads from, then set the heading shown in the report.
              </Typography>
            </Stack>
            <Stack spacing={1}>
              {cols.map((c, i) => {
                const kind = columnKind(c, spec);
                const martCol = martColumnForOutput(c, spec);
                const mappable = kind === "grain" || kind === "attribute_rollup";
                return (
                <Box key={c}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={() => { if (dragI !== null) moveCol(dragI, i); setDragI(null); }}
                  sx={{
                    borderRadius: 1.5, border: "1px solid", borderColor: dragI === i ? "#007499" : "#E5E7EB",
                    bgcolor: dragI === i ? "#EAF4F7" : "#FAFBFC", p: { xs: 1, sm: 1.25 },
                  }}>
                  <Box sx={{
                    display: "grid",
                    gridTemplateColumns: {
                      xs: "auto 1fr",
                      sm: "auto auto minmax(140px, 1fr) minmax(140px, 1fr) auto",
                    },
                    gap: { xs: 0.75, sm: 1 },
                    alignItems: "start",
                  }}>
                    <Box draggable onDragStart={() => setDragI(i)} onDragEnd={() => setDragI(null)}
                      sx={{ display: "flex", cursor: "grab", color: "#C4CAD2", mt: 1, "&:active": { cursor: "grabbing" } }}
                      title="Drag to reorder">
                      <DragIndicator fontSize="small" />
                    </Box>
                    <Typography variant="caption" sx={{ color: "text.secondary", mt: 1.2, minWidth: 18 }} title={c}>
                      {i + 1}.
                    </Typography>
                    {mappable ? (
                      <Autocomplete
                        size="small"
                        freeSolo
                        sx={{ minWidth: 0, gridColumn: { xs: "1 / -1", sm: "auto" } }}
                        options={martColumnOptions}
                        value={martCol}
                        onChange={(_, v) => { if (typeof v === "string" && v.trim()) remapMartColumn(c, v); }}
                        onInputChange={(_, v, reason) => {
                          if (reason === "blur" && v.trim() && v.trim() !== martCol) remapMartColumn(c, v);
                        }}
                        renderInput={(params) => (
                          <TextField
                            {...params}
                            label="Mart column"
                            placeholder={sourceCols.length ? "Search fields…" : martCol}
                            onMouseDown={(e) => e.stopPropagation()}
                          />
                        )}
                      />
                    ) : (
                      <Tooltip title={
                        kind === "row_case"
                          ? "Derived by a row rule — edit in JSON or AI helper"
                          : "Formula column — edit rules in JSON or AI helper"
                      }>
                        <Stack direction="row" spacing={0.75} alignItems="center"
                          sx={{ minHeight: 40, gridColumn: { xs: "1 / -1", sm: "auto" }, px: 0.5 }}>
                          <Chip size="small"
                            label={kind === "row_case" ? "Rule" : "Calculated"}
                            sx={{ height: 22, fontSize: "0.68rem" }} />
                          <Typography variant="body2" noWrap
                            sx={{ fontFamily: "ui-monospace, Menlo, monospace", fontSize: "0.82rem" }}>
                            {c}
                          </Typography>
                        </Stack>
                      </Tooltip>
                    )}
                    <TextField
                      size="small"
                      variant="outlined"
                      label="Column heading"
                      value={columnHeadingValue(c, labels)}
                      onChange={(e) => setColumnLabel(c, e.target.value)}
                      onBlur={(e) => {
                        const v = e.target.value.trim();
                        if (!v || v === prettyColName(c)) {
                          setLabels((m) => {
                            if (!(c in m)) return m;
                            const next = { ...m };
                            delete next[c];
                            return next;
                          });
                        } else if (v !== e.target.value) {
                          setColumnLabel(c, v);
                        }
                      }}
                      onMouseDown={(e) => e.stopPropagation()}
                      helperText={`Shown in the report · key: ${c}`}
                      sx={{
                        minWidth: 0, gridColumn: { xs: "1 / -1", sm: "auto" },
                        "& .MuiInputBase-input": { py: 0.5, fontSize: "0.82rem" },
                      }}
                    />
                    <Stack direction="row" sx={{ justifySelf: { xs: "end", sm: "start" }, gridColumn: { xs: "1 / -1", sm: "auto" } }}>
                      <IconButton size="small" disabled={i === 0} onClick={() => moveCol(i, i - 1)} title="Move up">
                        <ArrowUpward fontSize="inherit" />
                      </IconButton>
                      <IconButton size="small" disabled={i === cols.length - 1} onClick={() => moveCol(i, i + 1)} title="Move down">
                        <ArrowDownward fontSize="inherit" />
                      </IconButton>
                      <IconButton size="small" onClick={() => removeCol(c)} title="Remove column">
                        <Close fontSize="inherit" />
                      </IconButton>
                    </Stack>
                  </Box>
                </Box>
                );
              })}
            </Stack>

            {/* Add a mart column to the report output. */}
            <Stack direction={{ xs: "column", sm: "row" }} spacing={1} alignItems={{ sm: "flex-start" }} sx={{ mt: 1.5 }}>
              <Autocomplete
                size="small"
                freeSolo
                sx={{ flex: 1, minWidth: 0, width: "100%" }}
                options={addColumnOptions}
                inputValue={newCol}
                onInputChange={(_, v) => setNewCol(v)}
                onChange={(_, v) => { if (typeof v === "string" && v.trim()) addColumn(v); }}
                renderInput={(params) => (
                  <TextField {...params} label="Add a column"
                    placeholder={addColumnOptions.length ? "Search mart fields…" : "Type a column name"}
                    onKeyDown={(e) => { if (e.key === "Enter" && newCol.trim()) addColumn(newCol); }} />
                )}
              />
              <Button variant="outlined" size="small" startIcon={<Add />}
                disabled={!newCol.trim() || cols.includes(newCol.trim())}
                onClick={() => addColumn(newCol)}
                sx={{ flexShrink: 0, width: { xs: "100%", sm: "auto" } }}>
                Add
              </Button>
            </Stack>
            <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.75, lineHeight: 1.45 }}>
              New fields are wired into the spec automatically (source, grain or rollup, and output).
            </Typography>
          </CardContent>
        </Card>
      )}

      {/* Filters — the controls the viewer shows before running (period, employee …).
          Same plain-language operators as the normal builder. */}
      {spec && (
        <Card variant="outlined" sx={{ mt: 2 }}>
          <CardContent sx={{ py: 2 }}>
            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
              <Stack direction="row" spacing={1} alignItems="center">
                <FilterAltOutlined fontSize="small" sx={{ color: "#007499" }} />
                <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>Filters</Typography>
                <Typography variant="caption" color="text.secondary">Shown in the viewer before running.</Typography>
              </Stack>
              <Button size="small" startIcon={<Add />} onClick={addFilter}>Add filter</Button>
            </Stack>
            {filters.length === 0 ? (
              <Typography variant="body2" color="text.secondary">No filters — add one (e.g. a date range or employee number).</Typography>
            ) : (
              <Stack spacing={1}>
                {filters.map((f, i) => (
                  <Stack key={i} direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                    <TextField size="small" label="Label" value={f.label ?? ""} sx={{ width: 150 }}
                      onChange={(e) => updateFilter(i, "label", e.target.value)} placeholder="From" />
                    <Autocomplete size="small" freeSolo options={sourceCols} sx={{ width: 180 }}
                      inputValue={f.column ?? ""}
                      onInputChange={(_, v) => updateFilter(i, "column", v)}
                      renderInput={(params) => (
                        <TextField {...params} label="Column"
                          placeholder={sourceCols.length ? "pick a field" : "work_date"}
                          helperText={f.column && sourceCols.length && !sourceCols.includes(f.column) ? "not a source field" : undefined} />
                      )} />
                    <TextField size="small" select label="Condition" value={f.op ?? "eq"} sx={{ width: 150 }}
                      onChange={(e) => updateFilter(i, "op", e.target.value)}>
                      {OPS.map((o) => <MenuItem key={o.v} value={o.v}>{o.label}</MenuItem>)}
                    </TextField>
                    <TextField size="small" select label="Type" value={f.type ?? "string"} sx={{ width: 110 }}
                      onChange={(e) => updateFilter(i, "type", e.target.value)}>
                      {FTYPES.map((t) => <MenuItem key={t.v} value={t.v}>{t.label}</MenuItem>)}
                    </TextField>
                    <FormControlLabel sx={{ mr: 0 }} label={<Typography variant="caption">Required</Typography>}
                      control={<Switch size="small" checked={Boolean(f.required)}
                        onChange={(e) => updateFilter(i, "required", e.target.checked)} />} />
                    <Tooltip title="Remove filter">
                      <IconButton size="small" onClick={() => removeFilter(i)}><Close fontSize="inherit" /></IconButton>
                    </Tooltip>
                  </Stack>
                ))}
              </Stack>
            )}
          </CardContent>
        </Card>
      )}

      {/* Export header — company / description / stamp printed on the Excel & PDF. */}
      {spec && (
        <Card variant="outlined" sx={{ mt: 2 }}>
          <CardContent sx={{ py: 2 }}>
            <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
              <ArticleOutlined fontSize="small" sx={{ color: "#007499" }} />
              <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>Export header</Typography>
              <Typography variant="caption" color="text.secondary">Printed on the Excel / PDF you download.</Typography>
            </Stack>
            <TextField label="Report description" value={exportOpts.description} fullWidth sx={{ mb: 1 }}
              onChange={(e) => setExportOpts((o) => ({ ...o, description: e.target.value }))}
              placeholder="e.g. Monthly overtime summary" />
            <Stack>
              <FormControlLabel
                control={<Switch checked={exportOpts.show_company}
                  onChange={(e) => setExportOpts((o) => ({ ...o, show_company: e.target.checked }))} />}
                label={<Typography variant="body2">Show company name</Typography>} />
              <FormControlLabel
                control={<Switch checked={exportOpts.show_meta}
                  onChange={(e) => setExportOpts((o) => ({ ...o, show_meta: e.target.checked }))} />}
                label={<Typography variant="body2">Show “Generated by … on …” (user + date/time)</Typography>} />
            </Stack>
          </CardContent>
        </Card>
      )}

      </>
      )}

      {/* Save-as-version — deliberate snapshot with a comment on what changed. */}
      <Dialog open={verDlg} onClose={() => setVerDlg(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ fontSize: "1.05rem" }}>Save as a new version</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
            This keeps the current version and snapshots a new one, stamped with the date and time.
            Add a short note on what changed.
          </Typography>
          <TextField autoFocus fullWidth multiline minRows={2} label="What changed in this version?"
            value={verNote} onChange={(e) => setVerNote(e.target.value)}
            placeholder="e.g. Added department column; capped OT at 60h." />
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setVerDlg(false)}>Cancel</Button>
          <Button variant="contained" disabled={busy || !verNote.trim()}
            onClick={() => { setVerDlg(false); doSave({ newVersion: true, note: verNote.trim() }); }}>
            Create version &amp; open
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
