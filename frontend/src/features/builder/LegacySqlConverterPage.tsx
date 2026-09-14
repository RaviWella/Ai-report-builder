// Legacy SQL Converter — a standalone migration helper. Paste an old report's
// SQL (from the client's previous MySQL-source system), get back a plain-
// language business-logic document with every legacy table/column/code
// resolved against THIS tenant's new datamart. Copy that document into the
// Rule Report Builder's "AI helper" chat as the requirement — this page has
// no connection to the DSL engine or the chat's JSON output itself.
import { useRef, useState } from "react";
import {
  Alert, Box, Button, Card, CircularProgress, IconButton, Stack, TextField, Tooltip, Typography,
} from "@mui/material";
import { AutoAwesome, Check, ContentCopyOutlined, UploadFileOutlined } from "@mui/icons-material";
import { legacySqlConverterApi } from "../../api/client";

export function LegacySqlConverterPage() {
  const [sql, setSql] = useState("");
  const [document, setDocument] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [copied, setCopied] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const analyze = async () => {
    if (!sql.trim()) return;
    setErr("");
    setBusy(true);
    setDocument("");
    try {
      const doc = await legacySqlConverterApi.analyze(sql);
      setDocument(doc);
    } catch (e) {
      setErr((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? "Couldn't analyze this SQL — try again.");
    } finally {
      setBusy(false);
    }
  };

  const copyDocument = () => {
    navigator.clipboard?.writeText(document).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }).catch(() => {});
  };

  return (
    <Box sx={{ maxWidth: 1100, mx: "auto", pt: 3, pb: 5, px: { xs: 1, md: 2 } }}>
      <Typography variant="h4" sx={{ mb: 0.75 }}>Legacy SQL Converter</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Paste an old report's SQL (from the client's previous system). This maps its tables,
        columns, and legacy codes onto this tenant's real datamart and writes a plain-language
        business-logic document — copy that into the Rule Report Builder's "AI helper" chat as
        the requirement, the same way you'd paste any client requirement.
      </Typography>

      <Card variant="outlined" sx={{ p: 2, mb: 2.5 }}>
        <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
          <Typography variant="subtitle2">Legacy SQL</Typography>
          <input ref={fileInputRef} type="file" accept=".sql,.txt" hidden
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) f.text().then(setSql);
              e.target.value = "";
            }} />
          <Button size="small" variant="text" startIcon={<UploadFileOutlined />}
            onClick={() => fileInputRef.current?.click()} sx={{ textTransform: "none" }}>
            or upload a .sql file
          </Button>
        </Stack>
        <TextField fullWidth multiline minRows={10} maxRows={24}
          placeholder="SELECT ..."
          value={sql} onChange={(e) => setSql(e.target.value)} disabled={busy}
          slotProps={{ input: { sx: { fontFamily: "ui-monospace, monospace", fontSize: "0.82rem" } } }} />
        <Stack direction="row" justifyContent="flex-end" sx={{ mt: 1.5 }}>
          <Button variant="contained" startIcon={busy ? <CircularProgress size={16} color="inherit" /> : <AutoAwesome />}
            disabled={busy || !sql.trim()} onClick={() => void analyze()}>
            {busy ? "Analyzing…" : "Analyze"}
          </Button>
        </Stack>
      </Card>

      {err && <Alert severity="error" sx={{ mb: 2.5 }}>{err}</Alert>}

      {document && (
        <Card variant="outlined" sx={{ p: 2 }}>
          <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
            <Typography variant="subtitle2">Business logic document</Typography>
            <Tooltip title={copied ? "Copied" : "Copy"}>
              <IconButton size="small" onClick={copyDocument}>
                {copied ? <Check fontSize="small" color="success" /> : <ContentCopyOutlined fontSize="small" />}
              </IconButton>
            </Tooltip>
          </Stack>
          <Box sx={{
            whiteSpace: "pre-wrap", fontSize: "0.86rem", lineHeight: 1.6,
            bgcolor: "#F8FAFC", borderRadius: 1.5, p: 2, maxHeight: 600, overflowY: "auto",
          }}>
            {document}
          </Box>
        </Card>
      )}
    </Box>
  );
}
