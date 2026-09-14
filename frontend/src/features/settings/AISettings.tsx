// AI provider settings (SRS §8.4, §9) — the client enters their API key HERE.
// Sent once, encrypted at rest server-side, never returned: only a masked hint.
import { useEffect, useState } from "react";
import {
  Alert, Box, Button, Card, CardContent, MenuItem, Stack, TextField,
  Typography,
} from "@mui/material";
import { Save, WifiTethering, Lock, Autorenew } from "@mui/icons-material";
import { aiConfigApi, semanticApi, type AIConfigPublic } from "../../api/client";

const ANTHROPIC_MODELS = ["claude-opus-4-8", "claude-sonnet-4-6", "claude-haiku-4-5-20251001"];

export function AISettings() {
  const [cfg, setCfg] = useState<AIConfigPublic | null>(null);
  const [provider, setProvider] = useState("anthropic");
  const [model, setModel] = useState("claude-opus-4-8");
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [status, setStatus] = useState<{ ok: boolean; msg: string } | null>(null);
  const [testing, setTesting] = useState(false);
  const [rebuilding, setRebuilding] = useState(false);
  const [rebuildMsg, setRebuildMsg] = useState("");

  const rebuild = async () => {
    setRebuilding(true); setRebuildMsg("Introspecting this tenant’s datamart…");
    try {
      const r = await semanticApi.rebuild();
      setRebuildMsg(`✅ v${r.version} — ${r.total_fields} fields across ${r.entities.length} categories (incl. this tenant’s pay items).`);
    } catch (e: unknown) {
      setRebuildMsg("❌ " + ((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Rebuild failed (datamart/VPN?)"));
    } finally { setRebuilding(false); }
  };

  useEffect(() => {
    aiConfigApi.get().then((c) => {
      setCfg(c); setProvider(c.provider); setModel(c.model); setBaseUrl(c.base_url ?? "");
    });
  }, []);

  const save = async () => {
    const c = await aiConfigApi.save({
      provider, model,
      base_url: provider === "selfhosted" ? baseUrl : null,
      ...(apiKey ? { api_key: apiKey } : {}),
      enabled: true,
    });
    setCfg(c); setApiKey(""); setStatus({ ok: true, msg: "Saved ✓" });
  };

  const test = async () => {
    setTesting(true); setStatus(null);
    try {
      const r = await aiConfigApi.test();
      setStatus({ ok: r.ok, msg: r.message });
    } finally { setTesting(false); }
  };

  return (
    <Box sx={{ maxWidth: 560 }}>
      <Typography variant="h4" sx={{ mb: 0.5 }}>AI Provider Settings</Typography>
      <Typography variant="body2" sx={{ mb: 2 }}>
        Your API key is encrypted at rest and never displayed again. The AI only ever receives
        report metadata — never employee data.
      </Typography>

      <Card>
        <CardContent>
          {cfg && (
            <Alert
              icon={<Lock fontSize="inherit" />}
              severity={cfg.has_api_key ? "success" : "warning"}
              sx={{ mb: 2 }}
            >
              <b>{cfg.provider}</b> · {cfg.model} · source: {cfg.source} ·{" "}
              {cfg.has_api_key ? `key configured (${cfg.api_key_hint})` : "no key set"}
            </Alert>
          )}

          <Stack spacing={2}>
            <TextField select size="small" label="Provider" value={provider}
              onChange={(e) => {
                const p = e.target.value;
                setProvider(p);
                // Don't carry an Anthropic model name over to the self-hosted
                // endpoint (it rejects unknown models with a 400), or vice versa.
                if (p === "selfhosted" && ANTHROPIC_MODELS.includes(model)) setModel("mimo-v2.5");
                if (p === "anthropic" && !ANTHROPIC_MODELS.includes(model)) setModel("claude-opus-4-8");
              }}>
              <MenuItem value="anthropic">Anthropic (external API, ZDR + BAA)</MenuItem>
              <MenuItem value="selfhosted">Self-hosted (vLLM, OpenAI-compatible)</MenuItem>
            </TextField>

            {provider === "anthropic" ? (
              <TextField select size="small" label="Model" value={model} onChange={(e) => setModel(e.target.value)}>
                {ANTHROPIC_MODELS.map((m) => <MenuItem key={m} value={m}>{m}</MenuItem>)}
              </TextField>
            ) : (
              <TextField size="small" label="Model" value={model} onChange={(e) => setModel(e.target.value)} placeholder="mimo-v2.5" />
            )}

            {provider === "selfhosted" && (
              <TextField size="small" label="Base URL" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="https://ai-proxy.minchy.ai" />
            )}

            <TextField
              size="small" type="password" autoComplete="off"
              label={
                (provider === "anthropic" ? "API Key" : "Bearer Token") +
                (cfg?.has_api_key ? " (blank = keep existing)" : "")
              }
              value={apiKey} onChange={(e) => setApiKey(e.target.value)}
              placeholder={provider === "anthropic" ? "sk-ant-…" : "sk-…"}
              helperText={provider === "selfhosted" ? "Sent as 'Authorization: Bearer …' to your endpoint" : undefined}
            />

            <Stack direction="row" spacing={1.5} alignItems="center">
              <Button variant="contained" startIcon={<Save />} onClick={save}>Save</Button>
              <Button variant="outlined" startIcon={<WifiTethering />} onClick={test} disabled={testing}>
                {testing ? "Testing…" : "Test connection"}
              </Button>
            </Stack>
            {status && (
              <Alert severity={status.ok ? "success" : "error"} sx={{ mt: 1.5, "& .MuiAlert-message": { wordBreak: "break-word" } }}>
                {status.msg}
              </Alert>
            )}
          </Stack>
        </CardContent>
      </Card>

      <Card sx={{ mt: 2 }}>
        <CardContent>
          <Typography variant="h6" sx={{ mb: 0.5 }}>Data fields (semantic layer)</Typography>
          <Typography variant="body2" sx={{ mb: 1.5 }}>
            Refresh the available report fields from this tenant’s datamart — picks up new
            dynamic pay items / allowances. Creates a new version; existing reports are unaffected.
          </Typography>
          <Stack direction="row" spacing={1.5} alignItems="center">
            <Button variant="outlined" startIcon={rebuilding ? null : <Autorenew />}
              onClick={rebuild} disabled={rebuilding}>
              {rebuilding ? "Rebuilding…" : "Rebuild data fields"}
            </Button>
            {rebuildMsg && <Typography variant="body2" color={rebuildMsg.startsWith("❌") ? "error" : "success.main"}>{rebuildMsg}</Typography>}
          </Stack>
        </CardContent>
      </Card>
    </Box>
  );
}
