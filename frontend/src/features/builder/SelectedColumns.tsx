// Selected columns panel — the report's chosen columns, in order. Makes it
// obvious what was added (via field chips, AI, or Excel confirm) and lets the
// user remove / reorder before previewing.
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Box, Button, Chip, Collapse, Stack, Typography, IconButton, TextField, Tooltip,
  Dialog, DialogTitle, DialogContent, DialogActions, CircularProgress,
} from "@mui/material";
import {
  Close, ArrowUpward, ArrowDownward, Functions, DragIndicator, ExpandLess, ExpandMore,
  TableChartOutlined, VisibilityOutlined, DataObject, ContentCopyOutlined, Check,
} from "@mui/icons-material";
import { authApi, semanticApi, templateApi, type Me } from "../../api/client";
import { isSupportAdmin } from "../../auth/roles";
import { useBuilderStore } from "../../store/builderStore";
import { CustomColumnDialog } from "./CustomColumnDialog";
import { formatCalcSummary } from "./calcFieldUtils";
import type { CalculatedField, SemanticFieldMeta } from "../../types/spec";

// Name hints for a summable (amount/quantity) column — used so the totals toggle
// still shows when the catalogue mis-typed an amount as a dimension.
export const AMOUNT_HINT =
  /amount|salary|total|cost|pay|wage|deduction|bonus|allowance|hours|minutes|days|count|qty|rate|net|gross|basic|epf|etf|tax|loan|advance|charge|overtime|\bot\b|balance/i;

export function SelectedColumns() {
  const { dataSpec, presentation, removeField, reorderFields, setFieldLabel, setFieldTotal, templateId } = useBuilderStore();
  const { data: allFields = [] } = useQuery({ queryKey: ["fields"], queryFn: semanticApi.fields });
  const fields = dataSpec.fields;
  const calcs = dataSpec.calculated_fields;
  const [showMap, setShowMap] = useState(false);
  const mapped = fields.filter((f) => f.source_header);  // columns that came from an Excel upload

  // Admin-only "View JSON" debug affordance — lets a tech lead inspect/copy the
  // exact spec being built without a DB/Network-tab detour.
  const [me, setMe] = useState<Me | null>(null);
  useEffect(() => { authApi.me().then(setMe).catch(() => {}); }, []);
  const [jsonOpen, setJsonOpen] = useState(false);
  const [jsonCopied, setJsonCopied] = useState(false);
  const specJson = JSON.stringify({ data_spec: dataSpec, presentation_spec: presentation }, null, 2);
  const copySpecJson = () => {
    navigator.clipboard?.writeText(specJson).then(() => {
      setJsonCopied(true);
      setTimeout(() => setJsonCopied(false), 1500);
    }).catch(() => {});
  };

  // The uploaded sheet is stored (encrypted) with the template, so on edit we can
  // preview the exact rows without re-uploading. Parsed IN THE BROWSER.
  const [hasFile, setHasFile] = useState(false);
  const [pvOpen, setPvOpen] = useState(false);
  const [pvBusy, setPvBusy] = useState(false);
  const [pvErr, setPvErr] = useState("");
  const [preview, setPreview] = useState<{ headers: string[]; rows: string[][] } | null>(null);

  useEffect(() => {
    if (!templateId || mapped.length === 0) { setHasFile(false); return; }
    templateApi.sourceFileMeta(templateId)
      .then((m) => setHasFile(Boolean(m.exists)))
      .catch(() => setHasFile(false));
  }, [templateId, mapped.length]);

  const openPreview = async () => {
    setPvOpen(true);
    if (preview || !templateId) return;
    setPvBusy(true); setPvErr("");
    try {
      const blob = await templateApi.sourceFile(templateId);
      const XLSX = await import("xlsx"); // lazy — only when previewing
      const buf = await blob.arrayBuffer();
      const wb = XLSX.read(buf, { sheetRows: 51 });
      const ws = wb.Sheets[wb.SheetNames[0]];
      const grid = XLSX.utils.sheet_to_json<string[]>(ws, { header: 1, blankrows: false, defval: "" });
      const headers = (grid[0] ?? []).map((h) => String(h ?? ""));
      const rows = grid.slice(1, 51).map((r) => headers.map((_, i) => String(r[i] ?? "")));
      setPreview({ headers, rows });
    } catch {
      setPvErr("Couldn’t load the stored file (only .xlsx/.xls/.csv can be previewed).");
    } finally {
      setPvBusy(false);
    }
  };
  // A field can carry a column total (SUM at the bottom) when it's numeric OR its
  // name reads like an amount/quantity — so an "Amount"/"Total Cost" column still
  // offers the total even if the catalogue mis-typed it as a dimension.
  const isNumeric = (ref: string) => {
    const m = (allFields as SemanticFieldMeta[]).find((f) => f.ref === ref);
    if (m && (m.role === "measure" || m.type === "integer" || m.type === "decimal")) return true;
    return AMOUNT_HINT.test(`${ref} ${m?.label ?? ""}`);
  };
  const [dialog, setDialog] = useState(false);
  const [editCalc, setEditCalc] = useState<CalculatedField | null>(null);
  const calcForRef = (ref: string) => calcs.find((c) => `calc.${c.name}` === ref);
  const refLabel = (ref: string) =>
    (allFields as SemanticFieldMeta[]).find((f) => f.ref === ref)?.label ?? ref.split(".").pop() ?? ref;
  const openDialog = (calc?: CalculatedField | null) => { setEditCalc(calc ?? null); setDialog(true); };
  const closeDialog = () => { setEditCalc(null); setDialog(false); };

  const move = (from: number, to: number) => {
    if (to < 0 || to >= fields.length || from === to) return;
    const order = fields.map((f) => f.ref);
    const [moved] = order.splice(from, 1);
    order.splice(to, 0, moved);
    reorderFields(order);
  };
  // Drag-and-drop reordering — place any column anywhere (incl. between mapped ones).
  const [dragI, setDragI] = useState<number | null>(null);
  const drop = (to: number) => { if (dragI !== null) move(dragI, to); setDragI(null); };

  return (
    <Box>
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={1}>
        <Typography variant="h6">Selected Columns</Typography>
        <Stack direction="row" spacing={1} alignItems="center">
          <Typography variant="caption">{fields.length} column{fields.length === 1 ? "" : "s"}</Typography>
          <Button size="small" startIcon={<Functions />} onClick={() => openDialog()}>Custom column</Button>
        </Stack>
      </Stack>
      <CustomColumnDialog open={dialog} onClose={closeDialog} initialCalc={editCalc} />

      <Dialog open={pvOpen} onClose={() => setPvOpen(false)} maxWidth="lg" fullWidth>
        <DialogTitle sx={{ fontSize: "1rem" }}>Uploaded sheet — first 50 rows</DialogTitle>
        <DialogContent dividers>
          {pvBusy && <Stack alignItems="center" py={3}><CircularProgress size={26} /></Stack>}
          {pvErr && <Typography color="error" variant="body2">{pvErr}</Typography>}
          {preview && !pvBusy && (
            <Box sx={{ overflow: "auto", maxHeight: "62vh" }}>
              <table style={{ borderCollapse: "collapse", fontSize: "0.78rem", width: "100%" }}>
                <thead>
                  <tr>
                    {preview.headers.map((h, i) => (
                      <th key={i} style={{ position: "sticky", top: 0, background: "#F3F4F6", border: "1px solid #E5E7EB", padding: "4px 8px", textAlign: "left", whiteSpace: "nowrap", fontWeight: 600 }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.rows.map((r, ri) => (
                    <tr key={ri}>
                      {r.map((c, ci) => (
                        <td key={ci} style={{ border: "1px solid #EEF0F2", padding: "3px 8px", whiteSpace: "nowrap" }}>{c}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </Box>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={jsonOpen} onClose={() => setJsonOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Report JSON (admin)</DialogTitle>
        <DialogContent>
          <Box sx={{ position: "relative" }}>
            <Tooltip title={jsonCopied ? "Copied" : "Copy JSON"}>
              <IconButton size="small" onClick={copySpecJson}
                sx={{ position: "absolute", top: 6, right: 6, zIndex: 1, bgcolor: "#fff",
                      border: "1px solid #E2E8F0", "&:hover": { bgcolor: "#EAF4F7" } }}>
                {jsonCopied ? <Check fontSize="small" color="success" /> : <ContentCopyOutlined fontSize="small" />}
              </IconButton>
            </Tooltip>
            <Box component="pre" sx={{
              m: 0, p: 1.5, maxHeight: 480, overflow: "auto", fontSize: 12,
              bgcolor: "#F8FAFC", border: "1px solid #E2E8F0", borderRadius: 1,
            }}>
              {specJson}
            </Box>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setJsonOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>

      {/* How the columns were mapped from the uploaded Excel — collapsible, so you
          can check the mapping later when editing the template. */}
      {mapped.length > 0 && (
        <Box sx={{ mb: 1 }}>
          <Stack direction="row" spacing={0.5} alignItems="center">
            <Button size="small" startIcon={<TableChartOutlined />} endIcon={showMap ? <ExpandLess /> : <ExpandMore />}
              onClick={() => setShowMap((v) => !v)} sx={{ textTransform: "none" }}>
              Excel mapping ({mapped.length})
            </Button>
            {hasFile && (
              <Button size="small" startIcon={<VisibilityOutlined />} onClick={openPreview} sx={{ textTransform: "none" }}>
                View uploaded file
              </Button>
            )}
            {isSupportAdmin(me) && (
              <Tooltip title="View JSON (admin)">
                <Button size="small" startIcon={<DataObject />} onClick={() => setJsonOpen(true)} sx={{ textTransform: "none" }}>
                  View JSON
                </Button>
              </Tooltip>
            )}
          </Stack>
          <Collapse in={showMap} unmountOnExit>
            <Box sx={{ mt: 0.5, p: 1.25, borderRadius: 1.5, bgcolor: "#F9FAFB", border: "1px solid #E5E7EB" }}>
              <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 0.75 }}>
                How each column was mapped from your uploaded sheet.{" "}
                {hasFile
                  ? "Your sheet is stored (encrypted) — use “View uploaded file” to preview the exact rows."
                  : "The file will be stored (encrypted) once you save, so you can preview it on edit."}
              </Typography>
              <Stack spacing={0.25}>
                {mapped.map((f) => (
                  <Typography key={f.ref} variant="caption" sx={{ display: "block", fontFamily: "ui-monospace, monospace", fontSize: "0.72rem" }}>
                    <b style={{ color: "#374151" }}>{f.source_header}</b>
                    <span style={{ color: "#9CA3AF" }}> → </span>
                    {f.label || f.ref.split(".").pop()}
                  </Typography>
                ))}
              </Stack>
            </Box>
          </Collapse>
        </Box>
      )}
      {fields.length === 0 ? (
        <Typography variant="body2">
          None yet — pick fields on the left, ask the AI, or confirm an Excel mapping.
        </Typography>
      ) : (
        <>
        <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5, display: "block" }}>
          Drag <DragIndicator sx={{ fontSize: 13, verticalAlign: "middle" }} /> to reorder · edit a heading by typing.
        </Typography>
        <Stack spacing={0.75}>
          {fields.map((f, i) => {
            const calc = calcForRef(f.ref);
            return (
            <Box key={f.ref}>
            <Stack direction="row" alignItems="center" spacing={1}
              onDragOver={(e) => e.preventDefault()} onDrop={() => drop(i)}
              sx={{ borderRadius: 1, bgcolor: dragI === i ? "#EAF4F7" : "transparent" }}>
              <Box draggable onDragStart={() => setDragI(i)} onDragEnd={() => setDragI(null)}
                sx={{ display: "flex", alignItems: "center", cursor: "grab", color: "#C4CAD2", "&:active": { cursor: "grabbing" } }}
                title="Drag to reorder">
                <DragIndicator fontSize="small" />
              </Box>
              <Typography variant="caption" sx={{ width: 18, color: "text.secondary", cursor: "default" }} title={f.ref}>{i + 1}.</Typography>
              {calc && (
                <Chip size="small" label="Custom"
                  sx={{ height: 20, fontSize: "0.62rem", bgcolor: "#EEF2FF", color: "#4338CA", flexShrink: 0 }} />
              )}
              <TextField
                size="small" variant="outlined" value={f.label ?? ""}
                onChange={(e) => setFieldLabel(f.ref, e.target.value)}
                placeholder={f.ref.split(".").pop()}
                sx={{ flex: 1, "& .MuiInputBase-input": { py: 0.5, fontSize: "0.82rem" } }}
              />
              {calc && (
                <Tooltip title="View or edit this column’s formula / rules">
                  <Button size="small" sx={{ textTransform: "none", fontSize: "0.72rem", flexShrink: 0, minWidth: 0, px: 1 }}
                    onClick={() => openDialog(calc)}>
                    View rules
                  </Button>
                </Tooltip>
              )}
              {isNumeric(f.ref) && (
                <Tooltip title={f.total ? "Column total shown at the bottom — click to remove" : "Show a total (sum) of this column at the bottom of the report"}>
                  <Chip size="small" icon={<Functions />} label="Total" clickable
                    onClick={() => setFieldTotal(f.ref, !f.total)}
                    color={f.total ? "primary" : "default"} variant={f.total ? "filled" : "outlined"}
                    sx={{ height: 24, flexShrink: 0 }} />
                </Tooltip>
              )}
              <IconButton size="small" disabled={i === 0} onClick={() => move(i, i - 1)} title="Move up">
                <ArrowUpward fontSize="inherit" />
              </IconButton>
              <IconButton size="small" disabled={i === fields.length - 1} onClick={() => move(i, i + 1)} title="Move down">
                <ArrowDownward fontSize="inherit" />
              </IconButton>
              <IconButton size="small" onClick={() => removeField(f.ref)} title="Remove">
                <Close fontSize="inherit" />
              </IconButton>
            </Stack>
            {calc && (
              <Typography variant="caption" color="text.secondary"
                sx={{ display: "block", pl: 5.5, mt: 0.25, fontSize: "0.7rem", lineHeight: 1.35 }}>
                {formatCalcSummary(calc, refLabel)}
              </Typography>
            )}
            </Box>
            );
          })}
        </Stack>
        </>
      )}
    </Box>
  );
}
