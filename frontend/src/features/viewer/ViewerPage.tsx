// Viewer panel (FR-V1..V4) — run a published report with runtime filters and
// download Excel/PDF. Cannot edit template definitions.
import { useParams } from "react-router-dom";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Alert, Box, Button, Card, CardContent, ListSubheader, MenuItem, Select, Stack,
  TextField, Typography,
} from "@mui/material";
import { REPORT_MODULES } from "../../store/builderStore";
import { PlayArrow, GridOn, PictureAsPdf } from "@mui/icons-material";
import { reportApi, templateApi, exportApi } from "../../api/client";
import type { QueryResult } from "../../types/spec";
import { WideReportTable } from "../../components/WideReportTable";

export function ViewerPage() {
  const { templateId } = useParams();
  const { data: templates = [] } = useQuery({ queryKey: ["templates"], queryFn: templateApi.list });
  type Tpl = { id: string; name: string; module?: string };
  const byModule = (templates as Tpl[]).reduce<Record<string, Tpl[]>>((acc, t) => {
    const m = t.module || "General";
    (acc[m] ??= []).push(t);
    return acc;
  }, {});
  const order = [...REPORT_MODULES as readonly string[]];
  const groupedReports = Object.entries(byModule).sort(
    (a, b) => (order.indexOf(a[0]) + 1 || 99) - (order.indexOf(b[0]) + 1 || 99),
  );
  const [selected, setSelected] = useState(templateId ?? "");
  const [params, setParams] = useState("{}");
  const [result, setResult] = useState<QueryResult | null>(null);
  const [error, setError] = useState("");

  const parseParams = () => { try { return JSON.parse(params || "{}"); } catch { return {}; } };

  const run = async () => {
    setError("");
    try {
      setResult(await reportApi.run(selected, parseParams()));
    } catch (e: unknown) {
      setError((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Run failed");
    }
  };

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 2 }}>Run a Report</Typography>
      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Stack direction={{ xs: "column", md: "row" }} spacing={1.5} alignItems={{ md: "center" }}>
            <Select size="small" displayEmpty value={selected} onChange={(e) => setSelected(e.target.value)} sx={{ minWidth: 260 }}>
              <MenuItem value=""><em>— select report —</em></MenuItem>
              {groupedReports.flatMap(([mod, list]) => [
                <ListSubheader key={mod}>{mod}</ListSubheader>,
                ...list.map((t) => <MenuItem key={t.id} value={t.id} sx={{ pl: 3 }}>{t.name}</MenuItem>),
              ])}
            </Select>
            <TextField size="small" sx={{ flex: 1, minWidth: 280 }} value={params} onChange={(e) => setParams(e.target.value)}
              placeholder='runtime params e.g. {"join_range":["2024-01-01","2024-12-31"]}' />
            <Button variant="contained" startIcon={<PlayArrow />} onClick={run} disabled={!selected}>Run</Button>
            <Button variant="outlined" startIcon={<GridOn />} onClick={() => exportApi.download(selected, "xlsx", parseParams())} disabled={!selected}>Excel</Button>
            <Button variant="outlined" startIcon={<PictureAsPdf />} onClick={() => exportApi.download(selected, "pdf", parseParams())} disabled={!selected}>PDF</Button>
          </Stack>
        </CardContent>
      </Card>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {result && (
        <WideReportTable columns={result.columns} rows={result.rows} />
      )}
    </Box>
  );
}
