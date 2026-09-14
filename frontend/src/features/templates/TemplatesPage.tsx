// Templates list + versions (FR-B10) — publish / rollback any version.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Box, Button, Card, CardContent, Chip, Collapse, Dialog, DialogActions, DialogContent,
  DialogContentText, DialogTitle, IconButton, ListItemIcon, ListItemText, Menu, MenuItem,
  Select, Stack, Table, TableBody, TableCell, TableHead, TableRow, TextField, Tooltip, Typography,
} from "@mui/material";
import {
  AddCircleOutline, ExpandMore, ExpandLess, PlayArrow, Edit, DriveFileRenameOutline, Check,
  DeleteOutline, KeyboardArrowDown, TableChartOutlined, DataObjectOutlined,
} from "@mui/icons-material";
import { templateApi } from "../../api/client";
import { REPORT_MODULES } from "../../store/builderStore";

interface Tpl { id: string; name: string; description?: string; module?: string; current_published_version_id: string | null; kind?: "report" | "document" | "rule_report"; }
interface Ver { id: string; version_no: number; status: string; semantic_version_ref: number; note?: string; created_at?: string | null; is_current?: boolean; }

export function TemplatesPage() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { data: templates = [] } = useQuery({ queryKey: ["templates"], queryFn: templateApi.list });
  const [newAnchor, setNewAnchor] = useState<HTMLElement | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [renameId, setRenameId] = useState<string | null>(null);
  const [renameVal, setRenameVal] = useState("");
  const [deleteTpl, setDeleteTpl] = useState<Tpl | null>(null);

  const confirmDelete = async () => {
    if (!deleteTpl) return;
    await templateApi.remove(deleteTpl.id);
    setDeleteTpl(null);
    qc.invalidateQueries({ queryKey: ["templates"] });
  };

  const saveName = async (id: string) => {
    if (renameVal.trim()) await templateApi.rename(id, { name: renameVal.trim() });
    setRenameId(null);
    qc.invalidateQueries({ queryKey: ["templates"] });
  };
  const changeModule = async (id: string, module: string) => {
    await templateApi.rename(id, { module });
    qc.invalidateQueries({ queryKey: ["templates"] });
  };
  const { data: versions = [] } = useQuery({
    queryKey: ["versions", openId], queryFn: () => templateApi.versions(openId!), enabled: !!openId,
  });

  const rollback = async (tid: string, vid: string) => {
    await templateApi.rollback(tid, vid);
    qc.invalidateQueries({ queryKey: ["templates"] });
    qc.invalidateQueries({ queryKey: ["versions", tid] });
  };

  // Group by module, ordered by the known module list (unknowns last). Documents
  // are managed on the Documents page, so this report list excludes them.
  const byModule = (templates as Tpl[])
    .filter((t) => t.kind !== "document")
    .reduce<Record<string, Tpl[]>>((acc, t) => {
    const m = t.module || "General";
    (acc[m] ??= []).push(t);
    return acc;
  }, {});
  const order = [...REPORT_MODULES as readonly string[]];
  const groupedModules = Object.entries(byModule).sort(
    (a, b) => (order.indexOf(a[0]) + 1 || 99) - (order.indexOf(b[0]) + 1 || 99),
  );

  return (
    <Box>
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={2.5}>
        <Box>
          <Typography variant="h4">Report Templates</Typography>
          <Typography variant="body2">Design, version and publish reports — no SQL, no developer.</Typography>
        </Box>
        <Button variant="contained" startIcon={<AddCircleOutline />} endIcon={<KeyboardArrowDown />}
          onClick={(e) => setNewAnchor(e.currentTarget)}>
          New Report
        </Button>
        <Menu anchorEl={newAnchor} open={Boolean(newAnchor)} onClose={() => setNewAnchor(null)}
          anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
          transformOrigin={{ vertical: "top", horizontal: "right" }}
          slotProps={{ paper: { sx: { width: 340, mt: 0.5 } } }}>
          <MenuItem onClick={() => { setNewAnchor(null); navigate("/builder"); }} sx={{ py: 1.25, alignItems: "flex-start" }}>
            <ListItemIcon sx={{ mt: 0.25 }}><TableChartOutlined fontSize="small" /></ListItemIcon>
            <ListItemText primary="Visual report"
              secondary="Drop an Excel sheet or pick fields — for tables, filters and totals."
              primaryTypographyProps={{ fontWeight: 600 }} secondaryTypographyProps={{ fontSize: "0.75rem" }} />
          </MenuItem>
          <MenuItem onClick={() => { setNewAnchor(null); navigate("/rule-reports/new"); }} sx={{ py: 1.25, alignItems: "flex-start" }}>
            <ListItemIcon sx={{ mt: 0.25 }}><DataObjectOutlined fontSize="small" /></ListItemIcon>
            <ListItemText primary="Rule report (JSON)"
              secondary="For rule-heavy calculations — day-type logic, thresholds, overtime. Governed spec."
              primaryTypographyProps={{ fontWeight: 600 }} secondaryTypographyProps={{ fontSize: "0.75rem" }} />
          </MenuItem>
        </Menu>
      </Stack>

      {groupedModules.map(([mod, tpls]) => (
        <Box key={mod} sx={{ mb: 2.5 }}>
          <Typography sx={{ fontWeight: 700, fontSize: "0.72rem", textTransform: "uppercase", letterSpacing: 0.6, color: "#6B7280", mb: 0.75 }}>
            {mod} · {tpls.length}
          </Typography>
          <Stack spacing={1.5}>
        {tpls.map((t) => (
          <Card key={t.id}>
            <CardContent sx={{ py: 1.75, "&:last-child": { pb: 1.75 } }}>
              <Stack direction="row" justifyContent="space-between" alignItems="center">
                <Box>
                  {renameId === t.id ? (
                    <Stack direction="row" spacing={1} alignItems="center">
                      <TextField size="small" autoFocus value={renameVal}
                        onChange={(e) => setRenameVal(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && saveName(t.id)} />
                      <IconButton size="small" color="primary" onClick={() => saveName(t.id)}><Check fontSize="small" /></IconButton>
                    </Stack>
                  ) : (
                    <Stack direction="row" spacing={0.5} alignItems="center">
                      <Typography sx={{ fontWeight: 600, fontSize: "0.95rem" }}>{t.name}</Typography>
                      <IconButton size="small" title="Rename"
                        onClick={() => { setRenameId(t.id); setRenameVal(t.name); }}>
                        <DriveFileRenameOutline sx={{ fontSize: 16 }} />
                      </IconButton>
                    </Stack>
                  )}
                  <Typography variant="body2">{t.description || "—"}</Typography>
                </Box>
                <Stack direction="row" spacing={1} alignItems="center">
                  <Select size="small" value={t.module || "General"} variant="standard" disableUnderline
                    onChange={(e) => changeModule(t.id, e.target.value)}
                    sx={{ fontSize: "0.72rem", "& .MuiSelect-select": { py: 0.25 } }} title="Module">
                    {REPORT_MODULES.map((m) => <MenuItem key={m} value={m}>{m}</MenuItem>)}
                  </Select>
                  <Chip
                    size="small"
                    label={t.current_published_version_id ? "Published" : "Draft only"}
                    color={t.current_published_version_id ? "primary" : "default"}
                  />
                  <Button size="small" startIcon={<Edit />}
                    onClick={() => navigate(t.kind === "rule_report" ? `/rule-reports/${t.id}` : `/builder/${t.id}`)}>Edit</Button>
                  <Tooltip title={t.current_published_version_id ? "Run this report" : "Publish a version first — drafts can be previewed in the Builder"}>
                    <span>
                      <Button size="small" startIcon={<PlayArrow />} disabled={!t.current_published_version_id}
                        onClick={() => navigate(`/viewer/r/${t.id}`)}>Run</Button>
                    </span>
                  </Tooltip>
                  <Button size="small" color="error" startIcon={<DeleteOutline />} onClick={() => setDeleteTpl(t)}>Delete</Button>
                  <IconButton size="small" onClick={() => setOpenId(openId === t.id ? null : t.id)}>
                    {openId === t.id ? <ExpandLess /> : <ExpandMore />}
                  </IconButton>
                </Stack>
              </Stack>

              <Collapse in={openId === t.id} unmountOnExit>
                <Table size="small" sx={{ mt: 1.5 }}>
                  <TableHead>
                    <TableRow>
                      <TableCell>Version</TableCell><TableCell>What changed</TableCell>
                      <TableCell>When</TableCell><TableCell align="right">Actions</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {(versions as Ver[]).map((v) => (
                      <TableRow key={v.id}>
                        <TableCell sx={{ whiteSpace: "nowrap" }}>
                          v{v.version_no}
                          {v.is_current && <Chip size="small" label="current" color="primary" sx={{ ml: 1, height: 20 }} />}
                        </TableCell>
                        <TableCell sx={{ color: v.note ? "inherit" : "#9CA3AF" }}>{v.note || "—"}</TableCell>
                        <TableCell sx={{ whiteSpace: "nowrap", fontSize: "0.8rem", color: "#6B7280" }}>
                          {v.created_at ? new Date(v.created_at).toLocaleString() : "—"}
                        </TableCell>
                        <TableCell align="right">
                          {!v.is_current && <Button size="small" onClick={() => rollback(t.id, v.id)}>Make current</Button>}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Collapse>
            </CardContent>
          </Card>
        ))}
          </Stack>
        </Box>
      ))}
      {!templates.length && (
        <Card><CardContent><Typography variant="body2">No templates yet — click “New Report”.</Typography></CardContent></Card>
      )}

      <Dialog open={Boolean(deleteTpl)} onClose={() => setDeleteTpl(null)} maxWidth="xs" fullWidth>
        <DialogTitle>Delete report?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Permanently delete <b>{deleteTpl?.name}</b> and all its versions. This can’t be undone,
            and it will be removed from the Viewer.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteTpl(null)}>Cancel</Button>
          <Button color="error" variant="contained" onClick={confirmDelete}>Delete</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
