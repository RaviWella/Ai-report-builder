// AI helper for the Rule Report builder — upload a requirement doc + sample
// sheet, then chat with Claude Code to iterate to a validated RuleReportSpec
// JSON. "Use this spec →" writes straight into the same `json` state the
// "JSON logic" tab edits — the only point of contact with the rest of the
// builder, so nothing else needs to change.
import { useEffect, useRef, useState } from "react";
import {
  Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent,
  DialogTitle, IconButton, ListItemIcon, ListItemText, Menu, MenuItem, Stack, TextField, Tooltip, Typography,
} from "@mui/material";
import {
  AttachFileOutlined, AutoAwesome, Close, CodeOutlined, DescriptionOutlined,
  GridOnOutlined, SendOutlined, SmartToyOutlined,
} from "@mui/icons-material";
import { ruleChatApi, type RuleChatAttachment, type RuleChatMessage } from "../../api/client";

function _attachmentIcon(kind: RuleChatAttachment["kind"]) {
  if (kind === "requirement_doc") return <DescriptionOutlined />;
  if (kind === "sample_sheet") return <GridOnOutlined />;
  return <CodeOutlined />;
}

interface Props {
  // Passed the full assistant message (spec + any row_number_column/subtotal/
  // totals/pivot the AI proposed alongside it) — not just spec — so the
  // builder can carry the whole thing into its JSON editor unchanged.
  onUseSpec: (msg: RuleChatMessage) => void;
  // Resuming an existing report's conversation (RuleReportBuilder already
  // fetched it via templateApi.getRuleReportChatSession) — seeded on mount,
  // no fetch in here, so there's only ever one place that does the
  // tenant-wide (not creator-only) lookup.
  initialSessionId?: string | null;
  initialMessages?: RuleChatMessage[];
  // Fires whenever this chat's own session id changes (seeded from the
  // above, or newly created on first send) — so the parent always knows
  // which session is active, to record on save.
  onSessionChange?: (id: string) => void;
}

export default function RuleReportAIChat({
  onUseSpec, initialSessionId, initialMessages, onSessionChange,
}: Props) {
  const [sessionId, setSessionId] = useState<string | null>(initialSessionId ?? null);
  const [messages, setMessages] = useState<RuleChatMessage[]>(initialMessages ?? []);
  const [input, setInput] = useState("");
  const [reqDoc, setReqDoc] = useState<File | null>(null);
  const [sheet, setSheet] = useState<File | null>(null);
  const [sourceSql, setSourceSql] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [attachAnchor, setAttachAnchor] = useState<HTMLElement | null>(null);
  const [sqlDialogOpen, setSqlDialogOpen] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const reqDocInputRef = useRef<HTMLInputElement>(null);
  const sheetInputRef = useRef<HTMLInputElement>(null);

  // initialSessionId/initialMessages arrive asynchronously (RuleReportBuilder's
  // own getDraft + getRuleReportChatSession calls resolve after this component
  // has already mounted with nothing) — seed state once they show up, but
  // never clobber a conversation already in progress.
  useEffect(() => {
    if (initialSessionId && messages.length === 0) {
      setSessionId(initialSessionId);
      setMessages(initialMessages ?? []);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialSessionId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  const send = async () => {
    const text = input.trim();
    if (!text && !reqDoc && !sheet && !sourceSql) return;
    setErr("");
    setBusy(true);
    const outgoing: RuleChatMessage = {
      role: "you", text,
      attachments: [
        ...(reqDoc ? [{ kind: "requirement_doc" as const, filename: reqDoc.name }] : []),
        ...(sheet ? [{ kind: "sample_sheet" as const, filename: sheet.name }] : []),
        ...(sourceSql ? [{ kind: "source_sql" as const, filename: sourceSql.name }] : []),
      ],
    };
    setMessages((m) => [...m, outgoing]);
    setInput("");
    const thisReqDoc = reqDoc, thisSheet = sheet, thisSourceSql = sourceSql;
    setReqDoc(null); setSheet(null); setSourceSql(null);
    try {
      let sid = sessionId;
      if (!sid) {
        const s = await ruleChatApi.createSession(text.slice(0, 80) || "New report");
        sid = s.id;
        setSessionId(sid);
        onSessionChange?.(sid);
      }
      const r = await ruleChatApi.sendMessage(sid, text, {
        requirementDoc: thisReqDoc, sampleSheet: thisSheet, sourceSql: thisSourceSql,
      });
      setMessages((m) => [...m, {
        role: "assistant", text: r.reply, spec: r.spec,
        row_number_column: r.row_number_column, subtotal: r.subtotal,
        totals: r.totals, pivot: r.pivot,
      }]);
    } catch (e) {
      setErr((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? "Couldn't reach the AI helper — try again.");
      setMessages((m) => m.slice(0, -1));
      setInput(text);
      setReqDoc(thisReqDoc); setSheet(thisSheet); setSourceSql(thisSourceSql);
    } finally {
      setBusy(false);
    }
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void send(); }
  };

  return (
    <Box sx={{ display: "flex", flexDirection: "column", height: 660 }}>
      {messages.length === 0 && (
        <Box sx={{ p: 2, textAlign: "center", color: "text.secondary" }}>
          <AutoAwesome sx={{ fontSize: 32, color: "#007499", mb: 1 }} />
          <Typography variant="body2" sx={{ maxWidth: 480, mx: "auto" }}>
            Attach the client's written requirement (a screenshot or PDF), a sample output
            sheet, and — if this replaces an existing report — the old source SQL, then
            describe the report. The AI will map the old logic onto this tenant's actual
            datamart columns and ask when something isn't there.
          </Typography>
        </Box>
      )}

      <Box sx={{ flex: 1, overflowY: "auto", px: 1.5, py: 1 }}>
        <Stack spacing={1.5}>
          {messages.map((m, i) => (
            <Stack key={i} direction="row" spacing={1} justifyContent={m.role === "you" ? "flex-end" : "flex-start"}>
              {m.role === "assistant" && (
                <SmartToyOutlined fontSize="small" sx={{ color: "#007499", mt: 0.5 }} />
              )}
              <Box sx={{
                maxWidth: "78%", px: 1.5, py: 1, borderRadius: 2,
                bgcolor: m.role === "you" ? "#007499" : "#F1F5F9",
                color: m.role === "you" ? "#fff" : "inherit",
              }}>
                {!!m.attachments?.length && (
                  <Stack direction="row" spacing={0.5} sx={{ mb: 0.5, flexWrap: "wrap" }}>
                    {m.attachments.map((a, j) => (
                      <Chip key={j} size="small" variant="outlined"
                        icon={_attachmentIcon(a.kind)}
                        label={a.filename}
                        sx={{ bgcolor: "rgba(255,255,255,0.15)", color: "inherit" }} />
                    ))}
                  </Stack>
                )}
                <Typography variant="body2" sx={{ whiteSpace: "pre-wrap", fontSize: "0.86rem", color: "inherit" }}>
                  {m.text}
                </Typography>
                {m.spec != null && (
                  <Button size="small" variant="contained" startIcon={<AutoAwesome />}
                    onClick={() => onUseSpec(m)}
                    sx={{ mt: 1, textTransform: "none", bgcolor: "#00617A", "&:hover": { bgcolor: "#004E63" } }}>
                    Use this spec →
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

      {err && <Alert severity="error" sx={{ mx: 1.5, mb: 1 }}>{err}</Alert>}

      <Box sx={{ borderTop: "1px solid #E5E7EB", p: 1.5 }}>
        {!!(reqDoc || sheet || sourceSql) && (
          <Stack direction="row" spacing={1} sx={{ mb: 1, flexWrap: "wrap" }}>
            {reqDoc && (
              <Chip size="small" icon={<DescriptionOutlined fontSize="small" />} label={reqDoc.name}
                color="primary" onDelete={() => setReqDoc(null)} deleteIcon={<Close fontSize="small" />} />
            )}
            {sheet && (
              <Chip size="small" icon={<GridOnOutlined fontSize="small" />} label={sheet.name}
                color="primary" onDelete={() => setSheet(null)} deleteIcon={<Close fontSize="small" />} />
            )}
            {sourceSql && (
              <Chip size="small" icon={<CodeOutlined fontSize="small" />} label={sourceSql.name}
                color="primary" onDelete={() => setSourceSql(null)} deleteIcon={<Close fontSize="small" />} />
            )}
          </Stack>
        )}
        <input ref={reqDocInputRef} type="file" accept="image/*,application/pdf" hidden
          onChange={(e) => { const f = e.target.files?.[0]; if (f) setReqDoc(f); e.target.value = ""; }} />
        <input ref={sheetInputRef} type="file" accept=".xlsx,.xls,.xlsb,.csv" hidden
          onChange={(e) => { const f = e.target.files?.[0]; if (f) setSheet(f); e.target.value = ""; }} />
        {/* One rounded "pill" container, ChatGPT-style — the attach + send
            icons live INSIDE the same border as the text input, not as
            separate boxes beside it. */}
        <Box sx={{
          display: "flex", alignItems: "flex-end", gap: 0.25,
          border: "1px solid #D0D7DE", borderRadius: "24px",
          bgcolor: "#fff", pl: 0.5, pr: 0.5, py: 0.5,
          "&:focus-within": { borderColor: "#007499" },
        }}>
          <Tooltip title="Attach requirement doc, sample sheet, or source SQL">
            <IconButton size="small" onClick={(e) => setAttachAnchor(e.currentTarget)} disabled={busy}>
              <AttachFileOutlined fontSize="small" />
            </IconButton>
          </Tooltip>
          <Menu anchorEl={attachAnchor} open={!!attachAnchor} onClose={() => setAttachAnchor(null)}>
            <MenuItem onClick={() => { reqDocInputRef.current?.click(); setAttachAnchor(null); }}>
              <ListItemIcon><DescriptionOutlined fontSize="small" /></ListItemIcon>
              <ListItemText>Requirement doc</ListItemText>
            </MenuItem>
            <MenuItem onClick={() => { sheetInputRef.current?.click(); setAttachAnchor(null); }}>
              <ListItemIcon><GridOnOutlined fontSize="small" /></ListItemIcon>
              <ListItemText>Sample sheet</ListItemText>
            </MenuItem>
            <MenuItem onClick={() => { setSqlDialogOpen(true); setAttachAnchor(null); }}>
              <ListItemIcon><CodeOutlined fontSize="small" /></ListItemIcon>
              <ListItemText>Source SQL</ListItemText>
            </MenuItem>
          </Menu>
          <TextField fullWidth multiline minRows={1} maxRows={12} size="small" variant="standard"
            placeholder="Describe the report, or paste the full requirement…"
            value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={onKeyDown} disabled={busy}
            slotProps={{ input: { disableUnderline: true } }}
            sx={{ flex: 1, px: 0.5, py: 0.5 }} />
          <IconButton color="primary" size="small" onClick={() => void send()}
            disabled={busy || (!input.trim() && !reqDoc && !sheet && !sourceSql)}>
            <SendOutlined fontSize="small" />
          </IconButton>
        </Box>
      </Box>

      <SourceSqlDialog
        open={sqlDialogOpen} onClose={() => setSqlDialogOpen(false)}
        existingName={sourceSql?.name}
        onAttach={(f) => { setSourceSql(f); setSqlDialogOpen(false); }}
      />
    </Box>
  );
}

// Paste-first (copy the old SQL straight out of your editor) — matches how this
// gets used in practice — with a small "upload a .sql file instead" escape
// hatch for anyone who has it saved as a file. Either way it ends up as a File,
// reusing the exact same upload path as the other two attachments.
function SourceSqlDialog({ open, onClose, existingName, onAttach }: {
  open: boolean; onClose: () => void; existingName?: string; onAttach: (f: File) => void;
}) {
  const [text, setText] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { if (open) setText(""); }, [open]);

  const loadFile = (f: File) => { f.text().then(setText); };
  const attach = () => {
    if (!text.trim()) { onClose(); return; }
    onAttach(new File([text], existingName ?? "source_query.sql", { type: "text/plain" }));
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>Paste the legacy source SQL</DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
          The old report's query, from the client's previous system — the AI will map
          its logic onto this tenant's actual datamart tables and columns instead of
          assuming the old names still apply.
        </Typography>
        <input ref={fileInputRef} type="file" accept=".sql,.txt" hidden
          onChange={(e) => { const f = e.target.files?.[0]; if (f) loadFile(f); e.target.value = ""; }} />
        <Button size="small" variant="text" onClick={() => fileInputRef.current?.click()}
          sx={{ mb: 1, textTransform: "none" }}>
          or upload a .sql file instead
        </Button>
        <TextField fullWidth multiline minRows={12} maxRows={24}
          placeholder="SELECT ..."
          value={text} onChange={(e) => setText(e.target.value)}
          slotProps={{ input: { sx: { fontFamily: "ui-monospace, monospace", fontSize: "0.8rem" } } }} />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="contained" onClick={attach} disabled={!text.trim()}>Attach</Button>
      </DialogActions>
    </Dialog>
  );
}
