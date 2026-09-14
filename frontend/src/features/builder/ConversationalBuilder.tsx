// Conversational report builder (FR-A3/A4) — a ChatGPT-style page: a history
// sidebar of past chats plus a full-width conversation where the user talks to the
// semantic layer in plain language and the result renders INLINE under each answer.
//
// Chat history is PERSISTED (aiApi sessions). Reopening a past chat replays its
// stored messages — including the saved result rows — verbatim: a past answer never
// changes even if the datamart data has since moved (immutable snapshot).
//
//   chat turn  -> aiApi.chat (deterministic-first; LLM fallback)
//   live data  -> reportApi.previewSpec (Redis-cached; ~ms on repeat), shown inline
//   history    -> chatSessionApi (create / list / get / append / delete)
//   save       -> templateApi.create -> saveDraft -> publish
import { useEffect, useRef, useState } from "react";
import {
  Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent,
  DialogTitle, IconButton, InputAdornment, MenuItem, Paper, Snackbar, Stack,
  TextField, Tooltip, Typography,
} from "@mui/material";
import { WideReportTable } from "../../components/WideReportTable";
import {
  AddOutlined, AutoAwesomeOutlined, BoltOutlined, DeleteOutline, FilterAltOutlined,
  SaveOutlined, Send, TableChartOutlined, ReportProblemOutlined, CheckCircleOutline,
} from "@mui/icons-material";
import { useNavigate } from "react-router-dom";
import {
  aiApi, chatSessionApi, reportApi, templateApi, validationsApi,
  type ChatSessionHead, type StoredMsg,
} from "../../api/client";
import { REPORT_MODULES, useBuilderStore } from "../../store/builderStore";
import type { DataSpec, QueryResult } from "../../types/spec";

interface Mapping {
  matched: { phrase: string; ref: string; label: string; score: number }[];
  unmatched: string[]; filters: string[]; confidence: number;
}
interface Msg {
  role: "you" | "assistant" | "error" | "result";
  text?: string; source?: string; mapping?: Mapping | null;
  result?: QueryResult; tookMs?: number;
  spec?: DataSpec; prompt?: string;  // on a result: the spec + the prompt that built it (per-card save)
  ts?: number;                       // epoch ms when the message was created
  options?: string[];                // clarify: clickable follow-up suggestions
  gaps?: { term: string; status: "in_source" | "not_captured"; message: string }[]; // data gaps
}

const fmtTime = (ts?: number) =>
  ts ? new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "";

const STARTERS = [
  "Show me employee details — name, department, designation",
  "Headcount by department",
  "Total net pay by department this month",
  "Employees who joined in the last 12 months",
];

const detailOf = (e: unknown) =>
  (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;

export function ConversationalBuilder() {
  const navigate = useNavigate();
  const { dataSpec, setDataSpec, presentation, updatePresentation, module, setModule, reset } =
    useBuilderStore();

  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  // Data gaps the user has flagged "request it" (term -> requested), for the chat drill-down.
  const [requestedGaps, setRequestedGaps] = useState<Record<string, boolean>>({});
  const [previewing, setPreviewing] = useState(false);

  // Persisted history.
  const [sessions, setSessions] = useState<ChatSessionHead[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const sessionRef = useRef<string | null>(null);  // stable across awaits

  const [saveOpen, setSaveOpen] = useState(false);
  const [saveName, setSaveName] = useState("");
  const [saveSpec, setSaveSpec] = useState<DataSpec | null>(null);  // which report the dialog will save
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<{ open: boolean; msg: string; sev: "success" | "error" }>(
    { open: false, msg: "", sev: "success" },
  );

  const threadRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const hasSpec = dataSpec.fields.length > 0 || dataSpec.aggregations.length > 0;

  // Keep the cursor in the composer: focus on load and whenever a turn finishes,
  // so the next prompt can be typed without clicking back into the box.
  useEffect(() => { if (!busy) inputRef.current?.focus(); }, [busy]);

  const setSession = (id: string | null) => { sessionRef.current = id; setSessionId(id); };
  const refreshSessions = () => { chatSessionApi.list().then(setSessions).catch(() => {}); };

  // Open to a fresh chat; load the history list into the sidebar.
  useEffect(() => {
    reset(); setSession(null); refreshSessions();
    /* eslint-disable-next-line react-hooks/exhaustive-deps */
  }, []);

  // Keep the thread scrolled to the newest message.
  useEffect(() => {
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, busy, previewing]);

  const newChat = () => { reset(); setMessages([]); setSession(null); setInput(""); };

  const openSession = async (id: string) => {
    if (busy) return;
    try {
      const s = await chatSessionApi.get(id);
      setMessages((s.messages as Msg[]) ?? []);
      if (s.working_data_spec) setDataSpec(s.working_data_spec);
      else reset();
      setSession(id);
    } catch {
      setToast({ open: true, msg: "Couldn’t open that chat.", sev: "error" });
    }
  };

  const removeSession = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    await chatSessionApi.remove(id).catch(() => {});
    if (sessionRef.current === id) newChat();
    refreshSessions();
  };

  // Persist a completed turn (its messages + the working spec) to the session,
  // creating the session on the first turn. Best-effort — never blocks the chat.
  const persistTurn = async (turn: Msg[], spec: DataSpec, firstPrompt: string) => {
    try {
      let sid = sessionRef.current;
      if (!sid) { const s = await chatSessionApi.create(firstPrompt.slice(0, 120)); sid = s.id; setSession(sid); }
      await chatSessionApi.append(sid, turn as StoredMsg[], spec);
      refreshSessions();
    } catch { /* history is best-effort */ }
  };

  const ask = async (text: string) => {
    const q = text.trim();
    if (!q || busy) return;
    setInput("");
    const turn: Msg[] = [{ role: "you", text: q, ts: Date.now() }];
    setMessages((m) => [...m, turn[0]]);
    setBusy(true);
    let specForSave = dataSpec;
    // The most recent result on screen — lets the chat answer follow-up questions
    // about it ("what's the total of above?", "which is highest?").
    const lastResult = [...messages].reverse().find((m) => m.role === "result" && m.result);
    const context = lastResult?.result
      ? { columns: lastResult.result.columns, rows: lastResult.result.rows, prompt: lastResult.prompt }
      : undefined;
    try {
      const res = await aiApi.chat(q, hasSpec ? dataSpec : undefined, context);
      const am: Msg = {
        role: "assistant", text: res.message, source: res.source, mapping: res.mapping,
        ts: Date.now(), options: res.options ?? undefined, gaps: res.gaps ?? undefined,
      };
      turn.push(am);
      setMessages((m) => [...m, am]);

      if (res.kind === "report" && res.data_spec) {
        setDataSpec(res.data_spec);
        specForSave = res.data_spec;
        if (!presentation.title) updatePresentation({ title: q.slice(0, 60) });
        setPreviewing(true);
        const started = performance.now();
        try {
          const r = await reportApi.previewSpec(res.data_spec);
          const rm: Msg = {
            role: "result", result: r, tookMs: Math.round(performance.now() - started),
            spec: res.data_spec, prompt: q, ts: Date.now(),
          };
          turn.push(rm); setMessages((m) => [...m, rm]);
        } catch (e: unknown) {
          const em: Msg = { role: "error", text: detailOf(e) ?? "Couldn’t load the data for that report.", ts: Date.now() };
          turn.push(em); setMessages((m) => [...m, em]);
        } finally {
          setPreviewing(false);
        }
      }
    } catch (e: unknown) {
      const em: Msg = { role: "error", text: detailOf(e) ?? "AI request failed — set an API key in AI Settings.", ts: Date.now() };
      turn.push(em); setMessages((m) => [...m, em]);
    } finally {
      setBusy(false);
      void persistTurn(turn, specForSave, q);
    }
  };

  // Open the save dialog for a SPECIFIC report (a result card, or the latest spec).
  const openSave = (spec: DataSpec, suggestedTitle: string) => {
    setSaveSpec(spec);
    setSaveName(suggestedTitle || presentation.title || "");
    setSaveOpen(true);
  };

  // Hand the report off to the guided Builder to add manual filters (Excel-style):
  // load the chosen spec into the shared store and open on the Filter step.
  const openInBuilder = () => {
    setDataSpec(saveSpec ?? dataSpec);
    updatePresentation({ title: saveName.trim() || presentation.title || "Untitled report" });
    setSaveOpen(false);
    navigate("/builder", { state: { keepSpec: true } });
  };

  const doSave = async () => {
    const spec = saveSpec ?? dataSpec;
    setSaving(true);
    try {
      const name = saveName.trim() || "Untitled report";
      const created = await templateApi.create(name, module, "Built via chat") as { id: string };
      const draft = await templateApi.saveDraft(created.id, { ...spec }, { ...presentation, title: name }) as
        { version_id?: string; id?: string };
      const versionId = draft.version_id ?? draft.id;
      if (versionId) await templateApi.publish(created.id, versionId);
      setSaveOpen(false);
      setToast({ open: true, msg: `Saved “${name}” to Templates.`, sev: "success" });
    } catch (e: unknown) {
      setToast({ open: true, msg: detailOf(e) ?? "Could not save the report.", sev: "error" });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Box sx={{ display: "flex", gap: 2, height: "100%", minHeight: 0 }}>
      {/* ── History sidebar ── */}
      <Paper variant="outlined" sx={{ width: 240, flexShrink: 0, borderRadius: 3, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        <Box sx={{ p: 1.5 }}>
          <Button fullWidth variant="outlined" startIcon={<AddOutlined />} onClick={newChat}
            sx={{ justifyContent: "flex-start", borderRadius: 2 }}>
            New chat
          </Button>
        </Box>
        <Box sx={{ flex: 1, overflowY: "auto", px: 1, pb: 1 }}>
          {sessions.length === 0 ? (
            <Typography variant="caption" sx={{ px: 1.5, color: "text.secondary" }}>No saved chats yet.</Typography>
          ) : sessions.map((s) => (
            <Box key={s.id} onClick={() => void openSession(s.id)}
              sx={{
                display: "flex", alignItems: "center", gap: 0.5, px: 1.25, py: 1, mb: 0.25,
                borderRadius: 2, cursor: "pointer", fontSize: "0.82rem",
                bgcolor: s.id === sessionId ? "#EAF4F7" : "transparent",
                color: s.id === sessionId ? "#007499" : "#374151",
                "&:hover": { bgcolor: s.id === sessionId ? "#EAF4F7" : "#F3F4F6", "& .del": { opacity: 1 } },
              }}>
              <Box sx={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{s.title}</Box>
              <IconButton className="del" size="small" onClick={(e) => void removeSession(s.id, e)}
                sx={{ opacity: 0, p: 0.25 }}>
                <DeleteOutline sx={{ fontSize: 15 }} />
              </IconButton>
            </Box>
          ))}
        </Box>
      </Paper>

      {/* ── Chat column ── */}
      <Box sx={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1, pb: 1.5 }}>
          <AutoAwesomeOutlined sx={{ color: "#007499", fontSize: 22 }} />
          <Box sx={{ flex: 1 }}>
            <Typography sx={{ fontWeight: 700, fontSize: "1rem", lineHeight: 1.1 }}>Chat to build a report</Typography>
            <Typography sx={{ fontSize: "0.74rem", color: "#6B7280" }}>Ask in plain language — your data appears right here in the chat.</Typography>
          </Box>
          <Button size="small" variant="contained" startIcon={<SaveOutlined />} disabled={!hasSpec}
            onClick={() => openSave(dataSpec, presentation.title || "")}>
            Save latest
          </Button>
        </Box>

        <Paper variant="outlined"
          sx={{ flex: 1, minHeight: 0, borderRadius: 3, display: "flex", flexDirection: "column", overflow: "hidden", bgcolor: "#FCFCFD" }}>
          <Box ref={threadRef} sx={{ flex: 1, overflowY: "auto", px: { xs: 2, sm: 4 }, py: 3 }}>
          {messages.length === 0 ? (
            <Box sx={{ color: "text.secondary" }}>
              <Typography variant="body2" sx={{ mb: 1.5 }}>Try one of these, or type your own:</Typography>
              <Stack spacing={1}>
                {STARTERS.map((s) => (
                  <Chip key={s} label={s} onClick={() => void ask(s)} variant="outlined"
                    sx={{ justifyContent: "flex-start", height: "auto", py: 0.75, borderRadius: 2,
                          "& .MuiChip-label": { whiteSpace: "normal", fontSize: "0.82rem" } }} />
                ))}
              </Stack>
            </Box>
          ) : (
            <Stack spacing={1.5}>
              {messages.map((m, i) =>
                m.role === "result" && m.result ? (
                  <ResultCard key={i} result={m.result} tookMs={m.tookMs} ts={m.ts}
                    onSave={m.spec ? () => openSave(m.spec!, m.prompt || "") : undefined} />
                ) : (
                  <Box key={i} sx={{
                    alignSelf: m.role === "you" ? "flex-end" : "flex-start",
                    bgcolor: m.role === "you" ? "#007499" : m.role === "error" ? "#FFF0ED" : "#F3F4F6",
                    color: m.role === "you" ? "#fff" : m.role === "error" ? "#C13515" : "#1A1A1A",
                    px: 1.75, py: 1.1, borderRadius: 2.5, maxWidth: "88%", fontSize: "0.88rem", lineHeight: 1.5,
                  }}>
                    {m.text}
                    {m.source && (
                      <Chip size="small"
                        label={
                          m.source === "certified" ? "✓ certified"
                          : m.source === "learned" ? "saved answer"
                          : m.source === "deterministic" ? "exact match"
                          : "AI"
                        }
                        sx={{ ml: 1, height: 18, fontSize: "0.62rem",
                              bgcolor: m.source === "certified" ? "#E6F4EA" : "#fff",
                              color: m.source === "certified" ? "#1E7E34" : "#6B7280" }} />
                    )}
                    {m.mapping && (m.mapping.matched.length > 0 || m.mapping.unmatched.length > 0) && (
                      <Box sx={{ mt: 0.75, display: "flex", flexWrap: "wrap", gap: 0.5 }}>
                        {m.mapping.matched.map((f) => (
                          <Chip key={f.ref} size="small" label={f.label}
                            sx={{ height: 20, fontSize: "0.66rem", bgcolor: "#E6F4EA", color: "#1E7E34" }} />
                        ))}
                        {m.mapping.filters.map((f, j) => (
                          <Chip key={`flt${j}`} size="small" label={f} variant="outlined"
                            sx={{ height: 20, fontSize: "0.66rem", borderColor: "#C4CAD2", color: "#374151" }} />
                        ))}
                        {m.mapping.unmatched.map((u, j) => (
                          <Chip key={`un${j}`} size="small" label={`✕ ${u}`}
                            sx={{ height: 20, fontSize: "0.66rem", bgcolor: "#FFF0ED", color: "#C13515" }} />
                        ))}
                      </Box>
                    )}
                    {m.options && m.options.length > 0 && (
                      <Box sx={{ mt: 0.75, display: "flex", flexWrap: "wrap", gap: 0.5 }}>
                        {m.options.map((opt) => (
                          <Chip key={opt} label={opt} size="small" onClick={() => void ask(opt)}
                            disabled={busy} variant="outlined"
                            sx={{ height: 24, fontSize: "0.72rem", borderColor: "#007499", color: "#007499",
                                  "&:hover": { bgcolor: "#EAF4F7" } }} />
                        ))}
                      </Box>
                    )}
                    {/* Data gaps — business-language drill-down for the HR user */}
                    {m.gaps && m.gaps.length > 0 && (
                      <Stack spacing={0.75} sx={{ mt: 1 }}>
                        {m.gaps.map((g) => (
                          <Box key={g.term} sx={{ p: 1, borderRadius: 1.5,
                            bgcolor: g.status === "in_source" ? "#FFFBEB" : "#F3F4F6",
                            border: `1px solid ${g.status === "in_source" ? "#FDE68A" : "#E5E7EB"}` }}>
                            <Stack direction="row" spacing={0.75} alignItems="flex-start">
                              <ReportProblemOutlined sx={{ fontSize: 16, color: "#92400E", mt: "1px" }} />
                              <Typography sx={{ fontSize: "0.76rem", color: "#374151", flex: 1 }}>{g.message}</Typography>
                            </Stack>
                            {g.status === "in_source" && (
                              requestedGaps[g.term] ? (
                                <Chip size="small" icon={<CheckCircleOutline />} label="Requested"
                                  sx={{ mt: 0.5, height: 22, fontSize: "0.68rem", bgcolor: "#E6F4EA", color: "#1E7E34" }} />
                              ) : (
                                <Button size="small" sx={{ mt: 0.25, textTransform: "none", fontSize: "0.72rem" }}
                                  onClick={() => {
                                    setRequestedGaps((p) => ({ ...p, [g.term]: true }));
                                    validationsApi.requestField(g.term).catch(() => {});
                                  }}>
                                  Request it
                                </Button>
                              )
                            )}
                          </Box>
                        ))}
                      </Stack>
                    )}
                    {m.ts && (
                      <Typography sx={{
                        mt: 0.5, fontSize: "0.6rem", textAlign: m.role === "you" ? "right" : "left",
                        color: m.role === "you" ? "rgba(255,255,255,0.72)" : "#9CA3AF",
                      }}>
                        {fmtTime(m.ts)}
                      </Typography>
                    )}
                  </Box>
                ),
              )}
              {(busy || previewing) && (
                <Box sx={{ alignSelf: "flex-start", display: "flex", alignItems: "center", gap: 1, color: "#6B7280", fontSize: "0.82rem" }}>
                  <CircularProgress size={13} thickness={5} /> {previewing ? "running the report…" : "thinking…"}
                </Box>
              )}
            </Stack>
          )}
          </Box>

          <Box sx={{ borderTop: "1px solid #E5E7EB", p: 1.5, bgcolor: "#fff" }}>
            <TextField
              fullWidth multiline minRows={1} maxRows={10} value={input} disabled={busy}
              inputRef={inputRef} autoFocus
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void ask(input); } }}
              placeholder="Ask anything"
              InputProps={{
                sx: { borderRadius: "26px", alignItems: "center", py: 1, pl: 1, pr: 0.75, bgcolor: "#fff" },
                startAdornment: (
                  <InputAdornment position="start">
                    <Tooltip title="New chat">
                      <IconButton size="small" onClick={newChat} disabled={busy}><AddOutlined /></IconButton>
                    </Tooltip>
                  </InputAdornment>
                ),
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton color="primary" onClick={() => void ask(input)} disabled={busy || !input.trim()}>
                      <Send />
                    </IconButton>
                  </InputAdornment>
                ),
              }} />
          </Box>
        </Paper>
      </Box>

      {/* ── Save dialog ── */}
      <Dialog open={saveOpen} onClose={() => setSaveOpen(false)} fullWidth maxWidth="xs">
        <DialogTitle sx={{ fontSize: "1rem", fontWeight: 700 }}>Save as report template</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 0.5 }}>
            <TextField label="Report name" size="small" fullWidth value={saveName} onChange={(e) => setSaveName(e.target.value)} autoFocus />
            <TextField label="Module" size="small" select fullWidth value={module} onChange={(e) => setModule(e.target.value)}>
              {REPORT_MODULES.map((m) => <MenuItem key={m} value={m}>{m}</MenuItem>)}
            </TextField>
            <Typography variant="caption" color="text.secondary">
              Save &amp; publish now, or add manual filters in the Builder first (the same
              filter step Excel-built reports use).
            </Typography>
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2, justifyContent: "space-between" }}>
          <Button onClick={openInBuilder} color="inherit" startIcon={<FilterAltOutlined />}>
            Add filters…
          </Button>
          <Box>
            <Button onClick={() => setSaveOpen(false)} color="inherit">Cancel</Button>
            <Button onClick={() => void doSave()} variant="contained" disabled={saving}
              startIcon={saving ? <CircularProgress size={14} /> : <SaveOutlined />}>Save</Button>
          </Box>
        </DialogActions>
      </Dialog>

      <Snackbar open={toast.open} autoHideDuration={5000} onClose={() => setToast((t) => ({ ...t, open: false }))}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}>
        <Alert severity={toast.sev} onClose={() => setToast((t) => ({ ...t, open: false }))}
          action={toast.sev === "success" ? <Button color="inherit" size="small" onClick={() => navigate("/")}>View</Button> : undefined}>
          {toast.msg}
        </Alert>
      </Snackbar>
    </Box>
  );
}

// Format a cell value for prose: thousands separators for numbers, em-dash for null.
const fmtVal = (v: unknown): string => {
  if (v == null || v === "") return "—";
  const n = Number(v);
  if (typeof v !== "boolean" && !Number.isNaN(n) && /^-?\d/.test(String(v))) {
    return Number.isInteger(n) ? n.toLocaleString() : n.toLocaleString(undefined, { maximumFractionDigits: 2 });
  }
  return String(v);
};

// A short, plain-language explanation of a result — deterministic (no LLM), built
// from the columns/rows so a user instantly understands the numbers.
function summarize(r: QueryResult): string {
  const { row_count: n, columns: cols, rows } = r;
  if (n === 0) return "No matching records found.";
  if (n === 1 && cols.length === 1) return `${cols[0]}: ${fmtVal(rows[0][cols[0]])}.`;
  // A grouped roll-up: one dimension + one numeric measure.
  const numeric = [...cols].reverse().find(
    (c) => rows.some((row) => row[c] != null) &&
      rows.every((row) => row[c] == null || (row[c] !== "" && !Number.isNaN(Number(row[c])))),
  );
  if (n > 1 && cols.length === 2 && numeric) {
    const dim = cols.find((c) => c !== numeric)!;
    const sorted = [...rows].filter((row) => row[numeric] != null)
      .sort((a, b) => Number(b[numeric]) - Number(a[numeric]));
    const top = sorted[0], bottom = sorted[sorted.length - 1];
    const range = sorted.length > 1
      ? ` Highest: ${fmtVal(top[dim])} (${fmtVal(top[numeric])}); lowest: ${fmtVal(bottom[dim])} (${fmtVal(bottom[numeric])}).`
      : top ? ` ${fmtVal(top[dim])}: ${fmtVal(top[numeric])}.` : "";
    return `${numeric} across ${n} ${dim} value${n === 1 ? "" : "s"}.${range}`;
  }
  if (n === 1) return `1 record — ${cols.join(", ")}.`;
  return `${n.toLocaleString()} records — showing ${cols.join(", ")}.`;
}

// An inline result table — rendered in the conversation flow, ChatGPT-style. When a
// past chat is reopened, this renders the STORED snapshot (no re-query).
function ResultCard(
  { result, tookMs, ts, onSave }: { result: QueryResult; tookMs?: number; ts?: number; onSave?: () => void },
) {
  return (
    <Paper variant="outlined" sx={{ alignSelf: "stretch", borderRadius: 2.5, minWidth: 0, maxWidth: "100%" }}>
      <Box sx={{ px: 2, py: 1.25, borderBottom: "1px solid #E5E7EB", display: "flex", alignItems: "center", gap: 1 }}>
        <TableChartOutlined sx={{ fontSize: 18, color: "#007499" }} />
        <Typography sx={{ fontWeight: 700, fontSize: "0.85rem" }}>Result</Typography>
        {tookMs !== undefined && (
          <Tooltip title="Round-trip when this report was run">
            <Chip size="small" icon={<BoltOutlined sx={{ fontSize: 14 }} />} label={`${tookMs} ms`}
              sx={{ height: 20, fontSize: "0.66rem", bgcolor: "#EAF4F7", color: "#007499" }} />
          </Tooltip>
        )}
        {result.truncated && (
          <Chip size="small" color="warning" label={`Sample of ${result.rows.length} rows`} sx={{ height: 20, fontSize: "0.66rem" }} />
        )}
        <Box sx={{ flex: 1 }} />
        <Typography variant="caption" color="text.secondary" sx={{ mr: onSave ? 1 : 0 }}>
          {result.truncated ? `${result.rows.length} of ${result.row_count} rows` : `${result.row_count} row${result.row_count === 1 ? "" : "s"}`}
          {ts ? ` · ${fmtTime(ts)}` : ""}
        </Typography>
        {onSave && (
          <Button size="small" variant="outlined" startIcon={<SaveOutlined sx={{ fontSize: 16 }} />}
            onClick={onSave} sx={{ py: 0.25, minWidth: 0 }}>
            Save
          </Button>
        )}
      </Box>
      <Box sx={{ px: 2, py: 1.25, borderBottom: "1px solid #F0F1F3", display: "flex", gap: 0.75, alignItems: "flex-start" }}>
        <AutoAwesomeOutlined sx={{ fontSize: 15, color: "#007499", mt: "1px" }} />
        <Typography sx={{ fontSize: "0.82rem", color: "#374151", lineHeight: 1.45 }}>{summarize(result)}</Typography>
      </Box>
      <WideReportTable
        embedded
        columns={result.columns}
        rows={result.rows}
        cellText={(v) => fmtVal(v)}
        maxHeight={360}
      />
    </Paper>
  );
}
