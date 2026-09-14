// Document Studio home — three document TYPES (Letter · Email · Report-doc), each
// with tenant-defined CATEGORIES and unlimited templates. Fully dynamic: create a
// category, then design templates (canvas for letters/emails, layout upload for
// report-docs), preview/generate from here.
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Box, Button, Card, CardContent, Chip, CircularProgress, Dialog, DialogActions,
  DialogContent, DialogTitle, IconButton, Menu, MenuItem, Stack, Tab, Tabs, TextField, Tooltip, Typography,
} from "@mui/material";
import {
  Add, PictureAsPdf, EditOutlined, MailOutline, DescriptionOutlined, ArticleOutlined,
  VisibilityOutlined, DeleteOutline, FolderOutlined, SearchOutlined, ContentCopyOutlined, MoreVert,
  FileDownloadOutlined,
} from "@mui/icons-material";

// Lifecycle status → chip label + colour.
const STATUS_META: Record<string, { label: string; color: "primary" | "default" | "warning" }> = {
  active: { label: "Active", color: "primary" },
  draft: { label: "Draft", color: "default" },
  inactive: { label: "Inactive", color: "warning" },
  archived: { label: "Archived", color: "default" },
};
import { documentApi } from "../../api/client";
import type { DocType, DocumentListItem, DocumentDesign } from "../../types/document";
import { DocumentPreviewDialog } from "./DocumentPreviewDialog";

const now = new Date();

const TYPES: { key: DocType; label: string; icon: React.ReactNode; blurb: string }[] = [
  { key: "letter", label: "Letters", icon: <ArticleOutlined />, blurb: "Design a letter on a canvas — drag blocks, add rich text, merge data fields, generate one page per employee." },
  { key: "email", label: "Email templates", icon: <MailOutline />, blurb: "Compose a reusable email body with merge fields and a dynamic subject. Preview against real records." },
  { key: "report", label: "Report documents", icon: <DescriptionOutlined />, blurb: "Payslip / statement / certificate — one page per record from an uploaded layout." },
];

export function DocumentsPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [type, setType] = useState<DocType>("letter");
  const [activeCat, setActiveCat] = useState<string | null>(null);

  const { data: documents = [], isLoading } = useQuery({
    queryKey: ["documents", type],
    queryFn: () => documentApi.list(type),
  });
  const { data: categories = [] } = useQuery({
    queryKey: ["doc-categories", type],
    queryFn: () => documentApi.categories(type),
  });

  // Categories to show = tenant-created ones ∪ any category already used by a template.
  const catNames = useMemo(() => {
    const s = new Set<string>(categories.map((c) => c.name));
    documents.forEach((d) => d.category && s.add(d.category));
    return [...s].sort();
  }, [categories, documents]);

  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "draft" | "inactive" | "archived">("all");
  const [sort, setSort] = useState<"updated" | "name" | "category">("updated");

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    let list = documents.filter((d) =>
      (!activeCat || d.category === activeCat) &&
      (statusFilter === "all" ? d.status !== "archived" : d.status === statusFilter) &&
      (!q || d.name.toLowerCase().includes(q) || (d.description ?? "").toLowerCase().includes(q) || d.category.toLowerCase().includes(q)),
    );
    list = [...list].sort((a, b) => {
      if (sort === "name") return a.name.localeCompare(b.name);
      if (sort === "category") return a.category.localeCompare(b.category) || a.name.localeCompare(b.name);
      return (b.updated_at ?? "").localeCompare(a.updated_at ?? "");  // newest first
    });
    return list;
  }, [documents, activeCat, query, statusFilter, sort]);

  const [gen, setGen] = useState<DocumentListItem | null>(null);
  const [preview, setPreview] = useState<DocumentListItem | null>(null);
  const [newCatOpen, setNewCatOpen] = useState(false);
  const [newCat, setNewCat] = useState("");

  const meta = TYPES.find((t) => t.key === type)!;

  const startNew = (category?: string) => {
    const cat = category ?? activeCat ?? "";
    const q = cat ? `?category=${encodeURIComponent(cat)}` : "";
    if (type === "report") navigate(`/documents/report/new${q}`);
    else navigate(`/documents/design/new?type=${type}${cat ? `&category=${encodeURIComponent(cat)}` : ""}`);
  };
  const openEdit = (d: DocumentListItem) => {
    if (d.doc_type === "report") navigate(`/documents/report/${d.id}/edit`);
    else navigate(`/documents/design/${d.id}/edit`);
  };
  const duplicate = async (d: DocumentListItem) => {
    const res = await documentApi.duplicate(d.id);
    qc.invalidateQueries({ queryKey: ["documents", type] });
    if (d.doc_type === "report") navigate(`/documents/report/${res.template_id}/edit`);
    else navigate(`/documents/design/${res.template_id}/edit`);
  };
  const [menuEl, setMenuEl] = useState<HTMLElement | null>(null);
  const [menuDoc, setMenuDoc] = useState<DocumentListItem | null>(null);
  const changeStatus = async (status: "active" | "inactive" | "archived") => {
    if (!menuDoc) return;
    await documentApi.setStatus(menuDoc.id, status);
    qc.invalidateQueries({ queryKey: ["documents", type] });
    setMenuEl(null); setMenuDoc(null);
  };

  const addCategory = async () => {
    const name = newCat.trim();
    if (!name) return;
    await documentApi.createCategory(type, name);
    setNewCat(""); setNewCatOpen(false);
    qc.invalidateQueries({ queryKey: ["doc-categories", type] });
    setActiveCat(name);
  };
  const removeCategory = async (id: string, name: string) => {
    await documentApi.deleteCategory(id);
    qc.invalidateQueries({ queryKey: ["doc-categories", type] });
    if (activeCat === name) setActiveCat(null);
  };

  return (
    <Box sx={{ maxWidth: 1040, mx: "auto" }}>
      <Typography variant="h4" sx={{ mb: 0.5 }}>Document Studio</Typography>
      <Typography variant="body2" sx={{ mb: 2 }}>
        Design letters, email templates and report documents — organised by category, bound to your data.
      </Typography>

      <Tabs value={type} onChange={(_, v) => { setType(v); setActiveCat(null); }} sx={{ mb: 2, borderBottom: "1px solid #E5E7EB" }}>
        {TYPES.map((t) => <Tab key={t.key} value={t.key} icon={t.icon as React.ReactElement} iconPosition="start" label={t.label} sx={{ minHeight: 48, textTransform: "none" }} />)}
      </Tabs>

      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1.5 }}>
        <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 620 }}>{meta.blurb}</Typography>
        <Button variant="contained" startIcon={<Add />} onClick={() => startNew()}>New {type === "report" ? "document" : type}</Button>
      </Stack>

      {/* Category chips + manage */}
      <Stack direction="row" spacing={0.75} alignItems="center" flexWrap="wrap" useFlexGap sx={{ mb: 2 }}>
        <FolderOutlined sx={{ fontSize: 18, color: "#9CA3AF" }} />
        <Chip label={`All (${documents.length})`} size="small" color={activeCat === null ? "primary" : "default"}
          variant={activeCat === null ? "filled" : "outlined"} onClick={() => setActiveCat(null)} />
        {catNames.map((name) => {
          const cat = categories.find((c) => c.name === name);
          const count = documents.filter((d) => d.category === name).length;
          return (
            <Chip key={name} size="small" label={`${name} (${count})`}
              color={activeCat === name ? "primary" : "default"} variant={activeCat === name ? "filled" : "outlined"}
              onClick={() => setActiveCat(name)}
              onDelete={cat ? () => removeCategory(cat.id, name) : undefined}
              deleteIcon={cat ? <DeleteOutline /> : undefined} />
          );
        })}
        <Button size="small" startIcon={<Add />} onClick={() => setNewCatOpen(true)} sx={{ textTransform: "none" }}>Category</Button>
      </Stack>

      {/* Search · status filter · sort */}
      <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap sx={{ mb: 1.5 }}>
        <TextField size="small" placeholder="Search name, description…" value={query}
          onChange={(e) => setQuery(e.target.value)} sx={{ minWidth: 240, flex: 1 }}
          InputProps={{ startAdornment: <SearchOutlined sx={{ fontSize: 18, color: "#9CA3AF", mr: 0.5 }} /> }} />
        <TextField select size="small" label="Status" value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as typeof statusFilter)} sx={{ width: 140 }}>
          <MenuItem value="all">All active</MenuItem>
          <MenuItem value="active">Active</MenuItem>
          <MenuItem value="draft">Draft</MenuItem>
          <MenuItem value="inactive">Inactive</MenuItem>
          <MenuItem value="archived">Archived</MenuItem>
        </TextField>
        <TextField select size="small" label="Sort" value={sort}
          onChange={(e) => setSort(e.target.value as typeof sort)} sx={{ width: 150 }}>
          <MenuItem value="updated">Last updated</MenuItem>
          <MenuItem value="name">Name</MenuItem>
          <MenuItem value="category">Category</MenuItem>
        </TextField>
      </Stack>

      {isLoading ? (
        <Box sx={{ textAlign: "center", py: 6 }}><CircularProgress /></Box>
      ) : shown.length === 0 ? (
        <Card><CardContent sx={{ textAlign: "center", py: 6, color: "text.secondary" }}>
          <Box sx={{ fontSize: 40, color: "#C4CAD2" }}>{meta.icon}</Box>
          <Typography sx={{ fontWeight: 600, mt: 1 }}>No {meta.label.toLowerCase()} yet</Typography>
          <Typography variant="body2" sx={{ mb: 2 }}>Create the first one — {type === "report" ? "upload a layout" : "design it on the canvas"}.</Typography>
          <Button variant="contained" startIcon={<Add />} onClick={() => startNew()}>New {type === "report" ? "document" : type}</Button>
        </CardContent></Card>
      ) : (
        <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" } }}>
          {shown.map((d) => (
            <Card key={d.id} variant="outlined">
              <CardContent sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", py: 1.5 }}>
                <Box sx={{ minWidth: 0 }}>
                  <Typography sx={{ fontWeight: 600 }} noWrap>{d.name}</Typography>
                  <Stack direction="row" spacing={0.75} alignItems="center" sx={{ mt: 0.5 }} flexWrap="wrap" useFlexGap>
                    <Chip size="small" label={d.category} sx={{ height: 20 }} />
                    <Chip size="small" color={STATUS_META[d.status]?.color ?? "default"}
                      label={STATUS_META[d.status]?.label ?? d.status} sx={{ height: 20 }} />
                    {d.version_no ? <Typography variant="caption" color="text.secondary">v{d.version_no}</Typography> : null}
                    {d.updated_at && <Typography variant="caption" color="text.secondary">· {new Date(d.updated_at).toLocaleDateString()}</Typography>}
                  </Stack>
                </Box>
                <Stack direction="row" spacing={0.5}>
                  <Tooltip title="Preview"><IconButton size="small" onClick={() => setPreview(d)}><VisibilityOutlined fontSize="small" /></IconButton></Tooltip>
                  <Tooltip title="Edit"><IconButton size="small" onClick={() => openEdit(d)}><EditOutlined fontSize="small" /></IconButton></Tooltip>
                  <Tooltip title="Duplicate"><IconButton size="small" onClick={() => duplicate(d)}><ContentCopyOutlined fontSize="small" /></IconButton></Tooltip>
                  {d.doc_type !== "email" && (
                    <Tooltip title={d.doc_type === "letter" ? "Generate & download (PDF or Word)" : "Generate & download PDF"}>
                      <IconButton size="small" onClick={() => setGen(d)}><FileDownloadOutlined fontSize="small" /></IconButton>
                    </Tooltip>
                  )}
                  <Tooltip title="More"><IconButton size="small" onClick={(e) => { setMenuEl(e.currentTarget); setMenuDoc(d); }}><MoreVert fontSize="small" /></IconButton></Tooltip>
                </Stack>
              </CardContent>
            </Card>
          ))}
        </Box>
      )}

      {/* Lifecycle actions */}
      <Menu anchorEl={menuEl} open={Boolean(menuEl)} onClose={() => { setMenuEl(null); setMenuDoc(null); }}>
        {menuDoc?.status !== "active" && <MenuItem onClick={() => changeStatus("active")}>Activate</MenuItem>}
        {menuDoc?.status === "active" && <MenuItem onClick={() => changeStatus("inactive")}>Deactivate</MenuItem>}
        {menuDoc?.status !== "archived" && <MenuItem onClick={() => changeStatus("archived")}>Archive</MenuItem>}
        {menuDoc?.status === "archived" && <MenuItem onClick={() => changeStatus("inactive")}>Restore</MenuItem>}
      </Menu>

      {/* New category */}
      <Dialog open={newCatOpen} onClose={() => setNewCatOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle>New {meta.label.toLowerCase()} category</DialogTitle>
        <DialogContent>
          <TextField autoFocus fullWidth size="small" label="Category name" value={newCat}
            onChange={(e) => setNewCat(e.target.value)} onKeyDown={(e) => e.key === "Enter" && addCategory()} sx={{ mt: 1 }}
            placeholder={type === "letter" ? "e.g. Offer Letters" : type === "email" ? "e.g. Onboarding" : "e.g. Payroll"} />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setNewCatOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={addCategory} disabled={!newCat.trim()}>Add</Button>
        </DialogActions>
      </Dialog>

      {/* Generate PDF (letter / report-doc) */}
      <GenerateDialog doc={gen} onClose={() => setGen(null)} />

      {/* Preview (letter / email / report) */}
      {preview && <DocumentPreviewDialog doc={preview} onClose={() => setPreview(null)} />}
    </Box>
  );
}

function GenerateDialog({ doc, onClose }: { doc: DocumentListItem | null; onClose: () => void }) {
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [recordKey, setRecordKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [design, setDesign] = useState<DocumentDesign | null>(null);
  const [manualVals, setManualVals] = useState<Record<string, string>>({});

  useEffect(() => {
    setManualVals({}); setRecordKey("");
    if (doc && doc.doc_type !== "report") {
      documentApi.get(doc.id).then((d) => setDesign(d.design)).catch(() => setDesign(null));
    } else setDesign(null);
  }, [doc]);

  // A report-doc always uses period; a letter/email uses whatever scope it was given.
  const isReport = doc?.doc_type === "report";
  const needsPeriod = isReport || Boolean(design?.period_year_ref && design?.period_month_ref);
  const needsRecord = Boolean(design?.record_key_ref);
  const manualFields = design?.manual_fields ?? [];

  const download = async (fmt: "pdf" | "docx" = "pdf") => {
    if (!doc) return;
    setBusy(true);
    try {
      await documentApi.render(doc.id, {
        year: needsPeriod ? year : null, month: needsPeriod ? month : null,
        record_key: needsRecord && recordKey.trim() ? recordKey.trim() : null,
        manual: manualVals, fmt,
      });
      onClose();
    } finally { setBusy(false); }
  };
  return (
    <Dialog open={Boolean(doc)} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>Generate “{doc?.name}”</DialogTitle>
      <DialogContent>
        {needsRecord && (
          <TextField size="small" label="Employee ID" value={recordKey} autoFocus fullWidth sx={{ mt: 1 }}
            onChange={(e) => setRecordKey(e.target.value)}
            helperText="Leave blank to generate for everyone the filters match" />
        )}
        {needsPeriod && (
          <Stack direction="row" spacing={1.5} sx={{ mt: needsRecord ? 2 : 1 }}>
            <TextField size="small" type="number" label="Year" value={year} onChange={(e) => setYear(Number(e.target.value))} sx={{ width: 120 }} />
            <TextField select size="small" label="Month" value={month} onChange={(e) => setMonth(Number(e.target.value))} sx={{ width: 140 }}>
              {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => <MenuItem key={m} value={m}>{m}</MenuItem>)}
            </TextField>
          </Stack>
        )}
        {!needsPeriod && !needsRecord && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>Generates for everyone in scope.</Typography>
        )}
        {manualFields.length > 0 && (
          <Stack spacing={1.25} sx={{ mt: 2 }}>
            <Typography variant="caption" color="text.secondary">Fill in the manual fields:</Typography>
            {manualFields.map((m) => (
              <TextField key={m.key} size="small" label={m.label} value={manualVals[m.key] ?? ""}
                onChange={(e) => setManualVals((v) => ({ ...v, [m.key]: e.target.value }))} fullWidth />
            ))}
          </Stack>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        {doc?.doc_type === "letter" && (
          <Button variant="outlined" startIcon={<DescriptionOutlined />} disabled={busy}
            onClick={() => download("docx")}>Word</Button>
        )}
        <Button variant="contained" startIcon={busy ? <CircularProgress size={16} color="inherit" /> : <PictureAsPdf />}
          disabled={busy} onClick={() => download("pdf")}>Download PDF</Button>
      </DialogActions>
    </Dialog>
  );
}
