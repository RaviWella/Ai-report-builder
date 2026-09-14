// Live preview (FR-B9) — runs the unsaved data_spec on a small sample. In the
// builder it runs in `auto` mode: it re-runs ~900ms after the spec settles, so
// the report stays in view as the user shapes it (the report is the subject).
import { useEffect, useRef, useState } from "react";
import {
  Alert, Box, Button, Chip, CircularProgress, Stack, Typography,
} from "@mui/material";
import { Refresh, TableChartOutlined } from "@mui/icons-material";
import { reportApi } from "../../api/client";
import { useBuilderStore } from "../../store/builderStore";
import type { QueryResult } from "../../types/spec";
import { WideReportTable } from "../../components/WideReportTable";

export function PreviewPane({ auto = false }: { auto?: boolean }) {
  const { dataSpec } = useBuilderStore();
  const [result, setResult] = useState<QueryResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const lastRun = useRef("");
  const hasCols = dataSpec.fields.length > 0 || dataSpec.aggregations.length > 0;

  const run = async () => {
    const snap = JSON.stringify(dataSpec);
    setError(""); setLoading(true);
    try {
      const r = await reportApi.previewSpec(dataSpec);
      lastRun.current = snap;
      setResult(r);
    } catch (e: unknown) {
      setError((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Preview failed");
    } finally {
      setLoading(false);
    }
  };

  // Auto-refresh: debounce so we run a sample only after edits settle, and skip
  // when the spec hasn't changed since the last successful run.
  useEffect(() => {
    if (!auto || !hasCols) return;
    if (JSON.stringify(dataSpec) === lastRun.current) return;
    const t = setTimeout(() => { void run(); }, 900);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auto, hasCols, dataSpec]);

  return (
    <Box>
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={1}>
        <Stack direction="row" spacing={1} alignItems="center">
          <Typography variant="h6">Preview</Typography>
          {loading && <CircularProgress size={14} thickness={5} />}
        </Stack>
        <Button variant="outlined" size="small" startIcon={<Refresh />} onClick={() => void run()}
          disabled={!hasCols || loading}>
          Refresh
        </Button>
      </Stack>

      {error && <Alert severity="error" sx={{ mb: 1 }}>{error}</Alert>}

      {!hasCols ? (
        <Box sx={{
          border: "1px dashed #E5E7EB", borderRadius: 2, py: 4, px: 2, textAlign: "center",
          color: "text.secondary", bgcolor: "#FAFBFC",
        }}>
          <TableChartOutlined sx={{ fontSize: 30, color: "#C4CAD2" }} />
          <Typography variant="body2" sx={{ mt: 0.5 }}>
            Your report appears here.
          </Typography>
          <Typography variant="caption" sx={{ display: "block" }}>
            Add columns and a live sample shows up automatically.
          </Typography>
        </Box>
      ) : result ? (
        <>
          {result.truncated && (
            <Chip size="small" color="warning" label={`Sample of ${result.rows.length} rows`} sx={{ mb: 1 }} />
          )}
          <WideReportTable columns={result.columns} rows={result.rows} maxHeight={440} />
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.75 }}>
            {result.truncated
              ? `Showing ${result.rows.length} of ${result.row_count} rows`
              : `${result.row_count} row${result.row_count === 1 ? "" : "s"}`}
          </Typography>
        </>
      ) : (
        <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
          {loading ? "Running a sample…" : "Refresh to see live sample rows."}
        </Typography>
      )}
    </Box>
  );
}
