// Guided, Excel-first Report Builder for non-technical HR/admin users.
// Step 1 add columns (Upload Excel · Describe with AI · Advanced field picker)
// -> Step 2 filter & preview -> Step 3 publish. The 140-field list is hidden
// behind the "Pick fields" tab so the page isn't overwhelming on load.
import { useLocation, useParams } from "react-router-dom";
import { useEffect, useRef, useState } from "react";
import {
  Alert, Box, Button, Card, CardContent, Dialog, DialogActions, DialogContent, DialogTitle,
  Divider, MenuItem, Snackbar, Stack, Step, StepLabel, Stepper, Tab, Tabs, TextField, Typography,
} from "@mui/material";
import { Save, Publish, UploadFile, ChatBubbleOutline, Tune } from "@mui/icons-material";
import { templateApi } from "../../api/client";
import { useBuilderStore, REPORT_MODULES } from "../../store/builderStore";
import { FieldSelector } from "./FieldSelector";
import { SelectedColumns } from "./SelectedColumns";
import { SummaryModePanel } from "./SummaryModePanel";
import { FilterPanel } from "./FilterPanel";
import { SortPanel } from "./SortPanel";
import { PresentationPanel } from "./PresentationPanel";
import { ChatAssistant } from "./ChatAssistant";
import { ExcelUpload } from "./ExcelUpload";
import { PreviewPane } from "./PreviewPane";
import { OutputFormats } from "../../components/OutputFormats";
import type { DataSpec, PresentationSpec } from "../../types/spec";

const STEPS = ["Add columns", "Filter & preview", "Publish"];
const PLACEHOLDER_TITLE = "Untitled Report";

// One canonical serialization of the savable state, used by autosave, manual
// save, and load so equality checks never drift apart.
const snapOf = (s: { dataSpec: DataSpec; presentation: PresentationSpec; module: string; description: string }) =>
  JSON.stringify(s);

// Template `name` and presentation `title` can drift (autosave creates "Untitled
// Report" while the builder field stays blank). Prefer whichever the user set.
const mergeLoadedPresentation = (name: string, ps: PresentationSpec): PresentationSpec => {
  const title = (ps.title ?? "").trim();
  const savedName = name.trim();
  if (title && title !== PLACEHOLDER_TITLE) return { ...ps, title };
  if (savedName && savedName !== PLACEHOLDER_TITLE) return { ...ps, title: savedName };
  return { ...ps, title: title || savedName };
};

export function BuilderPage() {
  const { templateId } = useParams();
  const location = useLocation();
  // A report handed off from the chat's "Add filters in Builder" — keep the spec
  // already in the store instead of resetting, and open on the Filter step.
  const keepSpec = (location.state as { keepSpec?: boolean } | null)?.keepSpec === true;
  const {
    dataSpec, presentation, setTemplateId, updatePresentation, module, setModule,
    setDataSpec, setPresentation, reset, description, setDescription,
  } = useBuilderStore();

  // Autosave bookkeeping: the snapshot we last persisted, a promise chain that
  // serializes saves (so a brand-new template is created exactly once), and the
  // status shown to the user.
  const savedSnap = useRef("");
  const saveChain = useRef<Promise<void>>(Promise.resolve());
  // The source file already persisted, so we upload each distinct sheet at most
  // once (not on every autosave).
  const uploadedFile = useRef<File | null>(null);
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">("idle");

  // Load an existing report into the builder when editing (/builder/:id), or
  // start clean for a new one (/builder). Without this, editing showed an empty
  // builder and saving would overwrite the report with nothing.
  useEffect(() => {
    if (!templateId) {
      if (!keepSpec) reset();  // preserve a chat-handoff spec; else start clean
      savedSnap.current = ""; setSaveState("idle"); return;
    }
    setTemplateId(templateId);
    templateApi.getDraft(templateId)
      .then((d) => {
        const loadedPresentation = mergeLoadedPresentation(d.name, d.presentation_spec);
        setDataSpec(d.data_spec);
        setPresentation(loadedPresentation);
        setModule(d.module ?? "General");
        setDescription(d.description ?? "");
        // Seed the saved snapshot so loading doesn't immediately autosave.
        savedSnap.current = snapOf({
          dataSpec: d.data_spec, presentation: loadedPresentation,
          module: d.module ?? "General", description: d.description ?? "",
        });
        setSaveState("saved");
      })
      .catch(() => { /* no saved version yet — leave the builder as-is */ });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [templateId]);
  const [tab, setTab] = useState(keepSpec ? 1 : 0);  // land on Filter & preview from chat
  const [pubOpen, setPubOpen] = useState(false);
  const [published, setPublished] = useState(false);
  const [snack, setSnack] = useState<{ open: boolean; msg: string; sev: "success" | "error" }>({ open: false, msg: "", sev: "success" });
  const ok = (msg: string) => setSnack({ open: true, msg, sev: "success" });
  const fail = (e: unknown) =>
    setSnack({ open: true, sev: "error", msg: (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Save failed" });
  const hasColumns = dataSpec.fields.length > 0 || dataSpec.aggregations.length > 0;
  const activeStep = !hasColumns ? 0 : published ? 2 : 1;

  const ensureDraft = async () => {
    // Read the id fresh from the store (not a render-time closure) so a save
    // queued before the create resolves still sees the new template id.
    let tid = useBuilderStore.getState().templateId ?? templateId ?? null;
    const title = presentation.title.trim();
    if (!tid) {
      const tpl = await templateApi.create(title || PLACEHOLDER_TITLE, module, description);
      tid = tpl.id;
      setTemplateId(tid!);
    } else {
      // Keep template metadata in sync with what the user typed in the builder.
      await templateApi.rename(tid, {
        name: title || undefined,
        module,
        description,
      });
    }
    const version = await templateApi.saveDraft(tid!, dataSpec, presentation);
    // Persist the uploaded sheet (encrypted server-side) so it can be previewed on
    // edit. Fire-and-forget, once per distinct file; a failure just retries next save.
    const sf = useBuilderStore.getState().sourceFile;
    if (sf && uploadedFile.current !== sf) {
      uploadedFile.current = sf;
      templateApi.uploadSourceFile(tid!, sf).catch(() => { uploadedFile.current = null; });
    }
    return { tid: tid!, version };
  };
  const saveDraft = async () => {
    try {
      setSaveState("saving");
      const { version } = await ensureDraft();
      savedSnap.current = snapOf({ dataSpec, presentation, module, description });
      setSaveState("saved");
      ok(`✓ Draft saved (v${version.version_no}).`);
    } catch (e) { setSaveState("error"); fail(e); }
  };

  // Real autosave: ~1.2s after the user stops editing, persist the draft when
  // there are columns to save. Serialized through saveChain so a brand-new
  // template is only ever created once. This is what makes the "saves
  // automatically" promise below true.
  useEffect(() => {
    if (!hasColumns) return;
    const snap = snapOf({ dataSpec, presentation, module, description });
    if (snap === savedSnap.current) return;
    const t = setTimeout(() => {
      saveChain.current = saveChain.current.then(async () => {
        if (snapOf({ dataSpec, presentation, module, description }) === savedSnap.current) return;
        setSaveState("saving");
        try { await ensureDraft(); savedSnap.current = snap; setSaveState("saved"); }
        catch { setSaveState("error"); }
      });
    }, 1200);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataSpec, presentation, module, description, hasColumns]);
  // Always confirm name + module before publishing, so nothing lands as
  // "Untitled Report / General" in the Viewer.
  const openPublish = () => setPubOpen(true);
  const confirmPublish = async () => {
    const title = presentation.title;
    setPubOpen(false);
    try {
      const { tid, version } = await ensureDraft();
      await templateApi.publish(tid, version.version_id);
      savedSnap.current = snapOf({ dataSpec, presentation, module, description });
      setSaveState("saved");
      setPublished(true);
      ok(`✓ Published “${title}” to ${module} — now in the Viewer.`);
    } catch (e) { fail(e); }
  };

  const reportMetaFields = (
    <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
      <TextField
        size="small"
        label="Report name"
        required
        value={presentation.title ?? ""}
        onChange={(e) => updatePresentation({ title: e.target.value })}
        placeholder="e.g. Active Employees by Department"
        helperText="Shown in Templates and the Viewer"
        sx={{ flex: 1, minWidth: 0 }}
      />
      <TextField
        select
        size="small"
        label="Module"
        value={module}
        onChange={(e) => setModule(e.target.value)}
        sx={{ minWidth: 170 }}
      >
        {REPORT_MODULES.map((m) => <MenuItem key={m} value={m}>{m}</MenuItem>)}
      </TextField>
    </Stack>
  );

  return (
    <Box sx={{ maxWidth: 1280, mx: "auto" }}>
      <Typography variant="h4">{templateId ? "Edit report" : "Create a report"}</Typography>
      <Typography variant="body2" sx={{ mb: 2 }}>
        Start from a sample Excel, describe it in words, or pick fields — no SQL needed.
      </Typography>

      <Box sx={{ mb: 2.5 }}>
        {reportMetaFields}
      </Box>

      <Stepper activeStep={activeStep} sx={{ mb: 3 }}>
        {STEPS.map((s) => <Step key={s}><StepLabel>{s}</StepLabel></Step>)}
      </Stepper>

      {/* Two-column working layout: build on the left, the report itself stays
          in view on the right (sticky, auto-refreshing) so it's always the
          subject. Stacks to one column below lg. */}
      <Box
        sx={{
          display: "grid", gap: 2.5, alignItems: "start",
          gridTemplateColumns: { xs: "1fr", lg: "minmax(0, 1fr) minmax(360px, 420px)" },
        }}
      >
        {/* LEFT — inputs & configuration */}
        <Stack spacing={2} sx={{ minWidth: 0 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 1.5 }}>1. Add the columns you want</Typography>
              <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2, minHeight: 40 }}>
                <Tab icon={<UploadFile fontSize="small" />} iconPosition="start" label="Upload sample" sx={{ minHeight: 40, textTransform: "none" }} />
                <Tab icon={<ChatBubbleOutline fontSize="small" />} iconPosition="start" label="Describe with AI" sx={{ minHeight: 40, textTransform: "none" }} />
                <Tab icon={<Tune fontSize="small" />} iconPosition="start" label="Pick fields" sx={{ minHeight: 40, textTransform: "none" }} />
              </Tabs>
              {tab === 0 && <ExcelUpload />}
              {tab === 1 && <Box sx={{ height: 320 }}><ChatAssistant /></Box>}
              {tab === 2 && <FieldSelector />}
            </CardContent>
          </Card>

          {hasColumns && (
            <Card>
              <CardContent>
                <Typography variant="h6" sx={{ mb: 0.25 }}>2. Shape &amp; format</Typography>
                <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 2.5 }}>
                  Order columns, summarise, filter, and set how the export looks.
                </Typography>
                {/* One panel with dividers, not four identical cards. */}
                <Stack spacing={3} divider={<Divider flexItem />}>
                  <SelectedColumns />
                  <SummaryModePanel />
                  <FilterPanel />
                  <SortPanel />
                  <PresentationPanel />
                </Stack>
              </CardContent>
            </Card>
          )}
        </Stack>

        {/* RIGHT — the report (the subject), pinned in view on desktop */}
        <Box
          sx={{
            position: { lg: "sticky" }, top: { lg: 76 }, alignSelf: "start",
            display: "flex", flexDirection: "column", gap: 2,
          }}
        >
          <Card>
            <CardContent>
              <PreviewPane auto />
            </CardContent>
          </Card>

          {hasColumns && (
            <Card>
              <CardContent>
                <Typography variant="h6" sx={{ mb: 1 }}>3. Save &amp; publish</Typography>
                <Box sx={{ mb: 2 }}>{reportMetaFields}</Box>
                <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>
                  Allowed downloads in the Viewer
                </Typography>
                <Box sx={{ mb: 1 }}>
                  <OutputFormats
                    value={presentation.allowed_formats ?? ["view", "excel", "pdf"]}
                    onChange={(v) => updatePresentation({ allowed_formats: v })}
                  />
                </Box>
                <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap">
                  <Button variant="outlined" startIcon={<Save />} onClick={saveDraft}>Save draft</Button>
                  <Button variant="contained" startIcon={<Publish />} onClick={openPublish}>Save &amp; Publish</Button>
                </Stack>
                <Typography variant="caption" sx={{ display: "block", mt: 1, color: saveState === "error" ? "error.main" : "text.secondary" }}>
                  {saveState === "saving" ? "Saving…"
                    : saveState === "saved" ? "✓ All changes saved as a draft."
                    : saveState === "error" ? "Couldn’t autosave — click Save draft to retry."
                    : "Changes save automatically as a draft; an immutable version is snapshotted only on publish (SRS §7)."}
                </Typography>
              </CardContent>
            </Card>
          )}
        </Box>
      </Box>

      <Dialog open={pubOpen} onClose={() => setPubOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle>Publish report</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField autoFocus size="small" label="Report name" value={presentation.title}
              onChange={(e) => updatePresentation({ title: e.target.value })}
              placeholder="e.g. Monthly Paysheet" />
            <TextField select size="small" label="Module (where it shows in the Viewer)" value={module}
              onChange={(e) => setModule(e.target.value)}>
              {REPORT_MODULES.map((m) => <MenuItem key={m} value={m}>{m}</MenuItem>)}
            </TextField>
            <TextField size="small" label="Description (optional)" value={description}
              onChange={(e) => setDescription(e.target.value)} multiline minRows={2}
              placeholder="A short summary of what this report shows" />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPubOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={confirmPublish}
            disabled={!presentation.title.trim()}>Publish</Button>
        </DialogActions>
      </Dialog>

      <Snackbar open={snack.open} autoHideDuration={6000} onClose={() => setSnack((s) => ({ ...s, open: false }))}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}>
        <Alert severity={snack.sev} variant="filled" onClose={() => setSnack((s) => ({ ...s, open: false }))} sx={{ maxWidth: 560 }}>
          {snack.msg}
        </Alert>
      </Snackbar>
    </Box>
  );
}
