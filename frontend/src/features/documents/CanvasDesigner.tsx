// Canvas designer for LETTERS and EMAIL templates. Drag blocks onto an A4 canvas
// (rich text, bound fields, logo, table, divider, spacer, signature), style them,
// bind data via {{merge}} tokens, then preview against real records and generate.
// Report-docs use the upload-based DocumentBuilder instead.
import { useEffect, useMemo, useRef, useState } from "react";
import type { Editor } from "@tiptap/react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  DndContext, closestCenter, PointerSensor, useSensor, useSensors, useDroppable,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext, useSortable, verticalListSortingStrategy, arrayMove,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import {
  Alert, Autocomplete, Box, Button, Card, CardContent, Chip, CircularProgress, Dialog, DialogActions,
  DialogContent, DialogTitle, Divider, FormControlLabel, IconButton, LinearProgress, Menu, MenuItem,
  Popover, Snackbar, Stack, Switch, TextField, Tooltip, Typography, ToggleButton, ToggleButtonGroup,
} from "@mui/material";
import {
  TextFields, DataObjectOutlined, ImageOutlined, TableChartOutlined, Remove, SpaceBar,
  DrawOutlined, DragIndicator, DeleteOutline, Save, Publish, VisibilityOutlined, PictureAsPdf,
  CloudUpload, FormatAlignLeft, FormatAlignCenter, FormatAlignRight, Add, AutoAwesome,
  DescriptionOutlined, FileDownloadOutlined, InfoOutlined,
} from "@mui/icons-material";
import { documentApi, semanticApi, type DocSaveBody } from "../../api/client";
import type {
  BlockType, DesignBlock, DocType, DocumentDesign, ManualFieldPoolItem,
} from "../../types/document";
import { emptyDesign } from "../../types/document";
import { sanitizeDesignHtml, wordMarksKey } from "./letterHtml";
import type { SemanticFieldMeta } from "../../types/spec";
import { RichTextBlock } from "./blocks/RichTextBlock";
import { FieldSelect } from "./FieldSelect";
import { ValueMapPopover } from "./ValueMapPopover";
import { DocumentPreviewInline } from "./DocumentPreviewInline";
import { LetterheadPanel } from "./LetterheadPanel";

const now = new Date();
type Sev = "success" | "error";

// Built-in fields resolved at generation time (e.g. today's date on a letter).
const sysField = (ref: string, label: string): SemanticFieldMeta => ({
  ref, label, type: "date", role: "dimension", entity: "System", allowed_aggregations: [],
});
const SYSTEM_FIELDS: SemanticFieldMeta[] = [
  sysField("system.date", "Today’s date"),
  sysField("system.date_iso", "Today’s date (ISO)"),
  sysField("system.year", "Current year"),
  sysField("system.month", "Current month"),
];
const uid = () => (crypto?.randomUUID?.() ?? `b${Date.now()}${Math.round(Math.random() * 1e6)}`);

const PALETTE: { type: BlockType; label: string; icon: React.ReactNode }[] = [
  { type: "text", label: "Text", icon: <TextFields fontSize="small" /> },
  { type: "field", label: "Field", icon: <DataObjectOutlined fontSize="small" /> },
  { type: "image", label: "Image", icon: <ImageOutlined fontSize="small" /> },
  { type: "table", label: "Table", icon: <TableChartOutlined fontSize="small" /> },
  { type: "divider", label: "Divider", icon: <Remove fontSize="small" /> },
  { type: "spacer", label: "Spacer", icon: <SpaceBar fontSize="small" /> },
  { type: "signature", label: "Signature", icon: <DrawOutlined fontSize="small" /> },
];

function newBlock(type: BlockType): DesignBlock {
  const base: DesignBlock = { id: uid(), type, style: {} };
  if (type === "text") return { ...base, html: "<p>Type here… use Insert field for {{data}}.</p>" };
  if (type === "field") return { ...base, ref: null, label: "" };
  if (type === "signature") return { ...base, label: "Authorised Signatory" };
  if (type === "spacer") return { ...base, height_px: 24 };
  if (type === "image") return { ...base, width_pct: 30 };
  if (type === "table") return { ...base, columns: [] };
  return base;
}

export function CanvasDesigner() {
  const navigate = useNavigate();
  const { id: editingId } = useParams();
  const [params] = useSearchParams();
  const initialType = (params.get("type") as DocType) || "letter";
  const initialCat = params.get("category") || "";

  const { data: fields = [] } = useQuery({ queryKey: ["fields", "builder"], queryFn: semanticApi.fieldsForBuilder });
  const { data: categories = [] } = useQuery({
    queryKey: ["doc-categories", initialType],
    queryFn: () => documentApi.categories(initialType),
  });

  const [docType, setDocType] = useState<DocType>(initialType);
  const [design, setDesign] = useState<DocumentDesign>(emptyDesign());
  const [name, setName] = useState("");
  const [category, setCategory] = useState(initialCat);
  const [subject, setSubject] = useState("");
  const [sel, setSel] = useState<string | null>(null);
  const [savedId, setSavedId] = useState<string | null>(editingId ?? null);
  const [busy, setBusy] = useState(false);
  const [extracting, setExtracting] = useState(false);  // sample upload (deterministic, instant)
  const [enhancing, setEnhancing] = useState(false);    // opt-in AI enhance (slower)
  const [quickFields, setQuickFields] = useState<{ ref: string; label: string }[]>([]);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [snack, setSnack] = useState<{ open: boolean; msg: string; sev: Sev }>({ open: false, msg: "", sev: "success" });
  const [recordKeyError, setRecordKeyError] = useState(false);
  const scopeRef = useRef<HTMLDivElement>(null);
  const ok = (msg: string) => setSnack({ open: true, msg, sev: "success" });
  const fail = (e: unknown) => {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Something went wrong";
    setSnack({ open: true, sev: "error", msg });
    return msg;
  };
  // Inspector stays page XOR block; on the publish gate we switch back to the
  // page card so the control that satisfies record_key_ref is actually on screen.
  const revealPageScope = () => {
    setSel(null);
    window.setTimeout(() => {
      scopeRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 50);
  };

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));
  const wordPass = useRef("");
  const recordKeyDefaulted = useRef(false);
  const [editorEpoch, setEditorEpoch] = useState(0);

  // New letter only: pre-select the catalogue's record-identity field (whatever
  // ref this tenant assigned — often labelled Employee Number). Editable after.
  useEffect(() => {
    if (editingId || recordKeyDefaulted.current || design.record_key_ref) return;
    const identity = (fields as SemanticFieldMeta[]).find((f) => f.is_record_key);
    if (!identity) return;
    recordKeyDefaulted.current = true;
    setDesign((d) => (d.record_key_ref ? d : { ...d, record_key_ref: identity.ref }));
  }, [editingId, fields, design.record_key_ref]);

  // Same method as Display_Name: every leftover Word «Field» is scored by the
  // catalogue matcher (labels + glossary). Runs once per distinct set of marks.
  useEffect(() => {
    const blobs = [design.header_html, design.footer_html, ...design.blocks.map((b) => b.html)];
    // Sort across ALL blobs, not just within each — otherwise reordering blocks
    // (or editing an unrelated one) changes this key even though the actual set
    // of marks is unchanged, triggering a spurious re-fetch + editor remount.
    const marks = blobs.map((h) => wordMarksKey(h)).filter(Boolean).join("|").split("|").sort().join("|");
    if (!marks || marks === wordPass.current) return;
    wordPass.current = marks;
    documentApi.mapWordFields(design).then((res) => {
      setDesign(sanitizeDesignHtml(res.design));
      setEditorEpoch((n) => n + 1);
      const n = res.review.length;
      const left = res.unmatched.length;
      if (n) ok(`Mapped ${n} Word field${n === 1 ? "" : "s"} from your catalogue${left ? ` — ${left} still need Make dynamic` : ""}.`);
      else if (left) ok(`${left} Word field${left === 1 ? "" : "s"} didn’t match a catalogue field — select one and click Make dynamic.`);
    }).catch((e) => { wordPass.current = ""; fail(e); });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [design]);

  // Edit mode: load the saved design.
  useEffect(() => {
    if (!editingId) return;
    documentApi.get(editingId).then((d) => {
      setDocType(d.doc_type);
      if (d.design) setDesign(sanitizeDesignHtml(d.design));
      setName(d.name);
      setCategory(d.category);
      setSubject(d.email_subject || "");
    }).catch(fail);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editingId]);

  // New letter/email: seed one empty text block so the Word toolbar is available
  // immediately — the user can just start typing or paste content (Word/PDF, and any
  // script incl. Tamil/Sinhala). No upload required to get formatting tools.
  useEffect(() => {
    if (editingId) return;
    setDesign((d) => (d.blocks.length === 0
      ? { ...d, blocks: [{ ...newBlock("text"), html: "<p></p>" }] }
      : d));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editingId]);

  const selected = design.blocks.find((b) => b.id === sel) ?? null;

  const addBlock = (type: BlockType) => {
    const b = newBlock(type);
    setDesign((d) => ({ ...d, blocks: [...d.blocks, b] }));
    setSel(b.id);
  };

  // Live TipTap editors by block id, so the top "Field" inserts into the text you're
  // editing instead of making a separate block.
  const editors = useRef<Record<string, Editor | null>>({});
  const [activeText, setActiveText] = useState<string | null>(null);
  const [fieldAnchor, setFieldAnchor] = useState<HTMLElement | null>(null);
  const [addAnchor, setAddAnchor] = useState<HTMLElement | null>(null);  // "Add block" menu
  const [mapField, setMapField] = useState<SemanticFieldMeta | null>(null);
  const targetEditor = (): Editor | null => {
    if (activeText && editors.current[activeText]) return editors.current[activeText];
    const lastText = [...design.blocks].reverse().find((b) => b.type === "text");
    return lastText ? editors.current[lastText.id] ?? null : null;
  };
  const onAddField = (el: HTMLElement) => {
    if (targetEditor()) setFieldAnchor(el);   // insert into the active text editor
    else addBlock("field");                    // no text yet -> a standalone field block
  };
  const insertTokenInner = (tokenInner: string) => {
    targetEditor()?.chain().focus().insertContent(`{{${tokenInner}}}`).run();
    setFieldAnchor(null);
  };
  const insertFieldToken = (ref: string) => insertTokenInner(ref);
  const onFieldPicked = (f: SemanticFieldMeta) => {
    if (f.sample_values?.length) {
      setMapField(f);  // hold the field picker open behind the mapping popover
    } else {
      insertFieldToken(f.ref);
    }
  };
  const addFieldBlock = (ref: string, label: string) => {
    const b: DesignBlock = { ...newBlock("field"), ref, label };
    setDesign((d) => ({ ...d, blocks: [...d.blocks, b] }));
    setSel(b.id);
  };
  const updateBlock = (id: string, patch: Partial<DesignBlock>) =>
    setDesign((d) => ({ ...d, blocks: d.blocks.map((b) => (b.id === id ? { ...b, ...patch } : b)) }));
  const updateStyle = (id: string, patch: Record<string, string | number>) =>
    setDesign((d) => ({ ...d, blocks: d.blocks.map((b) => (b.id === id ? { ...b, style: { ...b.style, ...patch } } : b)) }));
  const removeBlock = (id: string) => {
    setDesign((d) => ({ ...d, blocks: d.blocks.filter((b) => b.id !== id) }));
    if (sel === id) setSel(null);
  };
  const onDragEnd = (e: DragEndEvent) => {
    const { active, over } = e;
    if (!over) return;
    const activeId = String(active.id);
    // Dragged a palette icon onto the canvas -> insert a new block at that spot.
    if (activeId.startsWith("palette-")) {
      const type = activeId.slice("palette-".length) as BlockType;
      const overId = String(over.id);
      const b = newBlock(type);
      setDesign((d) => {
        const idx = overId === "APPEND" ? d.blocks.length : d.blocks.findIndex((x) => x.id === overId);
        const at = idx === -1 ? d.blocks.length : idx;
        const blocks = [...d.blocks];
        blocks.splice(at, 0, b);
        return { ...d, blocks };
      });
      setSel(b.id);
      return;
    }
    // Reordered an existing block.
    if (activeId === String(over.id)) return;
    setDesign((d) => {
      const from = d.blocks.findIndex((x) => x.id === activeId);
      const to = d.blocks.findIndex((x) => x.id === String(over.id));
      if (from === -1 || to === -1) return d;
      return { ...d, blocks: arrayMove(d.blocks, from, to) };
    });
  };

  const patchDesign = (p: Partial<DocumentDesign>) => setDesign((d) => ({ ...d, ...p }));

  // Manual (issuance-time) fields — insertable in the picker as manual.<key> tokens.
  // Manual fields = the explicit list UNION any {{manual.*}} tokens already in the
  // letter — so they survive even if the saved list is lost (the tokens persist in
  // the block HTML). Label comes from the explicit list, else Title-Cased from the key.
  const manualFields = useMemo(() => {
    const explicit = new Map((design.manual_fields ?? []).map((m) => [m.key, m.label]));
    const keys = new Set<string>(explicit.keys());
    const scan = (html?: string | null) => {
      for (const m of (html ?? "").matchAll(/\{\{\s*manual\.([a-z0-9_]+)\s*\}\}/gi)) keys.add(m[1]);
    };
    design.blocks.forEach((b) => scan(b.html));
    scan(design.header_html); scan(design.footer_html);
    const titleCase = (k: string) => k.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
    return [...keys].map((k) => ({ key: k, label: explicit.get(k) ?? titleCase(k) }));
  }, [design]);
  const pickerFields = useMemo((): SemanticFieldMeta[] => {
    const extra: SemanticFieldMeta[] = manualFields.map((m) => ({
      ref: `manual.${m.key}`, label: `${m.label} (manual)`, type: "string" as const,
      role: "dimension" as const, entity: "Manual input", allowed_aggregations: [] as never[],
    }));
    return [...SYSTEM_FIELDS, ...(fields as SemanticFieldMeta[]), ...extra];
  }, [fields, manualFields]);
  const [manualDraft, setManualDraft] = useState("");
  // Tenant-scoped reusable pool — shared across every letter, never across tenants.
  const [pool, setPool] = useState<ManualFieldPoolItem[]>([]);
  useEffect(() => { documentApi.manualFields().then(setPool).catch(() => {}); }, []);
  const slugKey = (label: string) =>
    label.trim().toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");

  // Apply a field to THIS letter (adds it to the letter's manual fields → shows as a chip).
  const applyToLetter = (m: { key: string; label: string }) => {
    if (!m.key || manualFields.some((f) => f.key === m.key)) return;
    patchDesign({ manual_fields: [...manualFields, { key: m.key, label: m.label }] });
  };
  // Add a NEW field: save it to the tenant pool (only if not already there) and apply it.
  const addManualField = async (label: string) => {
    const key = slugKey(label);
    if (!key) return;
    setManualDraft("");
    applyToLetter({ key, label: label.trim() });
    try {
      const saved = await documentApi.createManualField(label.trim());
      setPool((p) => (p.some((x) => x.key === saved.key) ? p : [...p, saved].sort((a, b) => a.label.localeCompare(b.label))));
    } catch { /* pool save is best-effort; the field still works on this letter */ }
  };
  const removeManualField = (key: string) =>
    patchDesign({ manual_fields: manualFields.filter((m) => m.key !== key) });
  // Remove from the tenant pool entirely (does not touch letters already using it).
  const deletePoolField = async (item: ManualFieldPoolItem) => {
    setPool((p) => p.filter((x) => x.id !== item.id));
    try { await documentApi.deleteManualField(item.id); } catch { /* ignore */ }
  };
  const poolToAdd = useMemo(
    () => pool.filter((m) => !manualFields.some((f) => f.key === m.key)),
    [pool, manualFields],
  );

  // Start from a sample: upload a letter (Word/PDF/image/Excel), extract it into a
  // design with data lines auto-mapped to {{tokens}} for review.
  const onSample = async (file: File) => {
    if (design.blocks.length > 0 && !window.confirm("Replace the current design with the uploaded sample?")) return;
    setBusy(true); setExtracting(true);
    try {
      const res = await documentApi.designFromSample(file);
      setDesign((d) => ({ ...d, blocks: res.design.blocks }));
      setSel(res.design.blocks[0]?.id ?? null);
      setQuickFields(res.unmatched.map((u) => ({ ref: "", label: u })));
      const mapped = res.review.length;
      ok(`Built from “${file.name}” — ${mapped} field${mapped === 1 ? "" : "s"} auto-mapped${res.unmatched.length ? `, ${res.unmatched.length} to review` : ""}.`);
    } catch (e) { fail(e); } finally { setBusy(false); setExtracting(false); }
  };

  // Opt-in AI enhance — map the dynamic values the fast pass left behind (slower).
  const onEnhance = async () => {
    setBusy(true); setEnhancing(true);
    try {
      const res = await documentApi.aiEnhance(design);
      setDesign((d) => ({ ...d, blocks: res.design.blocks }));
      setQuickFields(res.unmatched.map((u) => ({ ref: "", label: u })));
      const mapped = res.review.length;
      ok(mapped ? `AI mapped ${mapped} more field${mapped === 1 ? "" : "s"}.` : "No extra fields found to map.");
    } catch (e) { fail(e); } finally { setBusy(false); setEnhancing(false); }
  };

  const body = (publish: boolean): DocSaveBody => ({
    name: name || (docType === "email" ? "Email template" : "Letter"),
    doc_type: docType, category: category || "General",
    design, subject: docType === "email" ? subject : undefined,
    publish, allowed_formats: docType === "email" ? ["email"] : ["pdf"],
  });
  const save = async (publish: boolean): Promise<string | null> => {
    setBusy(true);
    try {
      const res = savedId
        ? await documentApi.update(savedId, body(publish))
        : await documentApi.create(body(publish));
      setSavedId(res.template_id);
      ok(publish ? `✓ Published “${name}”.` : `✓ Draft saved (v${res.version_no}).`);
      return res.template_id;
    } catch (e) {
      const msg = fail(e);
      if (typeof msg === "string" && msg.includes("One per record")) {
        setRecordKeyError(true);
        revealPageScope();
      }
      return null;
    } finally { setBusy(false); }
  };
  const doPreview = async () => {
    const id = savedId ?? (await save(false));
    if (id) setPreviewOpen(true);
  };
  const [manualOpen, setManualOpen] = useState(false);
  const [manualVals, setManualVals] = useState<Record<string, string>>({});
  const [genRecord, setGenRecord] = useState("");
  const [genYear, setGenYear] = useState(now.getFullYear());
  const [genMonth, setGenMonth] = useState(now.getMonth() + 1);
  const needsPeriod = Boolean(design.period_year_ref && design.period_month_ref);
  const needsRecord = Boolean(design.record_key_ref);
  const generate = async () => {
    const id = savedId ?? (await save(false));
    if (!id) return;
    setManualOpen(true);  // let the issuer pick PDF or Word (and fill any scope/manual fields)
  };
  const runGenerate = async (id: string, manual: Record<string, string>, fmt: "pdf" | "docx" = "pdf") => {
    setBusy(true);
    try {
      await documentApi.render(id, {
        year: needsPeriod ? genYear : null, month: needsPeriod ? genMonth : null,
        record_key: needsRecord && genRecord.trim() ? genRecord.trim() : null,
        manual, fmt,
      });
      ok(fmt === "docx" ? "✓ Word document downloaded." : "✓ PDF downloaded."); setManualOpen(false);
    } catch (e) { fail(e); } finally { setBusy(false); }
  };

  return (
    <Box sx={{ maxWidth: 1560, mx: "auto" }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1.5 }}>
        <Box>
          <Typography variant="h4">{editingId ? "Edit" : "Design"} {docType === "email" ? "Email template" : "Letter"}</Typography>
          <Typography variant="body2" color="text.secondary">Add blocks, bind data with fields, then preview and generate.</Typography>
        </Box>
        <Stack direction="row" spacing={1}>
          <Button variant="text" onClick={() => navigate("/documents")}>Back</Button>
          <Button variant="outlined" startIcon={<VisibilityOutlined />} disabled={busy} onClick={doPreview}>Preview</Button>
          <Button variant="outlined" startIcon={<Save />} disabled={busy} onClick={() => save(false)}>Save draft</Button>
          <Button variant="contained" startIcon={<Publish />} disabled={busy || !name.trim()} onClick={() => save(true)}>Publish</Button>
          {docType !== "email" && (
            <Button variant="outlined" startIcon={<FileDownloadOutlined />} disabled={busy} onClick={generate}>Generate</Button>
          )}
        </Stack>
      </Stack>

      <Box sx={{ display: "grid", gap: 2, alignItems: "start", gridTemplateColumns: { xs: "1fr", lg: "minmax(0,1fr) 250px" } }}>
        {/* SETTINGS — narrow right column */}
        <Box sx={{ gridColumn: { lg: 2 }, gridRow: { lg: 1 }, display: "flex", flexDirection: "column", gap: 1.5, minWidth: 0 }}>
        <Card variant="outlined"><CardContent sx={{ py: 1.5 }}>
          <Stack spacing={1}>
            <Button component="label" size="small" variant="outlined" disabled={busy} fullWidth
              startIcon={extracting ? <CircularProgress size={14} color="inherit" /> : <CloudUpload />}>
              {extracting ? "Reading sample…" : "Start from a sample"}
              <input hidden type="file" accept=".doc,.docx,.xlsx,.xls,.pdf,image/*,application/msword" onChange={(e) => e.target.files?.[0] && onSample(e.target.files[0])} />
            </Button>
            {design.blocks.some((b) => b.type === "text") && (
              <Button size="small" variant="text" disabled={busy} onClick={onEnhance} fullWidth
                startIcon={enhancing ? <CircularProgress size={14} color="inherit" /> : <AutoAwesome />}
                sx={{ textTransform: "none", color: "#7C3AED" }}>
                {enhancing ? "Mapping…" : "Smart map with AI"}
              </Button>
            )}
            <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>
              Word (.doc or .docx) «fields» bind through your catalogue (same as Display Name). Leftovers stay amber — Make dynamic.
            </Typography>
          </Stack>
        </CardContent></Card>

        <Card variant="outlined"><CardContent sx={{ py: 1.5 }}>
          <Button size="small" variant="outlined" fullWidth startIcon={<Add />}
            onClick={(e) => setAddAnchor(e.currentTarget)} sx={{ textTransform: "none" }}>
            Add block
          </Button>
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.75 }}>
            Adds it to the letter. You can also format &amp; insert fields with the toolbar inside a text block.
          </Typography>
        </CardContent></Card>

        <Card variant="outlined"><CardContent sx={{ py: 1.5 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>Details</Typography>
          <Stack spacing={1.25}>
            <TextField size="small" label="Name" value={name} onChange={(e) => setName(e.target.value)} fullWidth />
            <TextField size="small" label="Category" value={category} onChange={(e) => setCategory(e.target.value)} fullWidth
              select={categories.length > 0} SelectProps={{ displayEmpty: true }}>
              {categories.length > 0 && [
                <MenuItem key="_none" value=""><em>General</em></MenuItem>,
                ...categories.map((c) => <MenuItem key={c.id} value={c.name}>{c.name}</MenuItem>),
              ]}
            </TextField>
            {docType === "email" && (
              <TextField size="small" label="Subject (supports {{fields}})" value={subject}
                onChange={(e) => setSubject(e.target.value)} fullWidth />
            )}
          </Stack>
        </CardContent></Card>

        <LetterheadPanel onApply={(header, footer) => patchDesign({ header_html: header, footer_html: footer })} />

        <Card variant="outlined"><CardContent sx={{ py: 1.5 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.5 }}>Manual fields</Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1 }}>
            Values the issuer types when generating. Reuse them across letters — your
            library is shared by every letter (and private to your organisation).
          </Typography>

          {/* Reusable pool — pick one to add it to this letter */}
          {poolToAdd.length > 0 && (
            <>
              <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600, display: "block", mb: 0.5 }}>
                From your library
              </Typography>
              <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap sx={{ mb: 1 }}>
                {poolToAdd.map((m) => (
                  <Chip key={m.id} size="small" variant="outlined" label={m.label} clickable icon={<Add />}
                    onClick={() => applyToLetter(m)} onDelete={() => deletePoolField(m)}
                    deleteIcon={<Tooltip title="Remove from library"><DeleteOutline fontSize="small" /></Tooltip>} />
                ))}
              </Stack>
            </>
          )}

          {/* Fields on THIS letter — click to insert the token where the cursor is */}
          {manualFields.length > 0 && (
            <>
              <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600, display: "block", mb: 0.5 }}>
                In this letter
              </Typography>
              <Stack spacing={0.5} sx={{ mb: 1 }}>
                {manualFields.map((m) => (
                  <Stack key={m.key} direction="row" alignItems="center" spacing={0.5}>
                    <Tooltip title="Click in the letter first, then click here to insert it there">
                      <Chip size="small" color="secondary" variant="outlined" label={m.label} clickable
                        icon={<Add />} onClick={() => insertFieldToken(`manual.${m.key}`)}
                        sx={{ flex: 1, justifyContent: "flex-start" }} />
                    </Tooltip>
                    <IconButton size="small" onClick={() => removeManualField(m.key)}><DeleteOutline fontSize="small" /></IconButton>
                  </Stack>
                ))}
              </Stack>
            </>
          )}

          <Stack direction="row" spacing={1}>
            <TextField size="small" fullWidth value={manualDraft} placeholder="New field, e.g. Effective Date"
              onChange={(e) => setManualDraft(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") addManualField(manualDraft); }} />
            <Button size="small" variant="outlined" disabled={!manualDraft.trim()} onClick={() => addManualField(manualDraft)}>Add</Button>
          </Stack>
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.5 }}>
            New fields join your library and this letter. Click <b>Save draft</b> to keep the letter.
          </Typography>
        </CardContent></Card>

        {selected ? (
          <BlockProperties block={selected} fields={pickerFields}
            onChange={(patch) => updateBlock(selected.id, patch)}
            onStyle={(patch) => updateStyle(selected.id, patch)} />
        ) : (
          <Card variant="outlined" ref={scopeRef}><CardContent sx={{ py: 1.5 }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>Page &amp; data scope</Typography>
            <Stack spacing={1.25}>
              <Stack spacing={1}>
                <Box>
                  <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 0.5 }}>Paper</Typography>
                  <ToggleButtonGroup size="small" exclusive value={design.page_size}
                    onChange={(_, v) => v && patchDesign({ page_size: v })} fullWidth>
                    <ToggleButton value="A4">A4</ToggleButton>
                    <ToggleButton value="Letter">Letter</ToggleButton>
                  </ToggleButtonGroup>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 0.5 }}>Orientation</Typography>
                  <ToggleButtonGroup size="small" exclusive value={design.orientation}
                    onChange={(_, v) => v && patchDesign({ orientation: v })} fullWidth>
                    <ToggleButton value="portrait">Portrait</ToggleButton>
                    <ToggleButton value="landscape">Landscape</ToggleButton>
                  </ToggleButtonGroup>
                </Box>
              </Stack>
              <Typography variant="caption" color="text.secondary">Margins (mm)</Typography>
              <Box sx={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 1 }}>
                <TextField size="small" type="number" label="T" value={design.margin_top ?? design.margin_mm}
                  onChange={(e) => patchDesign({ margin_top: Number(e.target.value) })} />
                <TextField size="small" type="number" label="R" value={design.margin_right ?? design.margin_mm}
                  onChange={(e) => patchDesign({ margin_right: Number(e.target.value) })} />
                <TextField size="small" type="number" label="B" value={design.margin_bottom ?? design.margin_mm}
                  onChange={(e) => patchDesign({ margin_bottom: Number(e.target.value) })} />
                <TextField size="small" type="number" label="L" value={design.margin_left ?? design.margin_mm}
                  onChange={(e) => patchDesign({ margin_left: Number(e.target.value) })} />
              </Box>
              <FormControlLabel control={<Switch size="small" checked={Boolean(design.show_page_numbers)}
                onChange={(e) => patchDesign({ show_page_numbers: e.target.checked })} />}
                label={<Typography variant="body2">Show page numbers</Typography>} />
              <Divider />
              <Typography variant="caption" color="text.secondary">Which records this generates for:</Typography>
              <Labeled label="Period — Year"><FieldSelect fields={fields} value={design.period_year_ref ?? null} optional
                onChange={(ref) => patchDesign({ period_year_ref: ref })} placeholder="No year filter" minWidth={0} /></Labeled>
              <Labeled label="Period — Month"><FieldSelect fields={fields} value={design.period_month_ref ?? null} optional
                onChange={(ref) => patchDesign({ period_month_ref: ref })} placeholder="No month filter" minWidth={0} /></Labeled>
              <Labeled label="One per record"
                hint={'Pick the field that uniquely identifies who this letter is for — usually '
                  + '"Employee Number". A separate PDF/email is generated for each distinct value, '
                  + 'e.g. one letter per employee. Leave blank only for a single shared document '
                  + '(e.g. a company-wide notice) — required before you can publish a per-employee letter.'}>
                <FieldSelect fields={fields} value={design.record_key_ref ?? null}
                  optional={!recordKeyError}
                  onChange={(ref) => { setRecordKeyError(false); patchDesign({ record_key_ref: ref }); }}
                  placeholder="e.g. Employee Number" minWidth={0} />
              </Labeled>
            </Stack>
          </CardContent></Card>
        )}
        </Box>

        {/* LEFT — toolbar + canvas (wide column) */}
        <Box sx={{ gridColumn: { lg: 1 }, gridRow: { lg: 1 }, minWidth: 0 }}>
      {(extracting || enhancing) && (
        <Box sx={{ mb: 1.5 }}>
          <LinearProgress sx={{ borderRadius: 2 }} />
          <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: "block" }}>
            {enhancing
              ? "Asking the AI to map the remaining dynamic values — this can take a few seconds…"
              : "Reading your sample and mapping its data to fields…"}
          </Typography>
        </Box>
      )}

      {quickFields.length > 0 && (
        <Box sx={{ mb: 1.5 }}>
          <Typography variant="caption" color="warning.main" sx={{ fontWeight: 600 }}>
            Needs a field — click to add &amp; bind:
          </Typography>
          <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap sx={{ mt: 0.5 }}>
            {quickFields.map((f, i) => (
              <Chip key={`${f.label}${i}`} size="small" label={f.label} icon={<Add />} onClick={() => addFieldBlock(f.ref, f.label)} sx={{ height: 24 }} />
            ))}
          </Stack>
        </Box>
      )}

      {/* CANVAS — only the letter page lives here; blocks are added from the right panel */}
      <Box>
        <Box sx={{ bgcolor: "#EEF1F4", borderRadius: 2, p: { xs: 1, md: 3 }, minHeight: 560 }}>
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
          <Box sx={{
            mx: "auto", bgcolor: "#fff", boxShadow: "0 1px 10px rgba(0,0,0,0.10)",
            width: design.orientation === "landscape" ? "100%" : "min(880px, 100%)",
            minHeight: 900,
            p: `${design.margin_top ?? design.margin_mm}mm ${design.margin_right ?? design.margin_mm}mm ${design.margin_bottom ?? design.margin_mm}mm ${design.margin_left ?? design.margin_mm}mm`,
          }}>
            {extracting ? (
              <Box sx={{ textAlign: "center", color: "#6B7280", py: 10 }}>
                <CircularProgress size={30} />
                <Typography sx={{ mt: 1.5, fontWeight: 600 }}>Reading your sample…</Typography>
                <Typography variant="body2">Extracting the letter and auto-mapping its data fields.</Typography>
              </Box>
            ) : (
              <>
                {/* Applied letterhead header — shown on the canvas as it prints */}
                {design.header_html && (
                  <Box sx={{ position: "relative", borderBottom: "1px solid #E5E7EB", pb: 1, mb: 2 }}>
                    <Box sx={{ fontSize: "0.9rem", "& img": { maxHeight: 64 } }}
                      dangerouslySetInnerHTML={{ __html: design.header_html }} />
                    <Chip size="small" label="Header" onDelete={() => patchDesign({ header_html: "" })}
                      sx={{ position: "absolute", top: -10, right: 0, height: 18, fontSize: "0.6rem", opacity: 0.7 }} />
                  </Box>
                )}
                {design.blocks.length === 0 ? (
                  <DropZone empty />
                ) : (
                  <>
                    <SortableContext items={design.blocks.map((b) => b.id)} strategy={verticalListSortingStrategy}>
                      {design.blocks.map((b) => (
                        <SortableBlock key={b.id} block={b} selected={sel === b.id} onSelect={() => setSel(b.id)}
                          onRemove={() => removeBlock(b.id)} fields={pickerFields}
                          onChange={(patch) => updateBlock(b.id, patch)}
                          registerEditor={(ed) => { editors.current[b.id] = ed; }}
                          onFocusBlock={() => setActiveText(b.id)}
                          textEpoch={editorEpoch} />
                      ))}
                    </SortableContext>
                    <DropZone />
                  </>
                )}
                {/* Applied letterhead footer */}
                {design.footer_html && (
                  <Box sx={{ position: "relative", borderTop: "1px solid #E5E7EB", pt: 1, mt: 3, color: "#6B7280", fontSize: "0.8rem" }}>
                    <Box dangerouslySetInnerHTML={{ __html: design.footer_html }} />
                    <Chip size="small" label="Footer" onDelete={() => patchDesign({ footer_html: "" })}
                      sx={{ position: "absolute", bottom: -10, right: 0, height: 18, fontSize: "0.6rem", opacity: 0.7 }} />
                  </Box>
                )}
              </>
            )}
          </Box>
          </DndContext>
        </Box>
      </Box>
        </Box>
      </Box>

      {/* Add-block menu (compact replacement for the old palette) */}
      <Menu anchorEl={addAnchor} open={Boolean(addAnchor)} onClose={() => setAddAnchor(null)}>
        {PALETTE.map((p) => (
          <MenuItem key={p.type} onClick={(e) => { setAddAnchor(null); p.type === "field" ? onAddField(e.currentTarget) : addBlock(p.type); }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>{p.icon} {p.label}</Box>
          </MenuItem>
        ))}
      </Menu>

      {/* Insert a field into the active text editor (from the top toolbar) */}
      <Popover open={Boolean(fieldAnchor) && !mapField} anchorEl={fieldAnchor} onClose={() => setFieldAnchor(null)}
        anchorOrigin={{ vertical: "bottom", horizontal: "left" }}>
        <Box sx={{ p: 1.5, width: 320 }}>
          <Autocomplete
            options={[...pickerFields].sort((a, b) =>
              Number(!!b.is_anchor) - Number(!!a.is_anchor)
              || a.entity.localeCompare(b.entity) || a.label.localeCompare(b.label))}
            groupBy={(o) => o.entity}
            getOptionLabel={(o) => o.label}
            onChange={(_, v) => v && onFieldPicked(v)}
            renderInput={(p) => <TextField {...p} autoFocus size="small" label="Insert field into the text" placeholder="Search fields…" />}
            renderOption={(props, o) => (
              <li {...props} key={o.ref}>
                <Box>
                  <Box sx={{ fontSize: "0.85rem" }}>{o.label}</Box>
                  <Box sx={{ fontSize: "0.7rem", color: "#9CA3AF", fontFamily: "ui-monospace, monospace" }}>{o.ref}</Box>
                  {o.description && (
                    <Box sx={{ fontSize: "0.7rem", color: "#6B7280" }}>{o.description}</Box>
                  )}
                  {!!o.sample_values?.length && (
                    <Box sx={{ fontSize: "0.7rem", color: "#6B7280", fontStyle: "italic" }}>
                      e.g. {o.sample_values.join(", ")}
                    </Box>
                  )}
                </Box>
              </li>
            )}
          />
        </Box>
      </Popover>
      <ValueMapPopover anchorEl={fieldAnchor} field={mapField}
        onClose={() => setMapField(null)} onInsert={insertTokenInner} />

      {previewOpen && savedId && (
        <DocumentPreviewInline id={savedId} docType={docType} onClose={() => setPreviewOpen(false)} />
      )}

      {/* Generate — collect the record / period / manual values this design needs */}
      <Dialog open={manualOpen} onClose={() => setManualOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle sx={{ fontSize: "1rem" }}>Generate document</DialogTitle>
        <DialogContent>
          <Stack spacing={1.5} sx={{ mt: 1 }}>
            {!needsRecord && !needsPeriod && manualFields.length === 0 && (
              <Typography variant="body2" color="text.secondary">Generates for everyone in scope. Choose a format below.</Typography>
            )}
            {needsRecord && (
              <TextField size="small" label="Employee ID" value={genRecord} autoFocus fullWidth
                onChange={(e) => setGenRecord(e.target.value)}
                helperText="Leave blank to generate for everyone the filters match" />
            )}
            {needsPeriod && (
              <Stack direction="row" spacing={1.5}>
                <TextField size="small" type="number" label="Year" value={genYear} onChange={(e) => setGenYear(Number(e.target.value))} sx={{ width: 110 }} />
                <TextField select size="small" label="Month" value={genMonth} onChange={(e) => setGenMonth(Number(e.target.value))} sx={{ width: 120 }}>
                  {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => <MenuItem key={m} value={m}>{m}</MenuItem>)}
                </TextField>
              </Stack>
            )}
            {manualFields.map((m) => (
              <TextField key={m.key} size="small" label={m.label} value={manualVals[m.key] ?? ""}
                onChange={(e) => setManualVals((v) => ({ ...v, [m.key]: e.target.value }))} fullWidth />
            ))}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setManualOpen(false)}>Cancel</Button>
          <Button variant="outlined" startIcon={<DescriptionOutlined />} disabled={busy}
            onClick={() => savedId && runGenerate(savedId, manualVals, "docx")}>Word</Button>
          <Button variant="contained" startIcon={<PictureAsPdf />} disabled={busy}
            onClick={() => savedId && runGenerate(savedId, manualVals, "pdf")}>PDF</Button>
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

function Labeled({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <Box>
      <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, mb: 0.25 }}>
        <Typography variant="caption" color="text.secondary">{label}</Typography>
        {hint && (
          <Tooltip title={hint} placement="top" arrow>
            <InfoOutlined sx={{ fontSize: 14, color: "#9CA3AF", cursor: "help" }} />
          </Tooltip>
        )}
      </Box>
      {children}
    </Box>
  );
}

// Drop target for appending at the end (or the empty-canvas prompt).
function DropZone({ empty }: { empty?: boolean }) {
  const { setNodeRef, isOver } = useDroppable({ id: "APPEND" });
  if (empty) {
    return (
      <Box ref={setNodeRef} sx={{ textAlign: "center", py: 8, borderRadius: 1,
        color: isOver ? "#007499" : "#9CA3AF", border: isOver ? "2px dashed #007499" : "2px dashed transparent" }}>
        <TextFields sx={{ fontSize: 34 }} />
        <Typography sx={{ mt: 1 }}>Drag a block here (or click one above), or “Start from a sample”.</Typography>
      </Box>
    );
  }
  return <Box ref={setNodeRef} sx={{ minHeight: 32, mt: 1, borderRadius: 1,
    border: isOver ? "2px dashed #007499" : "2px dashed transparent" }} />;
}

// One block on the canvas: drag handle + selectable frame + type-specific editor.
function SortableBlock({
  block, selected, onSelect, onRemove, onChange, fields, registerEditor, onFocusBlock, textEpoch,
}: {
  block: DesignBlock;
  selected: boolean;
  onSelect: () => void;
  onRemove: () => void;
  onChange: (patch: Partial<DesignBlock>) => void;
  fields: SemanticFieldMeta[];
  registerEditor?: (editor: Editor | null) => void;
  onFocusBlock?: () => void;
  textEpoch?: number;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: block.id });
  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.6 : 1 };
  const blockStyle = styleToCss(block);
  return (
    <Box ref={setNodeRef} style={style} onClick={onSelect}
      sx={{
        position: "relative", borderRadius: 1, px: 1, py: 0.5, mb: 0.5,
        border: selected ? "1.5px solid #007499" : "1.5px solid transparent",
        "&:hover": { border: selected ? "1.5px solid #007499" : "1.5px dashed #CBD5E1" },
        "&:hover .blk-tools": { opacity: 1 },
      }}>
      <Stack className="blk-tools" direction="row" spacing={0.25} sx={{
        position: "absolute", top: -12, right: 4, opacity: selected ? 1 : 0, transition: "opacity .15s",
        bgcolor: "#fff", border: "1px solid #E5E7EB", borderRadius: 1, zIndex: 2,
      }}>
        <IconButton size="small" {...attributes} {...listeners} sx={{ cursor: "grab" }}><DragIndicator sx={{ fontSize: 16 }} /></IconButton>
        <IconButton size="small" onClick={(e) => { e.stopPropagation(); onRemove(); }}><DeleteOutline sx={{ fontSize: 16 }} /></IconButton>
      </Stack>

      <Box sx={blockStyle}>
        {block.type === "text" && (
          <RichTextBlock key={textEpoch ?? 0} html={block.html || ""} fields={fields} onChange={(html) => onChange({ html })}
            registerEditor={registerEditor} onFocusBlock={onFocusBlock} />
        )}
        {block.type === "field" && (
          <Typography component="span" sx={{ fontSize: "inherit" }}>
            {block.label && <b style={{ color: "#6B7280" }}>{block.label}: </b>}
            <span style={{ background: "#E6F3F7", color: "#036", borderRadius: 4, padding: "0 4px", fontFamily: "ui-monospace, monospace", fontSize: "0.8em" }}>
              {block.prefix}{block.ref ? `{{${block.ref}}}` : "(pick a field →)"}{block.suffix}
            </span>
          </Typography>
        )}
        {block.type === "image" && (
          block.src
            ? <img src={block.src} alt="" style={{ width: `${block.width_pct || 30}%` }} />
            : <Box sx={{ border: "1px dashed #CBD5E1", borderRadius: 1, py: 2, textAlign: "center", color: "#9CA3AF" }}>
                <ImageOutlined /> <Typography variant="caption" display="block">Upload an image in properties →</Typography>
              </Box>
        )}
        {block.type === "table" && (
          <Box sx={{ border: "1px solid #E5E7EB", borderRadius: 1, p: 1 }}>
            <Typography variant="caption" color="text.secondary">Table — {(block.columns?.length ?? 0)} column(s). Configure in properties →</Typography>
          </Box>
        )}
        {block.type === "divider" && <Divider />}
        {block.type === "spacer" && <Box sx={{ height: block.height_px || 24 }} />}
        {block.type === "signature" && (
          <Box><Box sx={{ borderTop: "1px solid #374151", width: 220, mt: 4 }} />
            <Typography variant="caption" color="text.secondary">{block.label || "Signature"}</Typography></Box>
        )}
      </Box>
    </Box>
  );
}

function BlockProperties({
  block, fields, onChange, onStyle,
}: {
  block: DesignBlock;
  fields: SemanticFieldMeta[];
  onChange: (patch: Partial<DesignBlock>) => void;
  onStyle: (patch: Record<string, string | number>) => void;
}) {
  const onImage = (file: File) => {
    const reader = new FileReader();
    reader.onload = () => onChange({ src: String(reader.result) });
    reader.readAsDataURL(file);
  };
  return (
    <Card variant="outlined"><CardContent sx={{ py: 1.5 }}>
      <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1, textTransform: "capitalize" }}>{block.type} block</Typography>
      <Stack spacing={1.25}>
        {block.type === "field" && (
          <>
            <FieldSelect fields={fields} value={block.ref ?? null} onChange={(ref) => onChange({ ref })} placeholder="Bind a field" minWidth={0} />
            <TextField size="small" label="Label (optional)" value={block.label ?? ""} onChange={(e) => onChange({ label: e.target.value })} />
            <Stack direction="row" spacing={1}>
              <TextField size="small" label="Prefix" value={block.prefix ?? ""} onChange={(e) => onChange({ prefix: e.target.value })} />
              <TextField size="small" label="Suffix" value={block.suffix ?? ""} onChange={(e) => onChange({ suffix: e.target.value })} />
            </Stack>
          </>
        )}
        {block.type === "signature" && (
          <TextField size="small" label="Caption" value={block.label ?? ""} onChange={(e) => onChange({ label: e.target.value })} />
        )}
        {block.type === "spacer" && (
          <TextField size="small" type="number" label="Height (px)" value={block.height_px ?? 24} onChange={(e) => onChange({ height_px: Number(e.target.value) })} />
        )}
        {block.type === "image" && (
          <>
            <Button component="label" size="small" variant="outlined" startIcon={<CloudUpload />}>
              Upload image<input hidden type="file" accept="image/*" onChange={(e) => e.target.files?.[0] && onImage(e.target.files[0])} />
            </Button>
            <TextField size="small" type="number" label="Width (%)" value={block.width_pct ?? 30} onChange={(e) => onChange({ width_pct: Number(e.target.value) })} />
          </>
        )}
        {block.type === "table" && (
          <TableColumns block={block} fields={fields} onChange={onChange} />
        )}

        {(block.type === "text" || block.type === "field" || block.type === "signature" || block.type === "image") && (
          <>
            <Divider />
            <Labeled label="Align">
              <ToggleButtonGroup size="small" exclusive value={block.align ?? "left"} onChange={(_, v) => v && onChange({ align: v })}>
                <ToggleButton value="left"><FormatAlignLeft fontSize="small" /></ToggleButton>
                <ToggleButton value="center"><FormatAlignCenter fontSize="small" /></ToggleButton>
                <ToggleButton value="right"><FormatAlignRight fontSize="small" /></ToggleButton>
              </ToggleButtonGroup>
            </Labeled>
          </>
        )}

        {(block.type === "text" || block.type === "field" || block.type === "signature") && (
          <>
            <Stack direction="row" spacing={1}>
              <TextField size="small" label="Font size" placeholder="12pt" value={String(block.style?.fontSize ?? "")}
                onChange={(e) => onStyle({ fontSize: e.target.value })} />
              <TextField size="small" type="color" label="Color" value={String(block.style?.color ?? "#1F2937")}
                onChange={(e) => onStyle({ color: e.target.value })} sx={{ width: 90 }} />
            </Stack>
          </>
        )}
      </Stack>
    </CardContent></Card>
  );
}

function TableColumns({
  block, fields, onChange,
}: {
  block: DesignBlock;
  fields: SemanticFieldMeta[];
  onChange: (patch: Partial<DesignBlock>) => void;
}) {
  const cols = block.columns ?? [];
  const add = (ref: string | null) => {
    if (!ref) return;
    const f = fields.find((x) => x.ref === ref);
    onChange({ columns: [...cols, { ref, label: f?.label ?? ref }] });
  };
  const remove = (i: number) => onChange({ columns: cols.filter((_, j) => j !== i) });
  return (
    <>
      <Typography variant="caption" color="text.secondary">Columns (each binds a field)</Typography>
      {cols.map((c, i) => (
        <Stack key={i} direction="row" spacing={0.5} alignItems="center">
          <Chip size="small" label={c.label ?? c.ref} sx={{ flex: 1, justifyContent: "flex-start" }} />
          <IconButton size="small" onClick={() => remove(i)}><DeleteOutline fontSize="small" /></IconButton>
        </Stack>
      ))}
      <FieldSelect fields={fields} value={null} onChange={add} placeholder="Add a column…" minWidth={0} optional />
    </>
  );
}

// Map a block's align/style to a CSS object for the canvas preview.
function styleToCss(block: DesignBlock): Record<string, string | number> {
  const s = block.style || {};
  const css: Record<string, string | number> = {};
  if (block.align) css.textAlign = block.align;
  if (s.fontSize) css.fontSize = s.fontSize;
  if (s.color) css.color = s.color as string;
  if (s.fontWeight) css.fontWeight = s.fontWeight;
  return css;
}
