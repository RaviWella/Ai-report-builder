// Excel-first, guided upload (FR-A1/A2) for non-technical users.
// Flow: drop a sample -> we strip rows locally -> the AI reviews the layout ->
// a friendly mapping review -> "Add columns". Meaningful waiting messages
// throughout so the user always knows what's happening.
//
// The mapping review is a production-grade importer: every detected column gets
// an inline, searchable field-picker pre-filled with the AI's guess. Low-
// confidence guesses are flagged so the user knows what to check, and any wrong
// match can be corrected right here by picking the correct field (or skipped, or
// sent to a formula). Nothing is hardcoded — the picker options are the tenant's
// live semantic catalogue.
import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Alert, Autocomplete, Box, Button, Chip, CircularProgress, createFilterOptions, Dialog,
  DialogContent, DialogTitle, IconButton, LinearProgress, Stack, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, TextField, Tooltip,
  Typography, Paper,
} from "@mui/material";
import {
  CloudUpload, CheckCircle, Lock, AutoAwesome, ArrowForward, Functions,
  BlockOutlined, ReportProblemOutlined,
  TravelExploreOutlined, VisibilityOutlined, CloseOutlined, AddOutlined, EditOutlined,
  ArrowUpward, ArrowDownward,
} from "@mui/icons-material";
import { aiApi, semanticApi, validationsApi } from "../../api/client";
import { useBuilderStore } from "../../store/builderStore";
import { CustomColumnDialog } from "./CustomColumnDialog";
import ExcelMappingAIChat from "./ExcelMappingAIChat";
import { AMOUNT_HINT } from "./SelectedColumns";
import {
  buildMappingDisplayRows,
  extraAfterFromRows,
  moveExtraInRows,
  reportOrderFromRows,
} from "./excelMappingOrder";
import type { SemanticFieldMeta } from "../../types/spec";

interface Mapping { header: string; suggested_ref: string | null; confidence: number; source?: string; }

// Search matches the field label, its ref, AND its entity — so typing "salary",
// "employee.emp_no" or "payroll" all narrow the list.
const fieldFilter = createFilterOptions<SemanticFieldMeta>({
  stringify: (o) => `${o.label} ${o.ref} ${o.entity}`,
});

// Meaningful, sequential status while the upload is processed.
const STAGES = [
  "Reading your spreadsheet…",
  "Removing all data rows (privacy — only column names leave your browser)…",
  "Detecting each column’s type…",
  "AI is reviewing your column layout…",
  "Matching your columns to report fields…",
];

// File-picker filter: Excel variants, CSV, PDF, and images.
const UPLOAD_ACCEPT =
  ".xlsx,.xls,.xlsm,.xlsb,.csv,.pdf,image/*," +
  "application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv";

// Turn any upload failure into something the user can act on. The API answers
// parse problems with a string `detail`; anything else (proxy 413/504, plain-text
// 500, dropped connection) has no detail at all, so name the real cause instead
// of blaming the file.
function uploadError(err: unknown, fallback: string): string {
  const res = (err as { response?: { status?: number; data?: unknown } })?.response;
  const data = res?.data;
  const detail = (data as { detail?: unknown } | undefined)?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0] as { msg?: string } | undefined;
    if (first?.msg) return `Upload rejected: ${first.msg}`;
  }

  const status = res?.status;
  if (status === 413) {
    return "That file is too large for the server. Keep the sample under 20 MB — a few sample rows are enough.";
  }
  if (status === 504 || status === 502) {
    return "The server took too long to read that file. Try a sample with fewer columns, or retry.";
  }
  if (status === 401 || status === 403) {
    return "Your session no longer has access to upload samples. Reload the page and try again.";
  }
  if (status) return `${fallback} (server responded ${status})`;
  return `${fallback} (could not reach the server — check your connection and retry)`;
}

function titleFromFilename(filename: string): string {
  return filename
    .replace(/\.[^.]+$/, "")
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

// Confidence badge — draws the eye to the guesses worth double-checking.
function confBadge(c: number): { label: string; bg: string; fg: string } | null {
  if (c >= 0.8) return null; // confident — no noise
  if (c >= 0.5) return { label: "check", bg: "#FEF3C7", fg: "#92400E" };
  return { label: "low — verify", bg: "#FFF0ED", fg: "#C13515" };
}

export function ExcelUpload() {
  const { addField, removeField, setFieldLabel, setFieldTotal, reorderFields, dataSpec, setSourceFile, updatePresentation } = useBuilderStore();
  const selected = new Set(dataSpec.fields.map((f) => f.ref));
  const labelByRefSel = new Map(dataSpec.fields.map((f) => [f.ref, f.label ?? ""]));
  // Extra fields slot between sheet columns. Keyed by ref → the sheet header
  // they sit after (`null` = before the first column).
  const [extraAfter, setExtraAfter] = useState<Record<string, string | null>>({});
  const { data: fields = [] } = useQuery({ queryKey: ["fields"], queryFn: semanticApi.fields });
  const [mappings, setMappings] = useState<Mapping[]>([]);
  // View the uploaded file (parsed in the browser — rows never leave the device).
  const [rawFile, setRawFile] = useState<File | null>(null);
  const [viewData, setViewData] = useState<{ headers: string[]; rows: string[][] } | null>(null);
  const [viewOpen, setViewOpen] = useState(false);
  const [viewErr, setViewErr] = useState("");
  // Extra fields the user adds that weren't in the sheet.
  const [extra, setExtra] = useState<SemanticFieldMeta | null>(null);
  // The current chosen ref per source header (null = don't import). Seeded from
  // the AI's suggestion, then freely overridable by the user.
  const [choice, setChoice] = useState<Record<string, string | null>>({});
  const [fileName, setFileName] = useState("");
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState(0);
  const [error, setError] = useState("");
  const [defineLabel, setDefineLabel] = useState<string | null>(null);
  // AI/deterministic field suggestions per header (for columns that didn't map).
  const [sugg, setSugg] = useState<Record<string, { ref: string; label: string; reason: string }[]>>({});
  const [suggBusy, setSuggBusy] = useState<string | null>(null);
  // Headers the user has flagged as "not in our data yet" (ETL gap).
  const [requested, setRequested] = useState<Record<string, boolean>>({});
  // Drill-down: where a not-in-a-mart concept actually lives (fact/dim/staging).
  const [disc, setDisc] = useState<Record<string, { summary: string; matches: { schema: string; table: string; column: string; layer: string }[] }>>({});
  const [discBusy, setDiscBusy] = useState<string | null>(null);
  // Auto business-language gap note per unmatched header (same as the chat flow).
  const [gaps, setGaps] = useState<Record<string, { status: string; message: string }>>({});
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => () => { if (timer.current) clearInterval(timer.current); }, []);

  // Options for the picker: catalogue fields, sorted by entity then label so
  // MUI's groupBy renders clean per-entity sections.
  const options = useMemo(
    () =>
      [...(fields as SemanticFieldMeta[])].sort(
        (a, b) => a.entity.localeCompare(b.entity) || a.label.localeCompare(b.label),
      ),
    [fields],
  );
  const fieldByRef = useMemo(
    () => new Map((fields as SemanticFieldMeta[]).map((f) => [f.ref, f])),
    [fields],
  );

  const mappedChosen = useMemo(
    () => new Set(Object.values(choice).filter(Boolean) as string[]),
    [choice],
  );
  const extraFields = useMemo(
    () => dataSpec.fields.filter((f) => !mappedChosen.has(f.ref)),
    [dataSpec.fields, mappedChosen],
  );
  const mappingHeaders = useMemo(() => mappings.map((m) => m.header), [mappings]);
  // For the "Chat with AI to finish mapping" helper — headers still unmapped
  // (the ONLY ones the AI is allowed to touch), and a read-only snapshot of
  // what's already mapped (context only, for domain clues like "Gross Pay"
  // already resolved implying "Net Pay" is probably the sibling field).
  const unmappedHeaders = useMemo(
    () => mappings.filter((m) => !choice[m.header]).map((m) => m.header),
    [mappings, choice],
  );
  const mappedHeaderRefs = useMemo(
    () => Object.fromEntries(Object.entries(choice).filter(([, ref]) => !!ref)),
    [choice],
  );
  const mappingByHeader = useMemo(
    () => new Map(mappings.map((m) => [m.header, m])),
    [mappings],
  );
  const extraByRef = useMemo(
    () => new Map(extraFields.map((f) => [f.ref, f])),
    [extraFields],
  );
  const displayRows = useMemo(
    () => buildMappingDisplayRows(mappingHeaders, extraFields.map((f) => f.ref), extraAfter),
    [mappingHeaders, extraFields, extraAfter],
  );

  // Editing an existing Excel-built report: reconstruct the review panel from
  // the already-saved fields (each carries its source_header) instead of
  // leaving the tab on the bare upload dropzone — same picker/suggest/total
  // tools as a fresh upload, just already in the "Added" state. Runs once;
  // guarded by mappings.length so it never fights a later fresh upload
  // (onFile clears mappings back to [] first) or a field added afterward.
  useEffect(() => {
    if (mappings.length > 0) return;
    const withHeaders = dataSpec.fields.filter((f) => f.source_header);
    if (!withHeaders.length) return;
    const ms: Mapping[] = withHeaders.map((f) => ({
      header: f.source_header!, suggested_ref: f.ref, confidence: 1,
    }));
    setMappings(ms);
    setChoice(Object.fromEntries(ms.map((m) => [m.header, m.suggested_ref])));
  }, [dataSpec.fields, mappings.length]);

  // Drop slots for extras that were removed; new extras default to after the last sheet column.
  useEffect(() => {
    const extraRefs = new Set(extraFields.map((f) => f.ref));
    setExtraAfter((prev) => {
      let changed = false;
      const next: Record<string, string | null> = {};
      for (const [ref, after] of Object.entries(prev)) {
        if (extraRefs.has(ref)) next[ref] = after;
        else changed = true;
      }
      return changed ? next : prev;
    });
  }, [extraFields]);

  const persistVisualOrder = (rows: typeof displayRows, selectedRefs: Iterable<string>) => {
    const order = reportOrderFromRows(rows, choice, selectedRefs);
    const leftover = dataSpec.fields.map((f) => f.ref).filter((r) => !order.includes(r));
    reorderFields([...order, ...leftover]);
  };

  const moveField = (ref: string, dir: -1 | 1) => {
    const next = moveExtraInRows(displayRows, ref, dir);
    if (!next) return;
    setExtraAfter(extraAfterFromRows(next));
    persistVisualOrder(next, dataSpec.fields.map((f) => f.ref));
  };

  const addMappedColumn = (header: string, ref: string) => {
    addField({ ref, label: header, source_header: header });
    const selectedNow = new Set([...dataSpec.fields.map((f) => f.ref), ref]);
    persistVisualOrder(displayRows, selectedNow);
  };

  const onFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(""); setMappings([]); setChoice({}); setGaps({}); setFileName(file.name);
    setRawFile(file); setSourceFile(file); setViewData(null); setViewErr("");
    const suggestedTitle = titleFromFilename(file.name);
    if (suggestedTitle && !useBuilderStore.getState().presentation.title.trim()) {
      updatePresentation({ title: suggestedTitle });
    }
    setBusy(true); setStage(0);
    timer.current = setInterval(() => setStage((s) => Math.min(s + 1, STAGES.length - 1)), 1100);
    try {
      const res = await aiApi.excelMapping(file);
      const ms: Mapping[] = res.mappings;
      setMappings(ms);
      setChoice(Object.fromEntries(ms.map((m) => [m.header, m.suggested_ref])));
      // For columns that didn't map, PROACTIVELY resolve them (no button hunt):
      //  - auto-suggest the top-3 candidate fields (shown inline as "Did you mean")
      //  - auto-explain the gap in business language (collected-not-in-reports / not captured)
      const unmatched = ms.filter((m) => !m.suggested_ref).map((m) => m.header);
      if (unmatched.length) {
        aiApi.explainGaps(unmatched)
          .then((gs) => setGaps(Object.fromEntries(gs.map((g) => [g.term, { status: g.status, message: g.message }]))))
          .catch(() => {});
        // one call per unmatched header; keep only reasonably-relevant candidates so a
        // genuine data gap doesn't surface irrelevant guesses (it falls to the gap note).
        unmatched.slice(0, 25).forEach((h) => {
          aiApi.suggestFields(h)
            .then((s) => {
              const good = s.filter((x) => x.score >= 0.5).map((x) => ({ ref: x.ref, label: x.label, reason: x.reason }));
              setSugg((p) => ({ ...p, [h]: good }));
            })
            .catch(() => {});
        });
      }
    } catch (err: unknown) {
      setError(uploadError(
        err,
        "Couldn’t read that file. Use Excel (.xlsx, .xls, .csv), a PDF with selectable text, or a clear image.",
      ));
    } finally {
      if (timer.current) clearInterval(timer.current);
      setBusy(false);
    }
  };

  // Remember this header -> field choice so the next upload auto-corrects it.
  // Fire-and-forget: learning must never block the UI.
  const learn = (header: string, ref: string | null) => {
    aiApi.rememberColumnMapping(header, ref).catch(() => {});
  };

  // Change (or clear) a column's mapping. If that row was already added to the
  // report, swap it in place so the picker stays the single source of truth.
  // Every change is remembered so the correction sticks for next time.
  const changeMapping = (header: string, ref: string | null) => {
    setChoice((prev) => {
      const old = prev[header] ?? null;
      if (old && selected.has(old)) {
        removeField(old);
        if (ref) addField({ ref, label: header, source_header: header });
      }
      return { ...prev, [header]: ref };
    });
    learn(header, ref);
  };

  // Ask for candidate fields for a column that didn't map well.
  const askSuggest = async (header: string) => {
    setSuggBusy(header);
    try {
      const s = await aiApi.suggestFields(header);
      setSugg((p) => ({ ...p, [header]: s }));
    } catch {
      setSugg((p) => ({ ...p, [header]: [] }));
    } finally {
      setSuggBusy(null);
    }
  };

  // "This column isn't in our data yet" — log it to the Data Health gap list for ETL.
  const requestInData = (header: string) => {
    setRequested((p) => ({ ...p, [header]: true }));
    validationsApi.requestField(header).catch(() => {});
  };

  // View the uploaded sheet — parsed IN THE BROWSER (rows never leave the device).
  const openView = async () => {
    setViewOpen(true);
    if (viewData || !rawFile) return;
    setViewErr("");
    try {
      const XLSX = await import("xlsx"); // lazy — only loads when a file is viewed
      const buf = await rawFile.arrayBuffer();
      const wb = XLSX.read(buf, { sheetRows: 51 }); // header + up to 50 rows
      const ws = wb.Sheets[wb.SheetNames[0]];
      const grid = XLSX.utils.sheet_to_json<string[]>(ws, { header: 1, blankrows: false, defval: "" });
      const headers = (grid[0] ?? []).map((h) => String(h ?? ""));
      const rows = grid.slice(1, 51).map((r) => headers.map((_, i) => String(r[i] ?? "")));
      setViewData({ headers, rows });
    } catch {
      setViewErr("Couldn’t preview this file (only .xlsx/.xls/.csv can be shown here).");
    }
  };

  // Add a field that wasn't in the uploaded sheet.
  const addExtra = (f: SemanticFieldMeta | null) => {
    if (f && !selected.has(f.ref)) addField({ ref: f.ref, label: f.label });
    setExtra(null);
  };

  // Drill down the datamart layers to locate where this concept actually lives.
  const findInData = async (header: string) => {
    setDiscBusy(header);
    try {
      const r = await aiApi.discover(header);
      setDisc((p) => ({ ...p, [header]: { summary: r.summary, matches: r.matches } }));
    } catch {
      setDisc((p) => ({ ...p, [header]: { summary: "Couldn’t search the data.", matches: [] } }));
    } finally {
      setDiscBusy(null);
    }
  };

  const mappedCount = Object.values(choice).filter(Boolean).length;
  const addAll = () => {
    const added: string[] = [];
    Object.entries(choice).forEach(([header, ref]) => {
      if (ref && !selected.has(ref)) {
        addField({ ref, label: header, source_header: header });
        added.push(ref);
      }
      if (ref) learn(header, ref);
    });
    if (added.length) {
      persistVisualOrder(displayRows, [...dataSpec.fields.map((f) => f.ref), ...added]);
    }
  };
  const addedCount = Object.entries(choice).filter(([, ref]) => ref && selected.has(ref)).length;

  // ---- waiting state ----
  if (busy) {
    return (
      <Box sx={{ textAlign: "center", py: 3 }}>
        <AutoAwesome sx={{ fontSize: 36, color: "#007499" }} />
        <Typography sx={{ fontWeight: 600, mt: 1 }}>Reviewing “{fileName}”</Typography>
        <Typography variant="body2" sx={{ minHeight: 40, mt: 0.5 }}>{STAGES[stage]}</Typography>
        <LinearProgress sx={{ mt: 1.5, borderRadius: 2 }} />
      </Box>
    );
  }

  // ---- mapping review ----
  if (mappings.length > 0) {
    return (
      <Box>
        <Stack direction="row" spacing={1} alignItems="center" mb={0.5}>
          <CheckCircle sx={{ color: "#007499" }} fontSize="small" />
          <Typography sx={{ fontWeight: 600, flex: 1 }}>
            We matched {mappings.filter((m) => m.suggested_ref).length} of {mappings.length} columns
          </Typography>
          {rawFile && (
            <Button size="small" startIcon={<VisibilityOutlined />} onClick={openView}>
              View file
            </Button>
          )}
        </Stack>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          Review each one below — if a match looks wrong, just pick the right field. Clear a
          field to skip that column, or send it to a formula.
          {extraFields.length > 0
            ? " Use the arrows on green “added” rows to place them between your sheet columns."
            : ""}
        </Typography>
        <Alert severity="success" icon={<Lock fontSize="inherit" />} sx={{ mb: 1.5, py: 0.25 }}>
          The AI reviewed only your column names — your data rows were never sent to it. The
          sheet itself is saved with this report (encrypted) so you can preview it when editing.
        </Alert>

        {unmappedHeaders.length > 0 && (
          <ExcelMappingAIChat
            unmappedHeaders={unmappedHeaders}
            currentMapping={mappedHeaderRefs}
            onApply={(patch) => Object.entries(patch).forEach(([h, ref]) => changeMapping(h, ref))}
          />
        )}

        <Stack spacing={0.75}>
          {displayRows.map((row, rowI) => {
            if (row.kind === "extra") {
              const f = extraByRef.get(row.ref);
              if (!f) return null;
              const meta = fieldByRef.get(f.ref);
              const numeric = (!!meta && (meta.role === "measure" || meta.type === "integer" || meta.type === "decimal"))
                || AMOUNT_HINT.test(`${f.ref} ${f.label ?? ""}`);
              return (
                <Paper key={f.ref} variant="outlined" sx={{ p: 1, borderRadius: 2, display: "flex", alignItems: "center", gap: 1, bgcolor: "#F9FEFB" }}>
                  <Chip size="small" label="added" sx={{ height: 18, fontSize: "0.6rem", bgcolor: "#E6F4EA", color: "#1E7E34", flexShrink: 0 }} />
                  <TextField size="small" value={f.label ?? ""} onChange={(e) => setFieldLabel(f.ref, e.target.value)}
                    placeholder={f.ref.split(".").pop()} sx={{ flex: 1 }} />
                  {numeric && (
                    <Tooltip title={f.total ? "Column total shown — click to remove" : "Show a total (sum) at the bottom"}>
                      <Chip size="small" icon={<Functions />} label="Total" clickable
                        onClick={() => setFieldTotal(f.ref, !f.total)}
                        color={f.total ? "primary" : "default"} variant={f.total ? "filled" : "outlined"}
                        sx={{ height: 24, flexShrink: 0 }} />
                    </Tooltip>
                  )}
                  <Tooltip title={rowI === 0 ? "Already at the top" : "Move up (place between mapped columns)"}>
                    <span>
                      <IconButton size="small" disabled={rowI === 0} onClick={() => moveField(f.ref, -1)}>
                        <ArrowUpward fontSize="small" />
                      </IconButton>
                    </span>
                  </Tooltip>
                  <Tooltip title={rowI === displayRows.length - 1 ? "Already at the bottom" : "Move down"}>
                    <span>
                      <IconButton size="small" disabled={rowI === displayRows.length - 1} onClick={() => moveField(f.ref, 1)}>
                        <ArrowDownward fontSize="small" />
                      </IconButton>
                    </span>
                  </Tooltip>
                  <IconButton size="small" onClick={() => removeField(f.ref)}><CloseOutlined fontSize="small" /></IconButton>
                </Paper>
              );
            }
            const m = mappingByHeader.get(row.header);
            if (!m) return null;
            const ref = choice[m.header] ?? null;
            const added = ref ? selected.has(ref) : false;
            const badge = ref === m.suggested_ref && m.suggested_ref ? confBadge(m.confidence) : null;
            return (
              <Paper
                key={m.header}
                variant="outlined"
                sx={{ p: 1, borderRadius: 2, borderStyle: ref ? "solid" : "dashed" }}
              >
               <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                {/* source header from their sheet */}
                <Box sx={{ width: 150, flexShrink: 0, minWidth: 0 }}>
                  <Typography variant="body2" sx={{ fontWeight: 600 }} noWrap title={m.header}>
                    {m.header}
                  </Typography>
                  {m.source === "learned" && ref === m.suggested_ref ? (
                    <Chip size="small" label="learned"
                      sx={{ height: 16, fontSize: "0.6rem", bgcolor: "#EAF4F7", color: "#007499", mt: 0.25 }} />
                  ) : badge ? (
                    <Chip size="small" label={badge.label}
                      sx={{ height: 16, fontSize: "0.6rem", bgcolor: badge.bg, color: badge.fg, mt: 0.25 }} />
                  ) : null}
                </Box>

                <ArrowForward sx={{ fontSize: 15, color: "#9CA3AF", flexShrink: 0 }} />

                {/* the correctable mapping — searchable catalogue picker */}
                <Autocomplete
                  size="small"
                  sx={{ flex: 1, minWidth: 0 }}
                  options={options}
                  groupBy={(o) => o.entity}
                  getOptionLabel={(o) => o.label}
                  filterOptions={fieldFilter}
                  isOptionEqualToValue={(o, v) => o.ref === v.ref}
                  value={ref ? fieldByRef.get(ref) ?? null : null}
                  onChange={(_, v) => changeMapping(m.header, v?.ref ?? null)}
                  selectOnFocus
                  handleHomeEndKeys
                  noOptionsText="No field matches — try another word, ✨ Suggest, or Request in data"
                  renderOption={(props, o) => (
                    <li {...props} key={o.ref}>
                      <Box>
                        <Typography variant="body2">{o.label}</Typography>
                        <Typography variant="caption" color="text.secondary">{o.ref}</Typography>
                      </Box>
                    </li>
                  )}
                  renderInput={(p) => (
                    <TextField {...p} placeholder="Type to search fields — or clear to skip"
                      variant="outlined" />
                  )}
                />

                {/* actions: suggest + formula path + add/added */}
                <Tooltip title="Suggest matching fields">
                  <IconButton size="small" onClick={() => askSuggest(m.header)} disabled={suggBusy === m.header}>
                    {suggBusy === m.header
                      ? <CircularProgress size={16} />
                      : <AutoAwesome fontSize="small" sx={{ color: "#007499" }} />}
                  </IconButton>
                </Tooltip>
                <Tooltip title="Add logic for this column — formula, banding, lookup/mapping, or raw JSON">
                  <IconButton size="small" onClick={() => setDefineLabel(m.header)}>
                    <Functions fontSize="small" sx={{ color: "#9CA3AF" }} />
                  </IconButton>
                </Tooltip>
                {added ? (
                  <>
                    <Tooltip title="Rename this column (how it appears in the report)">
                      <TextField size="small" value={labelByRefSel.get(ref!) ?? ""}
                        onChange={(e) => ref && setFieldLabel(ref, e.target.value)}
                        placeholder="Show as…" sx={{ width: 140, flexShrink: 0 }}
                        slotProps={{ input: { startAdornment: (
                          <EditOutlined sx={{ fontSize: 14, color: "#9CA3AF", mr: 0.5 }} />
                        ) } }} />
                    </Tooltip>
                    {(() => {
                      const meta = ref ? fieldByRef.get(ref) : undefined;
                      const numeric = (!!meta && (meta.role === "measure" || meta.type === "integer" || meta.type === "decimal"))
                        || AMOUNT_HINT.test(`${ref ?? ""} ${m.header}`);
                      const totalOn = dataSpec.fields.find((x) => x.ref === ref)?.total ?? false;
                      return numeric ? (
                        <Tooltip title={totalOn ? "Column total shown — click to remove" : "Show a total (sum) at the bottom"}>
                          <Chip size="small" icon={<Functions />} label="Total" clickable
                            onClick={() => ref && setFieldTotal(ref, !totalOn)}
                            color={totalOn ? "primary" : "default"} variant={totalOn ? "filled" : "outlined"}
                            sx={{ height: 24, flexShrink: 0 }} />
                        </Tooltip>
                      ) : null;
                    })()}
                    <Chip size="small" color="primary" icon={<CheckCircle />} label="Added"
                      onDelete={() => ref && removeField(ref)} sx={{ flexShrink: 0 }} />
                  </>
                ) : (
                  <Button size="small" disabled={!ref} sx={{ flexShrink: 0 }}
                    onClick={() => { if (ref) { addMappedColumn(m.header, ref); learn(m.header, ref); } }}>
                    Add
                  </Button>
                )}
               </Box>

               {/* auto business-language gap note (same wording as the chat flow) */}
               {!ref && gaps[m.header] && (
                 <Box sx={{ mt: 0.75, ml: "158px", p: 1, borderRadius: 1.5,
                   bgcolor: gaps[m.header].status === "in_source" ? "#FFFBEB" : "#F3F4F6",
                   border: `1px solid ${gaps[m.header].status === "in_source" ? "#FDE68A" : "#E5E7EB"}` }}>
                   <Stack direction="row" spacing={0.75} alignItems="flex-start">
                     <ReportProblemOutlined sx={{ fontSize: 16, color: "#92400E", mt: "1px" }} />
                     <Typography sx={{ fontSize: "0.76rem", color: "#374151", flex: 1 }}>{gaps[m.header].message}</Typography>
                   </Stack>
                   {gaps[m.header].status === "in_source" && (
                     requested[m.header]
                       ? <Chip size="small" icon={<CheckCircle />} label="Requested"
                           sx={{ mt: 0.5, height: 22, fontSize: "0.68rem", bgcolor: "#E6F4EA", color: "#1E7E34" }} />
                       : <Button size="small" sx={{ mt: 0.25, textTransform: "none", fontSize: "0.72rem" }}
                           onClick={() => requestInData(m.header)}>Request it</Button>
                   )}
                 </Box>
               )}

               {/* suggestions for a column that didn't map — click to apply (then learned) */}
               {sugg[m.header] && (
                 <Box sx={{ mt: 0.75, pl: "158px" }}>
                   <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.5, alignItems: "center" }}>
                     {sugg[m.header].length === 0 ? (
                       <Typography variant="caption" color="text.secondary">No close fields:</Typography>
                     ) : (
                       <>
                         <Typography variant="caption" color="text.secondary" sx={{ mr: 0.5 }}>Did you mean:</Typography>
                         {sugg[m.header].map((s) => (
                           <Chip key={s.ref} size="small" variant="outlined" label={s.label}
                             title={`${s.ref} · ${s.reason}`} onClick={() => changeMapping(m.header, s.ref)}
                             sx={{ cursor: "pointer" }} />
                         ))}
                       </>
                     )}
                     <Tooltip title="Search the whole datamart (facts, dims, staging) for where this lives">
                       <Button size="small" disabled={discBusy === m.header}
                         startIcon={discBusy === m.header ? <CircularProgress size={13} /> : <TravelExploreOutlined />}
                         onClick={() => findInData(m.header)}>
                         Find in data
                       </Button>
                     </Tooltip>
                     {requested[m.header] ? (
                       <Chip size="small" icon={<CheckCircle />} label="Requested in data"
                         sx={{ bgcolor: "#FEF3C7", color: "#92400E" }} />
                     ) : (
                       <Tooltip title="Not captured yet? Flag it for the data team (shows on Data Health)">
                         <Button size="small" color="warning" startIcon={<ReportProblemOutlined />}
                           onClick={() => requestInData(m.header)}>
                           Request in data
                         </Button>
                       </Tooltip>
                     )}
                   </Box>

                   {/* drill-down result — where this concept lives across the layers */}
                   {disc[m.header] && (
                     <Box sx={{ mt: 0.5, p: 1, bgcolor: "#F9FAFB", border: "1px solid #E5E7EB", borderRadius: 1 }}>
                       <Typography variant="caption" sx={{ display: "block", color: "#374151", mb: disc[m.header].matches.length ? 0.5 : 0 }}>
                         {disc[m.header].summary}
                       </Typography>
                       {disc[m.header].matches.slice(0, 4).map((mm, i) => (
                         <Typography key={i} variant="caption"
                           sx={{ display: "block", color: "#6B7280", fontFamily: "ui-monospace, monospace", fontSize: "0.7rem" }}>
                           • <b style={{ color: mm.layer === "mart" ? "#1E7E34" : "#92400E" }}>{mm.layer}</b>
                           {" — "}{mm.schema}.{mm.table}.{mm.column}
                         </Typography>
                       ))}
                     </Box>
                   )}
                 </Box>
               )}
              </Paper>
            );
          })}
        </Stack>

        <CustomColumnDialog
          open={defineLabel != null}
          initialLabel={defineLabel ?? undefined}
          onClose={() => setDefineLabel(null)}
        />

        {/* Add a field that wasn't in the uploaded sheet */}
        <Box sx={{ mt: 1.5, p: 1.25, borderRadius: 2, border: "1px dashed #C4CAD2", bgcolor: "#FAFBFC" }}>
          <Stack direction="row" spacing={1} alignItems="center">
            <AddOutlined sx={{ fontSize: 18, color: "#007499" }} />
            <Typography variant="body2" sx={{ fontWeight: 600, flexShrink: 0 }}>Add another field</Typography>
            <Autocomplete
              size="small" sx={{ flex: 1, minWidth: 0 }} options={options} value={extra}
              groupBy={(o) => o.entity} getOptionLabel={(o) => o.label} filterOptions={fieldFilter}
              isOptionEqualToValue={(o, v) => o.ref === v.ref}
              onChange={(_, v) => addExtra(v)}
              renderOption={(props, o) => (
                <li {...props} key={o.ref}>
                  <Box><Typography variant="body2">{o.label}</Typography>
                    <Typography variant="caption" color="text.secondary">{o.ref}</Typography></Box>
                </li>
              )}
              renderInput={(p) => <TextField {...p} placeholder="Search a field not in your sheet…" />}
            />
          </Stack>
        </Box>

        {/* View uploaded file — parsed in the browser, rows never leave the device */}
        <Dialog open={viewOpen} onClose={() => setViewOpen(false)} maxWidth="lg" fullWidth>
          <DialogTitle sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <VisibilityOutlined sx={{ color: "#007499" }} />
            <Box sx={{ flex: 1 }}>
              <Typography sx={{ fontWeight: 600 }}>{fileName}</Typography>
              <Typography variant="caption" color="text.secondary">
                Previewed in your browser — data never leaves your device.
              </Typography>
            </Box>
            <IconButton onClick={() => setViewOpen(false)}><CloseOutlined /></IconButton>
          </DialogTitle>
          <DialogContent>
            {viewErr ? (
              <Alert severity="info">{viewErr}</Alert>
            ) : !viewData ? (
              <LinearProgress />
            ) : (
              <>
                <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1 }}>
                  {viewData.headers.length} columns · showing first {viewData.rows.length} rows
                </Typography>
                <TableContainer component={Paper} variant="outlined" sx={{ maxHeight: 460 }}>
                  <Table size="small" stickyHeader>
                    <TableHead>
                      <TableRow>
                        {viewData.headers.map((h, i) => (
                          <TableCell key={i} sx={{ fontWeight: 600, bgcolor: "#F9FAFB", whiteSpace: "nowrap" }}>{h}</TableCell>
                        ))}
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {viewData.rows.map((r, ri) => (
                        <TableRow key={ri} hover>
                          {viewData.headers.map((_, ci) => (
                            <TableCell key={ci} sx={{ whiteSpace: "nowrap", fontSize: "0.78rem" }}>{r[ci]}</TableCell>
                          ))}
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </>
            )}
          </DialogContent>
        </Dialog>

        <Stack direction="row" spacing={1} mt={2} alignItems="center">
          <Button variant="contained" endIcon={<ArrowForward />} disabled={mappedCount === 0}
            onClick={addAll}>
            Add all {mappedCount} mapped columns
          </Button>
          <Button component="label" size="small">
            Upload another
            <input hidden type="file" accept={UPLOAD_ACCEPT} onChange={onFile} />
          </Button>
        </Stack>
        {addedCount > 0 && (
          <Typography variant="caption" color="success.main" sx={{ display: "block", mt: 1 }}>
            ✓ {addedCount} added — see “Selected columns” below, then Run preview.
          </Typography>
        )}
        {mappedCount === 0 && (
          <Stack direction="row" spacing={0.5} alignItems="center" sx={{ mt: 1 }}>
            <BlockOutlined sx={{ fontSize: 15, color: "#9CA3AF" }} />
            <Typography variant="caption" color="text.secondary">
              Nothing mapped yet — pick a field for at least one column.
            </Typography>
          </Stack>
        )}
      </Box>
    );
  }

  // ---- idle / first upload ----
  return (
    <Box>
      <Paper variant="outlined" sx={{ p: 3, borderRadius: 2, borderStyle: "dashed", textAlign: "center", bgcolor: "#FAFBFC" }}>
        <CloudUpload sx={{ fontSize: 40, color: "#007499" }} />
        <Typography sx={{ fontWeight: 600, mt: 1 }}>Upload a sample of the report you want</Typography>
        <Typography variant="body2" sx={{ mb: 1.5 }}>
          Excel (.xlsx, .xls, .csv), PDF or an image with the columns/headings you need. Dummy or no data is fine.
        </Typography>
        <Button component="label" variant="contained" startIcon={<CloudUpload />}>
          Choose file
          <input hidden type="file" accept={UPLOAD_ACCEPT} onChange={onFile} />
        </Button>
      </Paper>
      {error && <Alert severity="error" sx={{ mt: 1.5 }}>{error}</Alert>}
      <Box sx={{ mt: 2 }}>
        <Typography variant="caption" sx={{ fontWeight: 600, color: "text.secondary" }}>HOW IT WORKS</Typography>
        <Stack spacing={0.5} mt={0.5}>
          {[
            "Export or make a sample sheet with your column headings.",
            "Upload it here — we read only the headings, never the data.",
            "We match each heading to a report field — change any that look wrong.",
            "Preview with real data, then Publish.",
          ].map((s, i) => (
            <Stack key={i} direction="row" spacing={1} alignItems="flex-start">
              <Chip size="small" label={i + 1} sx={{ height: 20, minWidth: 20 }} />
              <Typography variant="body2">{s}</Typography>
            </Stack>
          ))}
        </Stack>
      </Box>
    </Box>
  );
}
