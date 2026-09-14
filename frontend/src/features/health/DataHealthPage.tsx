// Data Health — the catalogue's data-capture coverage. Runs the coverage audit
// (POST /validations/coverage) and shows, per field, how populated its datamart
// column is: ok / empty (0%) / missing (column gone). Surfaces the gaps that make
// a correct mapping return blank data (e.g. an empty department column).
import { useEffect, useMemo, useState } from "react";
import {
  Alert, Box, Button, Card, CardContent, Chip, CircularProgress, LinearProgress,
  Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  ToggleButton, ToggleButtonGroup, Typography,
} from "@mui/material";
import {
  HealthAndSafetyOutlined, RefreshOutlined, ReportProblemOutlined,
  CheckCircleOutline, CloseOutlined,
} from "@mui/icons-material";
import { IconButton, Tooltip } from "@mui/material";
import {
  validationsApi, type CoverageReport, type CoverageField, type FieldRequest,
} from "../../api/client";

const TEAL = "#007499";

function Stat({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <Card sx={{ flex: 1, minWidth: 120 }}>
      <CardContent sx={{ py: 1.5 }}>
        <Typography sx={{ fontSize: "1.6rem", fontWeight: 700, color, lineHeight: 1 }}>{value}</Typography>
        <Typography variant="body2" color="text.secondary">{label}</Typography>
      </CardContent>
    </Card>
  );
}

const STATUS = {
  ok: { label: "ok", bg: "#E6F4EA", fg: "#1E7E34" },
  empty: { label: "empty", bg: "#FFF0ED", fg: "#C13515" },
  missing: { label: "missing", bg: "#FEF3C7", fg: "#92400E" },
  error: { label: "error", bg: "#F3F4F6", fg: "#6B7280" },
} as const;

export function DataHealthPage() {
  const [report, setReport] = useState<CoverageReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [filter, setFilter] = useState<"gaps" | "all">("gaps");
  const [requests, setRequests] = useState<FieldRequest[]>([]);

  const run = () => {
    setLoading(true); setErr("");
    validationsApi.coverage()
      .then(setReport)
      .catch((e: unknown) => setErr((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Audit failed (datamart/VPN?)"))
      .finally(() => setLoading(false));
  };
  const loadRequests = () => { validationsApi.fieldRequests().then(setRequests).catch(() => {}); };
  useEffect(() => { run(); loadRequests(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);

  const openRequests = requests.filter((r) => r.status === "open");

  const rows = useMemo(() => {
    const all = report?.results ?? [];
    return filter === "gaps" ? all.filter((r) => r.status !== "ok") : all;
  }, [report, filter]);

  const s = report?.summary;
  const pct = (r: CoverageField) => (r.coverage == null ? null : Math.round(r.coverage * 100));

  return (
    <Box sx={{ maxWidth: 1000 }}>
      <Stack direction="row" alignItems="center" sx={{ mb: 0.5 }} spacing={1}>
        <HealthAndSafetyOutlined sx={{ color: TEAL }} />
        <Typography variant="h4" sx={{ flex: 1 }}>Data Health</Typography>
        <Button variant="outlined" startIcon={loading ? <CircularProgress size={15} /> : <RefreshOutlined />}
          onClick={run} disabled={loading}>{loading ? "Auditing…" : "Re-run audit"}</Button>
      </Stack>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        How populated is every catalogue field’s datamart column. <b>Empty</b> fields map
        correctly but carry no data (a data-capture/ETL gap) — a report using them looks blank.
      </Typography>

      {err && <Alert severity="error" sx={{ mb: 2 }}>{err}</Alert>}
      {loading && !report && <LinearProgress sx={{ mb: 2 }} />}

      {openRequests.length > 0 && (
        <Card variant="outlined" sx={{ mb: 2, borderColor: "#FDE68A", bgcolor: "#FFFBEB" }}>
          <CardContent sx={{ py: 1.5 }}>
            <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1 }}>
              <ReportProblemOutlined sx={{ color: "#92400E" }} fontSize="small" />
              <Typography sx={{ fontWeight: 600, color: "#92400E", flex: 1 }}>
                Requested fields — not in your data yet ({openRequests.length})
              </Typography>
            </Stack>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              Users asked for these columns during upload but no field exists — a data-capture
              gap for the ETL team to expose. Resolve once the field is available.
            </Typography>
            <Table size="small">
              <TableHead>
                <TableRow>
                  {["Requested column", "Times", "Last asked", ""].map((h) => (
                    <TableCell key={h} sx={{ fontWeight: 600 }}>{h}</TableCell>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {openRequests.map((r) => (
                  <TableRow key={r.id} hover>
                    <TableCell>{r.header}</TableCell>
                    <TableCell>{r.hits}</TableCell>
                    <TableCell sx={{ color: "#6B7280" }}>
                      {r.last_requested_at ? new Date(r.last_requested_at).toLocaleDateString() : "—"}
                    </TableCell>
                    <TableCell align="right">
                      <Tooltip title="Mark resolved (field now available)">
                        <IconButton size="small" onClick={() => validationsApi.resolveFieldRequest(r.id).then(loadRequests)}>
                          <CheckCircleOutline fontSize="small" sx={{ color: "#1E7E34" }} />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Dismiss">
                        <IconButton size="small" onClick={() => validationsApi.deleteFieldRequest(r.id).then(loadRequests)}>
                          <CloseOutlined fontSize="small" sx={{ color: "#9CA3AF" }} />
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {s && (
        <>
          <Stack direction="row" spacing={1.5} sx={{ mb: 2, flexWrap: "wrap" }}>
            <Stat label="Fields" value={s.fields} color="#1A1A1A" />
            <Stat label="Populated" value={s.ok} color="#1E7E34" />
            <Stat label="Empty" value={s.empty} color="#C13515" />
            <Stat label="Missing" value={s.missing} color="#92400E" />
          </Stack>

          <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
            <Typography variant="body2" color="text.secondary">
              {s.empty + s.missing === 0
                ? "✅ No data-capture gaps — every mapped field has data."
                : `${s.empty + s.missing} field(s) need attention (escalate to ETL).`}
            </Typography>
            <ToggleButtonGroup size="small" exclusive value={filter} onChange={(_, v) => v && setFilter(v)}>
              <ToggleButton value="gaps">Gaps only</ToggleButton>
              <ToggleButton value="all">All fields</ToggleButton>
            </ToggleButtonGroup>
          </Stack>

          <TableContainer component={Card} variant="outlined">
            <Table size="small" stickyHeader>
              <TableHead>
                <TableRow>
                  {["Field", "Entity", "Column", "Coverage", "Status"].map((h) => (
                    <TableCell key={h} sx={{ fontWeight: 600, bgcolor: "#F9FAFB" }}>{h}</TableCell>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {rows.map((r) => {
                  const st = STATUS[r.status as keyof typeof STATUS] ?? STATUS.error;
                  const p = pct(r);
                  return (
                    <TableRow key={r.ref} hover>
                      <TableCell>{r.label}</TableCell>
                      <TableCell sx={{ color: "#6B7280" }}>{r.entity}</TableCell>
                      <TableCell sx={{ fontFamily: "ui-monospace, monospace", fontSize: "0.76rem", color: "#6B7280" }}>{r.table}.{r.column}</TableCell>
                      <TableCell>{p == null ? "—" : `${p}%`}{r.total ? <span style={{ color: "#9CA3AF" }}> ({r.populated}/{r.total})</span> : null}</TableCell>
                      <TableCell><Chip size="small" label={st.label} sx={{ height: 20, fontSize: "0.66rem", bgcolor: st.bg, color: st.fg }} /></TableCell>
                    </TableRow>
                  );
                })}
                {rows.length === 0 && (
                  <TableRow><TableCell colSpan={5} sx={{ textAlign: "center", color: "text.secondary", py: 3 }}>
                    {filter === "gaps" ? "No gaps 🎉" : "No fields."}
                  </TableCell></TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </>
      )}
    </Box>
  );
}
