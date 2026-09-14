// Letterhead presets (logo + header + footer) — pick one and apply it to the canvas,
// or manage the tenant's letterheads. Applying sets the design's header/footer.
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Box, Button, Card, CardContent, Dialog, DialogActions, DialogContent, DialogTitle,
  IconButton, MenuItem, Stack, TextField, Tooltip, Typography,
} from "@mui/material";
import { CloudUpload, DeleteOutline, EditOutlined, PostAddOutlined } from "@mui/icons-material";
import { documentApi, semanticApi } from "../../api/client";
import type { Letterhead } from "../../types/document";
import type { SemanticFieldMeta } from "../../types/spec";
import { RichTextBlock } from "./blocks/RichTextBlock";

// Compose a letterhead into a header HTML string (logo + header markup).
export function composeHeader(lh: Letterhead): string {
  const logo = lh.logo_data_url ? `<img src="${lh.logo_data_url}" style="max-height:64px"/>` : "";
  return [logo, lh.header_html].filter(Boolean).join(" ");
}

export function LetterheadPanel({ onApply }: { onApply: (header: string, footer: string) => void }) {
  const qc = useQueryClient();
  const { data: letterheads = [] } = useQuery({ queryKey: ["letterheads"], queryFn: documentApi.letterheads });
  const [picked, setPicked] = useState("");
  const [manageOpen, setManageOpen] = useState(false);
  const [edit, setEdit] = useState<Letterhead | null>(null);

  const apply = () => {
    const lh = letterheads.find((l) => l.id === picked);
    if (lh) onApply(composeHeader(lh), lh.footer_html || "");
  };
  const refresh = () => qc.invalidateQueries({ queryKey: ["letterheads"] });

  return (
    <Card variant="outlined"><CardContent sx={{ py: 1.5 }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 0.5 }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>Letterhead</Typography>
        <Button size="small" startIcon={<PostAddOutlined />} onClick={() => { setEdit(null); setManageOpen(true); }} sx={{ textTransform: "none" }}>Manage</Button>
      </Stack>
      <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1 }}>
        Apply a saved logo + header + footer preset to this document.
      </Typography>
      <Stack direction="row" spacing={1}>
        <TextField select size="small" fullWidth label="Preset" value={picked}
          onChange={(e) => setPicked(e.target.value)}>
          {letterheads.length === 0 && <MenuItem value="" disabled>No letterheads yet</MenuItem>}
          {letterheads.map((l) => <MenuItem key={l.id} value={l.id}>{l.name}</MenuItem>)}
        </TextField>
        <Button variant="outlined" size="small" disabled={!picked} onClick={apply}>Apply</Button>
      </Stack>

      <ManageDialog open={manageOpen} onClose={() => setManageOpen(false)} letterheads={letterheads}
        edit={edit} setEdit={setEdit} onChanged={refresh} />
    </CardContent></Card>
  );
}

function ManageDialog({
  open, onClose, letterheads, edit, setEdit, onChanged,
}: {
  open: boolean; onClose: () => void; letterheads: Letterhead[];
  edit: Letterhead | null; setEdit: (l: Letterhead | null) => void; onChanged: () => void;
}) {
  const { data: fields = [] } = useQuery({ queryKey: ["fields", "builder"], queryFn: semanticApi.fieldsForBuilder });
  const [name, setName] = useState("");
  const [logo, setLogo] = useState<string | null>(null);
  const [header, setHeader] = useState("");
  const [footer, setFooter] = useState("");
  const [busy, setBusy] = useState(false);

  const startEdit = (l: Letterhead | null) => {
    setEdit(l);
    setName(l?.name ?? ""); setLogo(l?.logo_data_url ?? null);
    setHeader(l?.header_html ?? ""); setFooter(l?.footer_html ?? "");
  };
  const onLogo = (file: File) => {
    const r = new FileReader();
    r.onload = () => setLogo(String(r.result));
    r.readAsDataURL(file);
  };
  const save = async () => {
    if (!name.trim()) return;
    setBusy(true);
    try {
      const body = { name, logo_data_url: logo, header_html: header, footer_html: footer };
      if (edit) await documentApi.updateLetterhead(edit.id, body);
      else await documentApi.createLetterhead(body);
      onChanged(); startEdit(null);
    } finally { setBusy(false); }
  };
  const remove = async (id: string) => { await documentApi.deleteLetterhead(id); onChanged(); if (edit?.id === id) startEdit(null); };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ fontSize: "1rem" }}>Letterheads</DialogTitle>
      <DialogContent dividers>
        {letterheads.length > 0 && (
          <Stack spacing={0.5} sx={{ mb: 2 }}>
            {letterheads.map((l) => (
              <Stack key={l.id} direction="row" alignItems="center" spacing={1}>
                {l.logo_data_url && <img src={l.logo_data_url} alt="" style={{ height: 22 }} />}
                <Typography variant="body2" sx={{ flex: 1 }}>{l.name}</Typography>
                <IconButton size="small" onClick={() => startEdit(l)}><EditOutlined fontSize="small" /></IconButton>
                <IconButton size="small" onClick={() => remove(l.id)}><DeleteOutline fontSize="small" /></IconButton>
              </Stack>
            ))}
          </Stack>
        )}
        <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>{edit ? "Edit letterhead" : "New letterhead"}</Typography>
        <Stack spacing={1.5}>
          <TextField size="small" label="Name" value={name} onChange={(e) => setName(e.target.value)} fullWidth />
          <Stack direction="row" spacing={1} alignItems="center">
            <Button component="label" size="small" variant="outlined" startIcon={<CloudUpload />}>
              {logo ? "Change logo" : "Upload logo"}
              <input hidden type="file" accept="image/*" onChange={(e) => e.target.files?.[0] && onLogo(e.target.files[0])} />
            </Button>
            {logo && <img src={logo} alt="" style={{ height: 28 }} />}
            {logo && <Tooltip title="Remove logo"><IconButton size="small" onClick={() => setLogo(null)}><DeleteOutline fontSize="small" /></IconButton></Tooltip>}
          </Stack>
          <Box>
            <Typography variant="caption" color="text.secondary">Header — format it & insert dynamic fields (company name, department, phone, address…)</Typography>
            <Box sx={{ border: "1px solid #E5E7EB", borderRadius: 1.5, p: 1, mt: 0.5 }}>
              <RichTextBlock key={`h-${edit?.id ?? "new"}`} html={header} fields={fields as SemanticFieldMeta[]} onChange={setHeader} />
            </Box>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary">Footer</Typography>
            <Box sx={{ border: "1px solid #E5E7EB", borderRadius: 1.5, p: 1, mt: 0.5 }}>
              <RichTextBlock key={`f-${edit?.id ?? "new"}`} html={footer} fields={fields as SemanticFieldMeta[]} onChange={setFooter} />
            </Box>
          </Box>
        </Stack>
      </DialogContent>
      <DialogActions>
        {edit && <Button onClick={() => startEdit(null)}>New</Button>}
        <Box sx={{ flex: 1 }} />
        <Button onClick={onClose}>Close</Button>
        <Button variant="contained" disabled={busy || !name.trim()} onClick={save}>{edit ? "Save" : "Add"}</Button>
      </DialogActions>
    </Dialog>
  );
}
