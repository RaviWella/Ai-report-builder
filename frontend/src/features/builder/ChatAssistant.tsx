// Chat assistant (FR-A3/A4) — NL request -> data_spec, adjustment chat. Equal,
// interleavable input mode with ExcelUpload; both refine the same spec.
import { useState } from "react";
import { Box, IconButton, Stack, TextField, Typography } from "@mui/material";
import { Send } from "@mui/icons-material";
import { aiApi } from "../../api/client";
import { useBuilderStore } from "../../store/builderStore";

export function ChatAssistant() {
  const { dataSpec, setDataSpec } = useBuilderStore();
  const [input, setInput] = useState("");
  const [log, setLog] = useState<{ role: string; text: string }[]>([]);
  const [busy, setBusy] = useState(false);
  const hasSpec = dataSpec.fields.length > 0 || dataSpec.aggregations.length > 0;

  const send = async () => {
    if (!input.trim()) return;
    setBusy(true);
    setLog((l) => [...l, { role: "you", text: input }]);
    try {
      const res = hasSpec ? await aiApi.adjust(input, dataSpec) : await aiApi.naturalLanguage(input);
      setDataSpec(res.data_spec);
      setLog((l) => [...l, { role: "assistant", text: res.rationale }]);
      setInput("");
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setLog((l) => [...l, { role: "error", text: msg ?? "AI request failed (set an API key in AI Settings)" }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Box sx={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <Typography variant="h6" sx={{ mb: 1 }}>AI Assistant</Typography>
      <Box sx={{ flex: 1, overflowY: "auto", minHeight: 120, mb: 1 }}>
        {log.length === 0 && <Typography variant="body2">Describe the report in plain language, or refine the current one.</Typography>}
        <Stack spacing={1}>
          {log.map((m, i) => (
            <Box key={i} sx={{
              alignSelf: m.role === "you" ? "flex-end" : "flex-start",
              bgcolor: m.role === "you" ? "#007499" : m.role === "error" ? "#FFF0ED" : "#F3F4F6",
              color: m.role === "you" ? "#fff" : m.role === "error" ? "#C13515" : "#1A1A1A",
              px: 1.25, py: 0.75, borderRadius: 2, maxWidth: "85%", fontSize: "0.8rem",
            }}>
              {m.text}
            </Box>
          ))}
        </Stack>
      </Box>
      <Stack direction="row" spacing={1}>
        <TextField size="small" fullWidth value={input} onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder={hasSpec ? "Refine: e.g. group by department" : "Describe the report…"} />
        <IconButton color="primary" onClick={send} disabled={busy}><Send /></IconButton>
      </Stack>
    </Box>
  );
}
