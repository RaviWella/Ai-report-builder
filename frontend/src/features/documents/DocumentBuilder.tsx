// Dynamic document authoring: upload a one-page-per-record layout, review/fix the
// auto-mapped lines (arbitrary sections, not fixed to any domain), save & publish,
// then generate a PDF with one page per record. Also handles edit (/documents/:id/edit).
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Alert, Box, Button, Card, CardContent, Chip, CircularProgress, Divider, FormControlLabel,
  MenuItem, Paper, Snackbar, Stack, Step, StepLabel, Stepper, Switch, TextField, Typography,
} from "@mui/material";
import { CloudUpload, Lock, Save, Publish, PictureAsPdf } from "@mui/icons-material";
import { documentApi, semanticApi } from "../../api/client";
import { REPORT_MODULES } from "../../store/builderStore";
import type { DocumentSpec, DocumentLine } from "../../types/document";
import type { SemanticFieldMeta } from "../../types/spec";
import { FieldSelect } from "./FieldSelect";

const STEPS = ["Upload layout", "Review & map", "Save & generate"];
const now = new Date();
type Sev = "success" | "error";

export function DocumentBuilder() {
  const navigate = useNavigate();
  const { id: editingId } = useParams();
  const { data: fields = [] } = useQuery({ queryKey: ["fields", "builder"], queryFn: semanticApi.fieldsForBuilder });

  const [busy, setBusy] = useState(false);
  const [spec, setSpec] = useState<DocumentSpec | null>(null);
  const [conf, setConf] = useState<Record<string, number>>({});
  const [name, setName] = useState("");
  const [module, setModule] = useState("Payroll");
  const [formats, setFormats] = useState<string[]>(["pdf"]);
  const [savedId, setSavedId] = useState<string | null>(null);
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [snack, setSnack] = useState<{ open: boolean; msg: string; sev: Sev }>({ open: false, msg: "", sev: "success" });

  const ok = (msg: string) => setSnack({ open: true, msg, sev: "success" });
  const fail = (e: unknown) =>
    setSnack({ open: true, sev: "error", msg: (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Something went wrong" });

  const activeStep = !spec ? 0 : savedId ? 2 : 1;
  const unmatched = useMemo(() => {
    if (!spec) return 0;
    let n = 0;
    for (const s of spec.sections) {
      n += s.lines.filter((l) => !l.ref).length;
      if (s.total && !s.total.ref) n += 1;
    }
    return n;
  }, [spec]);

  // Edit mode: load saved document, skip upload.
  useEffect(() => {
    if (!editingId) return;
    documentApi.get(editingId).then((d) => {
      if (d.document) setSpec(d.document);
      setName(d.name);
      setModule(d.category);
      setFormats(d.allowed_formats?.length ? d.allowed_formats : ["pdf"]);
    }).catch(fail);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editingId]);

  const onFile = async (file: File) => {
    setBusy(true);
    try {
      const d = await documentApi.ingest(file);
      setSpec(d.spec);
      setConf(Object.fromEntries(d.review.map((r) => [r.label, r.confidence])));
      if (!name) setName(d.spec.company_name ? `${d.spec.company_name} Document` : "Document");
    } catch (e) { fail(e); } finally { setBusy(false); }
  };

  // ---- spec editing helpers (arbitrary sections) ----
  const mutate = (fn: (s: DocumentSpec) => DocumentSpec) => setSpec((s) => (s ? fn(s) : s));
  const editLine = (si: number, li: number, ref: string | null) =>
    mutate((s) => ({ ...s, sections: s.sections.map((sec, i) => i !== si ? sec : { ...sec, lines: sec.lines.map((l, j) => j === li ? { ...l, ref } : l) }) }));
  const editTotal = (si: number, ref: string | null) =>
    mutate((s) => ({ ...s, sections: s.sections.map((sec, i) => i !== si || !sec.total ? sec : { ...sec, total: { ...sec.total, ref } }) }));
  const setTitle = (si: number, title: string) =>
    mutate((s) => ({ ...s, sections: s.sections.map((sec, i) => i === si ? { ...sec, title } : sec) }));
  const editIdentity = (i: number, ref: string | null) =>
    mutate((s) => ({ ...s, identity_fields: s.identity_fields.map((l, j) => j === i ? { ...l, ref } : l) }));
  const toggleDetail = (i: number, on: boolean) =>
    mutate((s) => ({ ...s, detail_blocks: s.detail_blocks.map((b, j) => j === i ? { ...b, enabled: on } : b) }));
  const patch = (p: Partial<DocumentSpec>) => mutate((s) => ({ ...s, ...p }));

  const save = async (publish: boolean) => {
    if (!spec) return;
    setBusy(true);
    try {
      const body = {
        name: name || "Document", doc_type: "report" as const, category: module,
        document: spec, publish, allowed_formats: formats,
      };
      const res = editingId ? await documentApi.update(editingId, body) : await documentApi.create(body);
      setSavedId(res.template_id);
      ok(publish ? `✓ Published “${name}” — ready to generate.` : `✓ Saved draft (v${res.version_no}).`);
    } catch (e) { fail(e); } finally { setBusy(false); }
  };

  const generate = async () => {
    if (!savedId) return;
    setBusy(true);
    try { await documentApi.render(savedId, { year, month }); ok("✓ Document PDF downloaded."); }
    catch (e) { fail(e); } finally { setBusy(false); }
  };

  return (
    <Box sx={{ maxWidth: 1280, mx: "auto" }}>
      <Typography variant="h4">{editingId ? "Edit Document" : "Create a Document"}</Typography>
      <Typography variant="body2" sx={{ mb: 2 }}>
        {editingId
          ? "Adjust the section mappings, formats and details, then save a new version."
          : "Upload your one-page-per-record layout (payslip, statement, certificate…). We read its sections and match each line to a field; you review, then generate a PDF with one page per record."}
      </Typography>

      <Stepper activeStep={activeStep} sx={{ mb: 3 }}>
        {STEPS.map((s) => <Step key={s}><StepLabel>{s}</StepLabel></Step>)}
      </Stepper>

      {!spec && (
        <Card sx={{ maxWidth: 760 }}><CardContent>
          <Paper variant="outlined" sx={{ p: 4, borderRadius: 2, borderStyle: "dashed", textAlign: "center", bgcolor: "#FAFBFC" }}>
            {busy ? (
              <><CircularProgress size={32} /><Typography sx={{ fontWeight: 600, mt: 1.5 }}>Reading your layout…</Typography>
                <Typography variant="body2">Detecting sections and matching lines to fields.</Typography></>
            ) : (
              <><CloudUpload sx={{ fontSize: 40, color: "#007499" }} />
                <Typography sx={{ fontWeight: 600, mt: 1 }}>Upload your document layout</Typography>
                <Typography variant="body2" sx={{ mb: 1.5 }}>An Excel with your sections and line labels. We read only the labels, never record data.</Typography>
                <Button component="label" variant="contained" startIcon={<CloudUpload />}>
                  Choose file
                  <input hidden type="file" accept=".xlsx,.xls" onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])} />
                </Button></>
            )}
          </Paper>
        </CardContent></Card>
      )}

      {spec && (
        <Box sx={{ display: "grid", gap: 2.5, alignItems: "start", gridTemplateColumns: { xs: "1fr", lg: "minmax(0, 1fr) minmax(320px, 360px)" } }}>
        {/* LEFT — the form */}
        <Stack spacing={2} sx={{ minWidth: 0 }}>
          <Alert severity="success" icon={<Lock fontSize="inherit" />}>
            Only your section/line labels were read, record values never left the file.
            {unmatched > 0 && <b> {unmatched} line{unmatched === 1 ? "" : "s"} need a field below.</b>}
          </Alert>

          <Card><CardContent>
            <Typography variant="h6" sx={{ mb: 1.5 }}>Header</Typography>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
              <TextField size="small" label="Company / title" value={spec.company_name ?? ""}
                onChange={(e) => patch({ company_name: e.target.value })} sx={{ flex: 1 }} />
              <TextField size="small" label="Value column caption" value={spec.value_label}
                onChange={(e) => patch({ value_label: e.target.value })} sx={{ minWidth: 200 }} />
            </Stack>
            {spec.identity_fields.length > 0 && (
              <>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, mt: 2, mb: 1 }}>Identity fields</Typography>
                <Stack spacing={1}>
                  {spec.identity_fields.map((l, i) => (
                    <LineRow key={l.label} line={l} fields={fields} onChange={(ref) => editIdentity(i, ref)} />
                  ))}
                </Stack>
              </>
            )}
          </CardContent></Card>

          <Card><CardContent>
            <Typography variant="h6" sx={{ mb: 0.5 }}>Filters &amp; scope</Typography>
            <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1.5 }}>
              These become the filters in the Viewer when generating. Leave blank to skip a filter.
            </Typography>
            <Stack spacing={1.25}>
              <ScopeRow label="Period — Year" value={spec.period_year_ref} fields={fields}
                onChange={(ref) => patch({ period_year_ref: ref })} placeholder="No year filter" />
              <ScopeRow label="Period — Month" value={spec.period_month_ref} fields={fields}
                onChange={(ref) => patch({ period_month_ref: ref })} placeholder="No month filter" />
              <ScopeRow label="Single record (e.g. employee no)" value={spec.record_key_ref} fields={fields}
                onChange={(ref) => patch({ record_key_ref: ref })} placeholder="No single-record filter" />
            </Stack>
          </CardContent></Card>

          {spec.sections.map((sec, si) => (
            <Card key={si}><CardContent>
              <TextField size="small" variant="standard" placeholder="Section title (optional)"
                value={sec.title} onChange={(e) => setTitle(si, e.target.value)}
                sx={{ mb: 1.5, "& input": { fontWeight: 700, fontSize: "0.95rem" } }} />
              <Stack spacing={1}>
                {sec.lines.map((l, li) => (
                  <LineRow key={l.label} line={l} fields={fields} conf={conf[l.label]}
                    onChange={(ref) => editLine(si, li, ref)} />
                ))}
                {sec.total && (
                  <LineRow line={sec.total} fields={fields} total onChange={(ref) => editTotal(si, ref)} />
                )}
              </Stack>
            </CardContent></Card>
          ))}

          {(spec.detail_blocks.length > 0) && (
            <Card><CardContent>
              <Typography variant="h6" sx={{ mb: 1 }}>Detail blocks</Typography>
              {spec.detail_blocks.map((b, i) => (
                <FormControlLabel key={i}
                  control={<Switch checked={b.enabled} onChange={(e) => toggleDetail(i, e.target.checked)} />}
                  label={<Typography variant="body2">{b.title} <span style={{ color: "#9CA3AF" }}>· {b.provider}</span></Typography>} />
              ))}
            </CardContent></Card>
          )}

          <Card><CardContent>
            <TextField fullWidth size="small" label="Footer note" value={spec.footer}
              onChange={(e) => patch({ footer: e.target.value })} />
          </CardContent></Card>
        </Stack>

        {/* RIGHT — outline + save (sticky), mirrors the report builder's rail */}
        <Box sx={{ position: { lg: "sticky" }, top: { lg: 76 }, display: "flex", flexDirection: "column", gap: 2 }}>
          <Card><CardContent>
            <Typography variant="h6" sx={{ mb: 1 }}>Outline</Typography>
            <Stack spacing={0.75}>
              {spec.sections.map((sec, i) => {
                const tot = sec.lines.length + (sec.total ? 1 : 0);
                const mapped = sec.lines.filter((l) => l.ref).length + (sec.total?.ref ? 1 : 0);
                return (
                  <Stack key={i} direction="row" justifyContent="space-between" alignItems="center" spacing={1}>
                    <Typography variant="body2" noWrap sx={{ color: sec.title ? "text.primary" : "text.secondary" }}>
                      {sec.title || "Untitled section"}
                    </Typography>
                    <Chip size="small" color={tot > 0 && mapped === tot ? "primary" : "default"}
                      label={`${mapped}/${tot}`} sx={{ height: 20 }} />
                  </Stack>
                );
              })}
              {spec.detail_blocks.filter((b) => b.enabled).map((b, i) => (
                <Stack key={`d${i}`} direction="row" justifyContent="space-between" alignItems="center">
                  <Typography variant="body2" noWrap>{b.title}</Typography>
                  <Chip size="small" label="detail" sx={{ height: 20 }} />
                </Stack>
              ))}
            </Stack>
            {unmatched > 0 && (
              <Typography variant="caption" color="warning.main" sx={{ display: "block", mt: 1 }}>
                {unmatched} line{unmatched === 1 ? "" : "s"} still need a field.
              </Typography>
            )}
          </CardContent></Card>

          <Card><CardContent>
            <Typography variant="h6" sx={{ mb: 1.5 }}>Save &amp; generate</Typography>
            <Stack spacing={1.5} sx={{ mb: 2 }}>
              <TextField size="small" label="Document name" value={name} onChange={(e) => setName(e.target.value)} fullWidth />
              <TextField select size="small" label="Module" value={module} onChange={(e) => setModule(e.target.value)} fullWidth>
                {REPORT_MODULES.map((m) => <MenuItem key={m} value={m}>{m}</MenuItem>)}
              </TextField>
            </Stack>
            <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>
              Allowed downloads in the Viewer (documents export as PDF)
            </Typography>
            <Box sx={{ mb: 1.5 }}><OutputFormatsInline value={formats} onChange={setFormats} /></Box>

            <Stack direction="row" spacing={1.5} flexWrap="wrap" alignItems="center">
              <Button variant="outlined" startIcon={<Save />} disabled={busy} onClick={() => save(false)}>Save draft</Button>
              <Button variant="contained" startIcon={<Publish />} disabled={busy || !name.trim()} onClick={() => save(true)}>Save &amp; Publish</Button>
              {savedId && <Chip color="success" size="small" label="Published" />}
            </Stack>

            {savedId && (
              <>
                <Divider sx={{ my: 2 }} />
                <Typography variant="subtitle2" sx={{ mb: 1 }}>Generate for a period</Typography>
                <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap">
                  <TextField size="small" type="number" label="Year" value={year} onChange={(e) => setYear(Number(e.target.value))} sx={{ width: 100 }} />
                  <TextField select size="small" label="Month" value={month} onChange={(e) => setMonth(Number(e.target.value))} sx={{ width: 110 }}>
                    {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => <MenuItem key={m} value={m}>{m}</MenuItem>)}
                  </TextField>
                  <Button variant="contained" startIcon={<PictureAsPdf />} disabled={busy} onClick={generate}>PDF</Button>
                  <Button size="small" onClick={() => navigate("/documents")}>Done</Button>
                </Stack>
                <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1 }}>One page per record for the chosen period.</Typography>
              </>
            )}
          </CardContent></Card>
        </Box>
        </Box>
      )}

      <Snackbar open={snack.open} autoHideDuration={6000} onClose={() => setSnack((s) => ({ ...s, open: false }))}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}>
        <Alert severity={snack.sev} variant="filled" onClose={() => setSnack((s) => ({ ...s, open: false }))} sx={{ maxWidth: 560 }}>
          {snack.msg}
        </Alert>
      </Snackbar>
    </Box>
  );
}

function LineRow({
  line, fields, onChange, conf, total,
}: {
  line: DocumentLine;
  fields: SemanticFieldMeta[];
  onChange: (ref: string | null) => void;
  conf?: number;
  total?: boolean;
}) {
  return (
    <Stack direction="row" spacing={1} alignItems="center">
      <Typography sx={{ flex: 1, fontWeight: total ? 700 : 400, fontSize: "0.85rem" }}>{line.label}</Typography>
      {!line.ref && conf === undefined && <Chip size="small" label="no data" sx={{ height: 22 }} />}
      <FieldSelect fields={fields} value={line.ref} onChange={onChange}
        placeholder={total ? "Total field" : "Pick a field"} minWidth={280} />
    </Stack>
  );
}

function ScopeRow({
  label, value, fields, onChange, placeholder,
}: {
  label: string;
  value: string | null;
  fields: SemanticFieldMeta[];
  onChange: (ref: string | null) => void;
  placeholder?: string;
}) {
  return (
    <Stack direction="row" spacing={1} alignItems="center">
      <Typography variant="body2" sx={{ flex: 1 }}>{label}</Typography>
      <FieldSelect fields={fields} value={value} onChange={onChange} placeholder={placeholder} minWidth={280} optional />
    </Stack>
  );
}

// Inline output-format selector (View/Excel/PDF).
function OutputFormatsInline({ value, onChange }: { value: string[]; onChange: (v: string[]) => void }) {
  const ALL = [{ v: "view", label: "View (table)" }, { v: "excel", label: "Excel" }, { v: "pdf", label: "PDF" }];
  const toggle = (v: string) => onChange(value.includes(v) ? value.filter((x) => x !== v) : [...value, v]);
  return (
    <Stack direction="row" spacing={0.5} flexWrap="wrap">
      {ALL.map((o) => (
        <FormControlLabel key={o.v}
          control={<Switch size="small" checked={value.includes(o.v)} onChange={() => toggle(o.v)} />}
          label={<Typography variant="body2">{o.label}</Typography>} />
      ))}
    </Stack>
  );
}
