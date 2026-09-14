// Canonical metrics admin — define governed named measures (Headcount, Total Net
// Pay, ratios) once, so they mean the same thing in every report. Defining one
// validates it compiles server-side; invalid definitions are rejected.
import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert, Box, Button, Card, CardContent, Chip, CircularProgress, FormControlLabel,
  MenuItem, Snackbar, Stack, Switch, TextField, ToggleButton, ToggleButtonGroup, Typography,
} from "@mui/material";
import { FunctionsOutlined, AddCircleOutline } from "@mui/icons-material";
import { metricApi, semanticApi } from "../../api/client";
import { FieldSelect } from "../documents/FieldSelect";
import type { MetricDef } from "../../types/metric";

const UNITS = ["currency", "count", "percent", "number"];
const AGGS = ["sum", "avg", "min", "max"];
const blank: MetricDef = { key: "", label: "", unit: "currency", kind: "aggregate", agg: "sum", ref: null, distinct: false, expression: "" };

export function MetricsPage() {
  const qc = useQueryClient();
  const { data: metrics = [], isLoading } = useQuery({ queryKey: ["metrics"], queryFn: metricApi.list });
  const { data: fields = [] } = useQuery({ queryKey: ["fields"], queryFn: semanticApi.fields });
  const realFields = useMemo(() => fields.filter((f) => f.entity !== "Metrics"), [fields]);
  const measures = useMemo(() => realFields.filter((f) => f.role === "measure"), [realFields]);

  const [m, setM] = useState<MetricDef>(blank);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [snack, setSnack] = useState("");
  const set = (p: Partial<MetricDef>) => setM((cur) => ({ ...cur, ...p }));

  const save = async () => {
    setBusy(true); setError("");
    const payload: MetricDef = {
      ...m,
      key: m.key.trim().toLowerCase().replace(/\s+/g, "_"),
      ref: m.kind === "formula" ? null : m.ref,
      agg: m.kind === "aggregate" ? m.agg : null,
      expression: m.kind === "formula" ? m.expression : null,
    };
    try {
      await metricApi.define(payload);
      qc.invalidateQueries({ queryKey: ["metrics"] });
      qc.invalidateQueries({ queryKey: ["fields"] });
      setSnack(`✓ Metric “${payload.label}” saved.`);
      setM(blank);
    } catch (e: unknown) {
      setError((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Could not save the metric.");
    } finally { setBusy(false); }
  };

  const seed = async () => {
    setBusy(true);
    try {
      const r = await metricApi.seedDefaults();
      qc.invalidateQueries({ queryKey: ["metrics"] });
      qc.invalidateQueries({ queryKey: ["fields"] });
      setSnack(r.created.length ? `✓ Added ${r.created.join(", ")}.` : "All default metrics already exist.");
    } finally { setBusy(false); }
  };

  const valid = m.key.trim() && m.label.trim() &&
    (m.kind === "formula" ? Boolean(m.expression?.trim()) : Boolean(m.ref));

  return (
    <Box sx={{ maxWidth: 980, mx: "auto" }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 0.5 }}>
        <Typography variant="h4">Metrics</Typography>
        <Button variant="outlined" startIcon={<FunctionsOutlined />} disabled={busy} onClick={seed}>
          Seed defaults
        </Button>
      </Stack>
      <Typography variant="body2" sx={{ mb: 3 }}>
        A metric is the single, governed definition of a business number, so “Headcount” or “Total Net Pay”
        means the same thing in every report. They appear in the builder field picker under <b>Metrics</b>.
      </Typography>

      <Box sx={{ display: "grid", gap: 2.5, alignItems: "start", gridTemplateColumns: { xs: "1fr", lg: "minmax(0,1fr) minmax(340px,400px)" } }}>
        {/* Existing metrics */}
        <Stack spacing={1.25}>
          {isLoading ? (
            <Box sx={{ textAlign: "center", py: 6 }}><CircularProgress /></Box>
          ) : metrics.length === 0 ? (
            <Card><CardContent sx={{ textAlign: "center", py: 5, color: "text.secondary" }}>
              <FunctionsOutlined sx={{ fontSize: 34, color: "#C4CAD2" }} />
              <Typography sx={{ fontWeight: 600, mt: 1 }}>No metrics yet</Typography>
              <Typography variant="body2">Seed the defaults or define one on the right.</Typography>
            </CardContent></Card>
          ) : metrics.map((x) => (
            <Card key={x.key}><CardContent sx={{ py: 1.5 }}>
              <Stack direction="row" justifyContent="space-between" alignItems="center">
                <Box>
                  <Typography sx={{ fontWeight: 600 }}>{x.label}</Typography>
                  <Typography variant="caption" sx={{ fontFamily: "ui-monospace, Menlo, monospace", color: "#6B7280" }}>
                    metric.{x.key} = {defSummary(x)}
                  </Typography>
                </Box>
                <Stack direction="row" spacing={0.5}>
                  {x.unit && <Chip size="small" label={x.unit} />}
                  <Chip size="small" color={x.source === "custom" ? "primary" : "default"} label={x.kind} />
                </Stack>
              </Stack>
            </CardContent></Card>
          ))}
        </Stack>

        {/* Define form */}
        <Card sx={{ position: { lg: "sticky" }, top: { lg: 76 } }}>
          <CardContent>
            <Typography variant="h6" sx={{ mb: 1.5 }}>Define a metric</Typography>
            <Stack spacing={1.5}>
              <Stack direction="row" spacing={1.5}>
                <TextField size="small" label="Key" placeholder="net_pay" value={m.key}
                  onChange={(e) => set({ key: e.target.value })} sx={{ flex: 1 }} />
                <TextField select size="small" label="Unit" value={m.unit ?? "number"}
                  onChange={(e) => set({ unit: e.target.value })} sx={{ width: 120 }}>
                  {UNITS.map((u) => <MenuItem key={u} value={u}>{u}</MenuItem>)}
                </TextField>
              </Stack>
              <TextField size="small" label="Label" placeholder="Net Pay" value={m.label}
                onChange={(e) => set({ label: e.target.value })} fullWidth />

              <ToggleButtonGroup exclusive size="small" color="primary" value={m.kind}
                onChange={(_, v) => v && set({ kind: v })} fullWidth>
                <ToggleButton value="aggregate" sx={{ textTransform: "none" }}>Aggregate</ToggleButton>
                <ToggleButton value="count" sx={{ textTransform: "none" }}>Count</ToggleButton>
                <ToggleButton value="formula" sx={{ textTransform: "none" }}>Formula</ToggleButton>
              </ToggleButtonGroup>

              {m.kind === "aggregate" && (
                <Stack spacing={1.25}>
                  <TextField select size="small" label="Aggregation" value={m.agg ?? "sum"}
                    onChange={(e) => set({ agg: e.target.value })}>
                    {AGGS.map((a) => <MenuItem key={a} value={a}>{a}</MenuItem>)}
                  </TextField>
                  <FieldSelect fields={measures} value={m.ref ?? null} onChange={(ref) => set({ ref })}
                    placeholder="Measure field" minWidth={0} />
                </Stack>
              )}
              {m.kind === "count" && (
                <Stack spacing={1.25}>
                  <FieldSelect fields={realFields} value={m.ref ?? null} onChange={(ref) => set({ ref })}
                    placeholder="Field to count" minWidth={0} />
                  <FormControlLabel control={<Switch checked={Boolean(m.distinct)} onChange={(e) => set({ distinct: e.target.checked })} />}
                    label={<Typography variant="body2">Count distinct</Typography>} />
                </Stack>
              )}
              {m.kind === "formula" && (
                <>
                  <TextField size="small" label="Expression" value={m.expression ?? ""}
                    onChange={(e) => set({ expression: e.target.value })} fullWidth
                    placeholder="metric.total_gross - metric.total_deductions" />
                  <Typography variant="caption" color="text.secondary">
                    Arithmetic over other metrics only: {metrics.map((x) => `metric.${x.key}`).join(", ") || "(define some first)"}
                  </Typography>
                </>
              )}

              {error && <Alert severity="error">{error}</Alert>}
              <Button variant="contained" startIcon={<AddCircleOutline />} disabled={!valid || busy} onClick={save}>
                Save metric
              </Button>
            </Stack>
          </CardContent>
        </Card>
      </Box>

      <Snackbar open={Boolean(snack)} autoHideDuration={5000} onClose={() => setSnack("")}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}>
        <Alert severity="success" variant="filled" onClose={() => setSnack("")}>{snack}</Alert>
      </Snackbar>
    </Box>
  );
}

function defSummary(m: MetricDef): string {
  if (m.kind === "formula") return m.expression || "";
  if (m.kind === "count") return `count(${m.distinct ? "distinct " : ""}${m.ref})`;
  return `${m.agg}(${m.ref})`;
}
