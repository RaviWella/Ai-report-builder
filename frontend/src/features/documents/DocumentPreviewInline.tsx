// Preview dialog used from the canvas designer — takes a saved template id + type
// directly (the studio variant takes a list item). Renders composed HTML in a
// sandboxed iframe with period controls.
import { useEffect, useState } from "react";
import {
  Alert, Box, Button, CircularProgress, Dialog, DialogContent, DialogTitle, FormControlLabel,
  MenuItem, Stack, Switch, TextField, Typography,
} from "@mui/material";
import { documentApi, type DocPreview } from "../../api/client";
import type { DocType, DesignManualField } from "../../types/document";
import { manualFieldsOf } from "../../types/document";

const now = new Date();

export function DocumentPreviewInline({
  id, docType, onClose,
}: {
  id: string;
  docType: DocType;
  onClose: () => void;
}) {
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [recordKey, setRecordKey] = useState("");
  const [needsPeriod, setNeedsPeriod] = useState(false);
  const [needsRecord, setNeedsRecord] = useState(false);
  const [manualFields, setManualFields] = useState<DesignManualField[]>([]);
  const [manualVals, setManualVals] = useState<Record<string, string>>({});
  const [data, setData] = useState<DocPreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [labelled, setLabelled] = useState(false);  // show [Field Label] instead of data

  // Only ask for what this design actually scopes on (letters usually just employee).
  useEffect(() => {
    documentApi.get(id).then((d) => {
      setNeedsPeriod(Boolean(d.design?.period_year_ref && d.design?.period_month_ref));
      setNeedsRecord(Boolean(d.design?.record_key_ref));
      setManualFields(manualFieldsOf(d.design));
    }).catch(() => {});
  }, [id]);

  const load = async () => {
    setBusy(true); setErr("");
    try {
      setData(await documentApi.preview(id, {
        year: needsPeriod ? year : null, month: needsPeriod ? month : null,
        record_key: needsRecord && recordKey.trim() ? recordKey.trim() : null, labelled,
        manual: manualVals,
      }));
    }
    catch (e) { setErr((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Couldn’t build a preview."); }
    finally { setBusy(false); }
  };
  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [labelled]);

  return (
    <Dialog open onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle sx={{ fontSize: "1rem" }}>Preview</DialogTitle>
      <DialogContent dividers>
        <Stack direction="row" spacing={1.5} alignItems="center" sx={{ mb: 1.5 }} flexWrap="wrap">
          {needsRecord && (
            <TextField size="small" label="Employee ID" value={recordKey} onChange={(e) => setRecordKey(e.target.value)}
              sx={{ width: 160 }} placeholder="blank = first match" />
          )}
          {needsPeriod && (
            <>
              <TextField size="small" type="number" label="Year" value={year} onChange={(e) => setYear(Number(e.target.value))} sx={{ width: 110 }} />
              <TextField select size="small" label="Month" value={month} onChange={(e) => setMonth(Number(e.target.value))} sx={{ width: 120 }}>
                {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => <MenuItem key={m} value={m}>{m}</MenuItem>)}
              </TextField>
            </>
          )}
          <Button variant="outlined" size="small" onClick={load} disabled={busy}>Refresh</Button>
          <FormControlLabel control={<Switch size="small" checked={labelled} onChange={(e) => setLabelled(e.target.checked)} />}
            label={<Typography variant="body2">Labelled placeholders</Typography>} />
          {data && !labelled && <Typography variant="caption" color="text.secondary">{data.record_count} matching record{data.record_count === 1 ? "" : "s"} — showing the first</Typography>}
        </Stack>
        {manualFields.length > 0 && !labelled && (
          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap sx={{ mb: 1.5 }}>
            <Typography variant="caption" color="text.secondary">Manual values:</Typography>
            {manualFields.map((m) => (
              <TextField key={m.key} size="small" label={m.label} value={manualVals[m.key] ?? ""}
                onChange={(e) => setManualVals((v) => ({ ...v, [m.key]: e.target.value }))} sx={{ width: 160 }} />
            ))}
            <Button variant="text" size="small" onClick={load} disabled={busy}>Apply</Button>
          </Stack>
        )}
        {busy && <Box sx={{ textAlign: "center", py: 4 }}><CircularProgress size={26} /></Box>}
        {err && <Alert severity="error">{err}</Alert>}
        {data && !busy && (
          <>
            {docType === "email" && (
              <Box sx={{ mb: 1, p: 1, bgcolor: "#F3F4F6", borderRadius: 1 }}>
                <Typography variant="caption" color="text.secondary">Subject</Typography>
                <Typography sx={{ fontWeight: 600 }}>{data.subject || "(no subject)"}</Typography>
              </Box>
            )}
            <Box sx={{ border: "1px solid #E5E7EB", borderRadius: 1, overflow: "hidden", bgcolor: "#fff" }}>
              <iframe title="preview" srcDoc={data.html} style={{ width: "100%", height: "60vh", border: 0 }} />
            </Box>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
