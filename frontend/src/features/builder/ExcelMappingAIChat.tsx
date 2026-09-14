// AI helper for the "unmapped columns" case in ExcelUpload's mapping review —
// same technique + visual layout as RuleReportAIChat (session-based chat with
// Claude Code, "Use this →" applies the result), trimmed: no attachments (the
// sheet is already uploaded), no session resume (fresh per upload), and the
// AI is only ever given the currently-unmapped headers — it can't touch an
// already-mapped column.
import { useEffect, useRef, useState } from "react";
import { Alert, Box, Button, CircularProgress, IconButton, Stack, TextField, Typography } from "@mui/material";
import { AutoAwesome, SendOutlined, SmartToyOutlined } from "@mui/icons-material";
import { excelMappingChatApi, type ExcelMappingChatMessage } from "../../api/client";

interface Props {
  unmappedHeaders: string[];
  currentMapping: Record<string, string | null>;
  onApply: (patch: Record<string, string | null>) => void;
}

export default function ExcelMappingAIChat({ unmappedHeaders, currentMapping, onApply }: Props) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ExcelMappingChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  const send = async () => {
    const text = input.trim();
    if (!text) return;
    setErr("");
    setBusy(true);
    setMessages((m) => [...m, { role: "you", text }]);
    setInput("");
    try {
      let sid = sessionId;
      if (!sid) {
        const s = await excelMappingChatApi.createSession(text.slice(0, 80) || "Finish mapping");
        sid = s.id;
        setSessionId(sid);
      }
      const r = await excelMappingChatApi.sendMessage(sid, text, unmappedHeaders, currentMapping);
      setMessages((m) => [...m, { role: "assistant", text: r.reply, mappings: r.mappings }]);
    } catch (e) {
      setErr((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? "Couldn't reach the AI helper — try again.");
      setMessages((m) => m.slice(0, -1));
      setInput(text);
    } finally {
      setBusy(false);
    }
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void send(); }
  };

  const useMappings = (mappings: ExcelMappingChatMessage["mappings"]) => {
    if (!mappings?.length) return;
    onApply(Object.fromEntries(mappings.map((m) => [m.header, m.ref])));
  };

  return (
    <Box sx={{ mt: 1, mb: 1.5, border: "1px solid #E5E7EB", borderRadius: 2, bgcolor: "#FAFDFE" }}>
      <Stack direction="row" spacing={1} alignItems="center" sx={{ px: 1.5, py: 1, borderBottom: messages.length ? "1px solid #E5E7EB" : "none" }}>
        <AutoAwesome sx={{ fontSize: 18, color: "#007499" }} />
        <Typography variant="body2" sx={{ fontWeight: 600 }}>Chat with AI to finish mapping</Typography>
      </Stack>

      {messages.length > 0 && (
        <Box sx={{ maxHeight: 280, overflowY: "auto", px: 1.5, py: 1 }}>
          <Stack spacing={1.25}>
            {messages.map((m, i) => (
              <Stack key={i} direction="row" spacing={1} justifyContent={m.role === "you" ? "flex-end" : "flex-start"}>
                {m.role === "assistant" && (
                  <SmartToyOutlined fontSize="small" sx={{ color: "#007499", mt: 0.5 }} />
                )}
                <Box sx={{
                  maxWidth: "80%", px: 1.5, py: 1, borderRadius: 2,
                  bgcolor: m.role === "you" ? "#007499" : "#F1F5F9",
                  color: m.role === "you" ? "#fff" : "inherit",
                }}>
                  <Typography variant="body2" sx={{ whiteSpace: "pre-wrap", fontSize: "0.86rem", color: "inherit" }}>
                    {m.text}
                  </Typography>
                  {!!m.mappings?.length && (
                    <Button size="small" variant="contained" startIcon={<AutoAwesome />}
                      onClick={() => useMappings(m.mappings)}
                      sx={{ mt: 1, textTransform: "none", bgcolor: "#00617A", "&:hover": { bgcolor: "#004E63" } }}>
                      Use these mappings ({m.mappings.length}) →
                    </Button>
                  )}
                </Box>
              </Stack>
            ))}
            {busy && (
              <Stack direction="row" spacing={1} alignItems="center">
                <SmartToyOutlined fontSize="small" sx={{ color: "#007499" }} />
                <CircularProgress size={16} />
                <Typography variant="caption" color="text.secondary">Thinking…</Typography>
              </Stack>
            )}
            <div ref={bottomRef} />
          </Stack>
        </Box>
      )}

      {err && <Alert severity="error" sx={{ mx: 1.5, mb: 1 }}>{err}</Alert>}

      {/* Same rounded "pill" input as RuleReportAIChat — send icon inside the
          same border as the text, ChatGPT-style. No attach icon here (nothing
          to attach — the sheet's already uploaded). */}
      <Box sx={{ p: 1.5 }}>
        <Box sx={{
          display: "flex", alignItems: "flex-end", gap: 0.25,
          border: "1px solid #D0D7DE", borderRadius: "24px",
          bgcolor: "#fff", pl: 1.25, pr: 0.5, py: 0.5,
          "&:focus-within": { borderColor: "#007499" },
        }}>
          <TextField fullWidth multiline minRows={1} maxRows={6} size="small" variant="standard"
            placeholder="Ask about the columns that didn't map…"
            value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={onKeyDown} disabled={busy}
            slotProps={{ input: { disableUnderline: true } }}
            sx={{ flex: 1, py: 0.5 }} />
          <IconButton color="primary" size="small" onClick={() => void send()} disabled={busy || !input.trim()}>
            <SendOutlined fontSize="small" />
          </IconButton>
        </Box>
      </Box>
    </Box>
  );
}
