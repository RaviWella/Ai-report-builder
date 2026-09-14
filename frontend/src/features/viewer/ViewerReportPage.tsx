// View a single published template — the COMMON Generate for both tabular
// reports and per-employee payslips. Same runtime filters (period, employee);
// the kind + allowed formats decide whether a table/Search shows and which
// download buttons appear.
import { useParams } from "react-router-dom";
import { useCallback, useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Alert, Box, Button, Card, CardContent, Chip, CircularProgress, Stack,
  TablePagination, Typography,
} from "@mui/material";
import { Search, GridOn, PictureAsPdf, ReceiptLongOutlined, BuildOutlined } from "@mui/icons-material";
import { reportApi, templateApi, exportApi } from "../../api/client";
import { FilterBar, type FilterValues } from "./FilterBar";
import type { QueryResult } from "../../types/spec";
import { useNavigate } from "react-router-dom";
import { WideReportTable } from "../../components/WideReportTable";

interface Tpl { id: string; name: string; module?: string; }

const filterStorageKey = (templateId: string) => `viewer-filters:${templateId}`;

function readStoredFilters(templateId: string): FilterValues | undefined {
  if (!templateId) return undefined;
  try {
    const raw = sessionStorage.getItem(filterStorageKey(templateId));
    return raw ? (JSON.parse(raw) as FilterValues) : undefined;
  } catch {
    return undefined;
  }
}

export function ViewerReportPage() {
  const navigate = useNavigate();
  const { templateId = "" } = useParams();
  const { data: templates = [] } = useQuery({ queryKey: ["templates"], queryFn: templateApi.list });
  const tpl = (templates as Tpl[]).find((t) => t.id === templateId);
  const { data: meta, isError: metaError, error: metaErr } = useQuery({
    queryKey: ["view-meta", templateId],
    queryFn: () => reportApi.viewMeta(templateId),
    enabled: Boolean(templateId),
    retry: false,
  });
  const metaDetail = (metaErr as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "";
  const draftOnly = metaError && /no published version/i.test(metaDetail);

  const kind = meta?.kind ?? "report";
  const allowed = meta?.allowed_formats ?? ["view", "excel", "pdf"];
  // Friendly column titles for rule reports (falls back to the raw field name).
  const colLabels: Record<string, string> = (meta as { labels?: Record<string, string> })?.labels ?? {};
  // A friendly title if the builder set one; otherwise prettify the raw field name
  // (underscores -> spaces, first letter of each word capitalised) — not ALL CAPS.
  const prettyCol = (c: string) => c.replace(/_/g, " ").replace(/\b\w/g, (m) => m.toUpperCase());
  const colLabel = (c: string) => colLabels[c] ?? prettyCol(c);
  // JSON serializes dates/times/timestamps as plain ISO strings (e.g.
  // "2026-06-06T06:16:00+05:30" for a timestamptz straight from Postgres, or
  // "14:05:00" for a bare time column) — shown raw that's unreadable. Trim to
  // "YYYY-MM-DD HH:MM" / "HH:MM"; anything else prints as-is.
  const ISO_DATETIME_TZ = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}):\d{2}(?:\.\d+)?(?:[+-]\d{2}:\d{2}|Z)?$/;
  const ISO_TIME = /^(\d{2}:\d{2}):\d{2}(?:\.\d+)?$/;
  const cellText = (value: unknown): string => {
    if (value === null || value === undefined) return "";
    if (typeof value === "string") {
      const dt = value.match(ISO_DATETIME_TZ);
      if (dt) return `${dt[1]} ${dt[2]}`;
      const t = value.match(ISO_TIME);
      if (t) return t[1];
    }
    return String(value);
  };
  const dq = meta?.data_quality;
  const isDocument = kind === "document";
  const canView = !isDocument && allowed.includes("view");
  const canExcel = allowed.includes("excel");
  const canPdf = allowed.includes("pdf");

  const [filters, setFilters] = useState<FilterValues>({});
  const [missingRequired, setMissingRequired] = useState<string[]>([]);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [error, setError] = useState("");
  const [running, setRunning] = useState(false);
  const [downloading, setDownloading] = useState("");
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(12);

  const [metaReady, setMetaReady] = useState(false);
  /** Initial auto-run after refresh — debounced so required period filters can pre-select first. */
  const initialRunDone = useRef(false);
  const [storedFilters] = useState(() => readStoredFilters(templateId));

  const onFilters = useCallback((v: FilterValues) => setFilters(v), []);
  const onValidity = useCallback((m: string[]) => setMissingRequired(m), []);
  const onReady = useCallback(() => setMetaReady(true), []);
  const blocked = missingRequired.length > 0;

  // Keep the user's filter choices across hard refresh so auto-run matches what they had.
  useEffect(() => {
    if (!templateId || !Object.keys(filters).length) return;
    try {
      sessionStorage.setItem(filterStorageKey(templateId), JSON.stringify(filters));
    } catch { /* quota / private mode */ }
  }, [templateId, filters]);

  const run = async (params: FilterValues = filters) => {
    setError(""); setRunning(true); setPage(0);
    try { setResult(await reportApi.run(templateId, params)); }
    catch (e: unknown) { setError((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Run failed"); }
    finally { setRunning(false); }
  };

  // Reset per template (the component is reused across /viewer/r/:id changes).
  useEffect(() => {
    initialRunDone.current = false;
    setMetaReady(false); setResult(null); setError(""); setMissingRequired([]);
  }, [templateId]);

  // Auto-run once filters are ready (wait briefly so enum/period defaults apply after refresh).
  useEffect(() => {
    if (!canView || !metaReady || blocked || initialRunDone.current) return;
    const t = window.setTimeout(() => {
      initialRunDone.current = true;
      run(filters);
    }, 350);
    return () => window.clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canView, metaReady, blocked, filters]);

  const download = async (fmt: "xlsx" | "pdf") => {
    setDownloading(fmt);
    try { await exportApi.download(templateId, fmt, filters); }
    catch (e: unknown) { setError((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Download failed"); }
    finally { setDownloading(""); }
  };

  return (
    <Box sx={{ minWidth: 0, maxWidth: "100%" }}>
      <Stack direction="row" spacing={1.5} alignItems="center" sx={{ mb: 2 }}>
        <Typography variant="h4">{tpl?.name ?? (isDocument ? "Document" : "Report")}</Typography>
        {isDocument && <Chip size="small" icon={<ReceiptLongOutlined />} label="Document" color="primary" />}
      </Stack>

      {metaError && (
        <Alert severity={draftOnly ? "warning" : "error"} sx={{ mb: 2 }}>
          {draftOnly ? (
            <>
              This report is <b>draft only</b> — publish a version from Templates first, then Run again.
              While editing, use <b>Preview</b> in the Builder to test your columns and rules.
            </>
          ) : (
            metaDetail || "Couldn't load this report."
          )}
          {draftOnly && (
            <Button size="small" startIcon={<BuildOutlined />} sx={{ mt: 1, display: "block" }}
              onClick={() => navigate(kind === "rule_report" ? `/rule-reports/${templateId}` : `/builder/${templateId}`)}>
              Open in Builder
            </Button>
          )}
        </Alert>
      )}

      {!metaError && (
      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Stack direction={{ xs: "column", lg: "row" }} spacing={2} alignItems={{ lg: "center" }} justifyContent="space-between">
            <Box sx={{ flex: 1 }}>
              <FilterBar
                templateId={templateId}
                initialValues={storedFilters}
                onChange={onFilters}
                onValidity={onValidity}
                onReady={onReady}
              />
            </Box>
            <Stack direction="row" spacing={1.5} alignItems="center">
              {canView && (
                <Button variant="contained" onClick={() => run()} disabled={running || blocked}
                  startIcon={running ? <CircularProgress size={16} color="inherit" /> : <Search />}>
                  {running ? "Searching…" : "Search"}
                </Button>
              )}
              {canExcel && (
                <Button variant="outlined" onClick={() => download("xlsx")} disabled={!!downloading || blocked}
                  startIcon={downloading === "xlsx" ? <CircularProgress size={16} /> : <GridOn />}>Excel</Button>
              )}
              {canPdf && (
                <Button variant={isDocument ? "contained" : "outlined"} onClick={() => download("pdf")} disabled={!!downloading || blocked}
                  startIcon={downloading === "pdf" ? <CircularProgress size={16} color="inherit" /> : <PictureAsPdf />}>
                  {isDocument ? "Download documents" : "PDF"}
                </Button>
              )}
            </Stack>
          </Stack>
          {blocked && (
            <Typography variant="caption" color="warning.main" sx={{ display: "block", mt: 1 }}>
              Select to continue: {missingRequired.join(", ")}
            </Typography>
          )}
        </CardContent>
      </Card>
      )}

      {/* WS-3 serve policy — warn when a critical data-quality assertion is failing. */}
      {dq?.critical_failure && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          A critical data-quality check is currently failing for this tenant's data.
          Numbers in this report may be unreliable until it's resolved.
        </Alert>
      )}

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {/* Document: no on-screen table — it's a per-record PDF. */}
      {isDocument && !error && (
        <Card>
          <CardContent sx={{ textAlign: "center", py: 5, color: "text.secondary" }}>
            <ReceiptLongOutlined sx={{ fontSize: 34, color: "#C4CAD2" }} />
            <Typography sx={{ fontWeight: 600, mt: 1 }}>One PDF, a page per record</Typography>
            <Typography variant="body2">
              Choose the period (and a record key for a single one), then download.
            </Typography>
          </CardContent>
        </Card>
      )}

      {canView && running && !result && (
        <Box sx={{ textAlign: "center", py: 6 }}>
          <CircularProgress />
          <Typography variant="body2" sx={{ mt: 1.5 }}>Running the report…</Typography>
        </Box>
      )}

      {canView && result && (
        <>
          <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
            <Typography variant="body2">
              {result.row_count} rows · {result.columns.length} columns
            </Typography>
            {result.truncated && <Typography variant="caption" color="warning.main">Showing first {result.rows.length}</Typography>}
          </Stack>
          <WideReportTable
            columns={result.columns}
            rows={result.rows.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage)}
            colLabel={colLabel}
            cellText={cellText}
            footer={(
              <TablePagination
                component="div"
                count={result.rows.length}
                page={page}
                onPageChange={(_, p) => setPage(p)}
                rowsPerPage={rowsPerPage}
                onRowsPerPageChange={(e) => { setRowsPerPage(parseInt(e.target.value, 10)); setPage(0); }}
                rowsPerPageOptions={[12, 25, 50, 100]}
                labelRowsPerPage="Per page"
                sx={{
                  border: "1px solid",
                  borderTop: "none",
                  borderColor: "divider",
                  borderRadius: "0 0 8px 8px",
                }}
              />
            )}
          />
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.5 }}>
            The table is paginated; Excel / PDF export the full {result.row_count} rows.
          </Typography>
          {result.provenance?.run_id && (
            <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.25, fontFamily: "ui-monospace, Menlo, monospace" }}>
              {result.provenance.semantic_version_ref != null && `catalogue v${result.provenance.semantic_version_ref} · `}
              run {result.provenance.run_id.slice(0, 8)}
              {result.provenance.datamart_snapshot_ref && ` · data ${result.provenance.datamart_snapshot_ref}`}
              {result.provenance.result_checksum && ` · checksum ${result.provenance.result_checksum.slice(0, 12)}`}
            </Typography>
          )}
        </>
      )}
    </Box>
  );
}
