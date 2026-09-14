// Hidden route: /settings/permissions
// Uses the existing Report Builder session — no separate sign-in.
// Nav sections are hardcoded; domains load from platform.tenant_provision_status.
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert, Box, Button, Card, CardContent, Chip, CircularProgress, Divider,
  FormControlLabel, InputAdornment, Stack, Switch, TextField, Typography,
} from "@mui/material";
import {
  AdminPanelSettingsOutlined, DomainOutlined, RestartAlt, SaveOutlined,
  SearchOutlined, CheckCircleOutline,
} from "@mui/icons-material";
import { platformApi, type PlatformTenant } from "../../api/client";
import {
  DEFAULT_NAV_SECTION_FLAGS, resolveNavFlags, type NavSectionFlags,
} from "../../auth/navSections";

/** Tenant-grantable sections only (Config / AI Settings are under Observations). */
const SECTION_KEYS = [
  "Chat",
  "Builder",
  "Documents",
  "Viewer",
  "How it works",
] as const;

const SECTION_META: Record<string, { blurb: string; group: "Workspace" | "Admin tools" }> = {
  Chat: { blurb: "Conversational report builder", group: "Workspace" },
  Builder: { blurb: "Classic / rule report builder", group: "Workspace" },
  Documents: { blurb: "Letter & document designer", group: "Workspace" },
  Viewer: { blurb: "Published report viewer", group: "Workspace" },
  "How it works": { blurb: "Architecture / product guide", group: "Admin tools" },
};

function flagsEqual(a: NavSectionFlags, b: NavSectionFlags): boolean {
  return SECTION_KEYS.every((key) => Boolean(a[key]) === Boolean(b[key]));
}

export function PermissionsSettings() {
  const [tenants, setTenants] = useState<PlatformTenant[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string>("");
  const [draft, setDraft] = useState<NavSectionFlags>({ ...DEFAULT_NAV_SECTION_FLAGS });
  const [baseline, setBaseline] = useState<NavSectionFlags>({ ...DEFAULT_NAV_SECTION_FLAGS });
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<{ ok: boolean; msg: string } | null>(null);

  const loadTenants = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const res = await platformApi.listTenants();
      setTenants(res.tenants);
      const first = res.tenants[0]?.subdomain ?? "";
      setSelected((prev) => {
        if (prev && res.tenants.some((t) => t.subdomain === prev)) return prev;
        return first;
      });
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setLoadError(detail ?? "Failed to load domains from the database.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadTenants();
  }, [loadTenants]);

  const selectedTenant = useMemo(
    () => tenants.find((t) => t.subdomain === selected) ?? null,
    [tenants, selected],
  );

  useEffect(() => {
    if (!selectedTenant) return;
    const flags = resolveNavFlags(selectedTenant.nav_sections);
    setDraft(flags);
    setBaseline(flags);
    setStatus(null);
  }, [selectedTenant]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return tenants;
    return tenants.filter((t) =>
      t.subdomain.toLowerCase().includes(q)
      || t.datamart_key.toLowerCase().includes(q)
      || t.pg_schema.toLowerCase().includes(q),
    );
  }, [tenants, query]);

  const dirty = useMemo(() => !flagsEqual(draft, baseline), [draft, baseline]);

  const enabledCount = useMemo(
    () => SECTION_KEYS.filter((key) => draft[key]).length,
    [draft],
  );

  const groups = useMemo(
    () => [
      {
        title: "Workspace",
        keys: SECTION_KEYS.filter((k) => SECTION_META[k].group === "Workspace"),
      },
      {
        title: "Admin tools",
        keys: SECTION_KEYS.filter((k) => SECTION_META[k].group === "Admin tools"),
      },
    ],
    [],
  );

  const selectTenant = (subdomain: string) => {
    if (dirty && !window.confirm("Discard unsaved permission changes?")) return;
    setSelected(subdomain);
  };

  const toggle = (key: string) => {
    setDraft((prev) => ({ ...prev, [key]: !prev[key] }));
    setStatus(null);
  };

  const resetDefaults = () => {
    setDraft({ ...DEFAULT_NAV_SECTION_FLAGS });
    setStatus(null);
  };

  const discard = () => {
    setDraft({ ...baseline });
    setStatus(null);
  };

  const save = async () => {
    if (!selected) return;
    setSaving(true);
    setStatus(null);
    try {
      const payload = Object.fromEntries(
        SECTION_KEYS.map((key) => [key, Boolean(draft[key])]),
      );
      const res = await platformApi.patchNavSections(selected, payload);
      const next = resolveNavFlags(res.nav_sections);
      setDraft(next);
      setBaseline(next);
      setTenants((prev) =>
        prev.map((t) => (t.subdomain === selected ? { ...t, nav_sections: next } : t)),
      );
      setStatus({ ok: true, msg: `Saved permissions for ${selected}` });
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setStatus({ ok: false, msg: detail ?? "Save failed" });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Box sx={{ maxWidth: 1100 }}>
      <Stack direction="row" spacing={1.5} alignItems="center" sx={{ mb: 0.5 }}>
        <AdminPanelSettingsOutlined sx={{ color: "#007499" }} />
        <Typography variant="h4">Domain permissions</Typography>
      </Stack>
      <Typography variant="body2" sx={{ mb: 2.5, color: "text.secondary", maxWidth: 720 }}>
        Set which Report Builder sidebar sections each domain can see.
        Config and AI Settings are admin-only under Observations and are not grantable here.
        Templates is always available.
      </Typography>

      {loadError && <Alert severity="error" sx={{ mb: 2 }}>{loadError}</Alert>}
      {status && (
        <Alert
          severity={status.ok ? "success" : "error"}
          sx={{ mb: 2 }}
          icon={status.ok ? <CheckCircleOutline /> : undefined}
        >
          {status.msg}
        </Alert>
      )}

      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: { xs: "1fr", md: "320px 1fr" },
          gap: 2,
          alignItems: "start",
        }}
      >
        <Card variant="outlined" sx={{ borderRadius: 2 }}>
          <CardContent sx={{ pb: "12px !important" }}>
            <Typography sx={{ fontWeight: 700, fontSize: "0.9rem", mb: 1.5 }}>Domains</Typography>
            <TextField
              size="small"
              fullWidth
              placeholder="Search subdomain…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              slotProps={{
                input: {
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchOutlined sx={{ fontSize: 18, color: "#9CA3AF" }} />
                    </InputAdornment>
                  ),
                },
              }}
              sx={{ mb: 1.5 }}
            />
            {loading ? (
              <Box sx={{ py: 4, textAlign: "center" }}><CircularProgress size={24} /></Box>
            ) : filtered.length === 0 ? (
              <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
                No domains found.
              </Typography>
            ) : (
              <Stack spacing={0.5} sx={{ maxHeight: 520, overflow: "auto", pr: 0.5 }}>
                {filtered.map((t) => {
                  const active = t.subdomain === selected;
                  const onCount = SECTION_KEYS.filter((k) => t.nav_sections?.[k]).length;
                  return (
                    <Box
                      key={t.subdomain}
                      onClick={() => selectTenant(t.subdomain)}
                      sx={{
                        cursor: "pointer",
                        borderRadius: 2,
                        px: 1.5,
                        py: 1.1,
                        border: "1px solid",
                        borderColor: active ? "#007499" : "#E5E7EB",
                        bgcolor: active ? "#EAF4F7" : "#fff",
                        "&:hover": { bgcolor: active ? "#EAF4F7" : "#F9FAFB" },
                      }}
                    >
                      <Stack direction="row" spacing={1} alignItems="center">
                        <DomainOutlined sx={{ fontSize: 18, color: active ? "#007499" : "#9CA3AF" }} />
                        <Box sx={{ minWidth: 0, flex: 1 }}>
                          <Typography noWrap sx={{ fontWeight: 600, fontSize: "0.85rem" }}>
                            {t.subdomain}
                          </Typography>
                          <Typography noWrap sx={{ fontSize: "0.7rem", color: "#6B7280" }}>
                            {onCount}/{SECTION_KEYS.length} sections · {t.status}
                          </Typography>
                        </Box>
                      </Stack>
                    </Box>
                  );
                })}
              </Stack>
            )}
          </CardContent>
        </Card>

        <Card variant="outlined" sx={{ borderRadius: 2 }}>
          <CardContent>
            {!selectedTenant ? (
              <Typography color="text.secondary" sx={{ py: 6, textAlign: "center" }}>
                Select a domain to edit its section permissions.
              </Typography>
            ) : (
              <>
                <Stack
                  direction={{ xs: "column", sm: "row" }}
                  justifyContent="space-between"
                  alignItems={{ xs: "stretch", sm: "center" }}
                  spacing={1.5}
                  sx={{ mb: 2 }}
                >
                  <Box>
                    <Typography sx={{ fontWeight: 700, fontSize: "1.05rem" }}>
                      {selectedTenant.subdomain}
                    </Typography>
                    <Typography sx={{ fontSize: "0.75rem", color: "#6B7280" }}>
                      schema {selectedTenant.pg_schema} · datamart {selectedTenant.datamart_key}
                    </Typography>
                  </Box>
                  <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                    <Chip
                      size="small"
                      label={`${enabledCount} enabled`}
                      sx={{ bgcolor: "#EAF4F7", color: "#007499", fontWeight: 600 }}
                    />
                    {dirty && <Chip size="small" color="warning" label="Unsaved changes" />}
                    <Chip
                      size="small"
                      label={selectedTenant.status}
                      color={selectedTenant.status === "active" ? "success" : "default"}
                      variant="outlined"
                    />
                  </Stack>
                </Stack>

                <Alert severity="info" sx={{ mb: 2 }}>
                  <b>Templates</b> is always visible for every domain and cannot be turned off here.
                </Alert>

                <Stack spacing={2.5}>
                  {groups.map((group) => (
                    <Box key={group.title}>
                      <Typography
                        sx={{
                          fontSize: "0.72rem",
                          fontWeight: 700,
                          letterSpacing: "0.06em",
                          textTransform: "uppercase",
                          color: "#6B7280",
                          mb: 1,
                        }}
                      >
                        {group.title}
                      </Typography>
                      <Stack
                        spacing={0}
                        sx={{ border: "1px solid #E5E7EB", borderRadius: 2, overflow: "hidden" }}
                      >
                        {group.keys.map((key, idx) => {
                          const meta = SECTION_META[key];
                          const on = Boolean(draft[key]);
                          return (
                            <Box key={key}>
                              {idx > 0 && <Divider />}
                              <Stack
                                direction="row"
                                alignItems="center"
                                justifyContent="space-between"
                                sx={{
                                  px: 2,
                                  py: 1.25,
                                  bgcolor: on ? "#F8FBFC" : "#fff",
                                }}
                              >
                                <Box sx={{ pr: 2 }}>
                                  <Typography sx={{ fontWeight: 600, fontSize: "0.9rem" }}>
                                    {key}
                                  </Typography>
                                  <Typography sx={{ fontSize: "0.75rem", color: "#6B7280" }}>
                                    {meta.blurb}
                                  </Typography>
                                </Box>
                                <FormControlLabel
                                  sx={{ mr: 0 }}
                                  control={
                                    <Switch
                                      checked={on}
                                      onChange={() => toggle(key)}
                                      color="primary"
                                    />
                                  }
                                  label={on ? "On" : "Off"}
                                  labelPlacement="start"
                                  slotProps={{
                                    typography: {
                                      sx: {
                                        fontSize: "0.75rem",
                                        fontWeight: 600,
                                        color: on ? "#007499" : "#9CA3AF",
                                        mr: 1,
                                        minWidth: 28,
                                      },
                                    },
                                  }}
                                />
                              </Stack>
                            </Box>
                          );
                        })}
                      </Stack>
                    </Box>
                  ))}
                </Stack>

                <Stack
                  direction={{ xs: "column", sm: "row" }}
                  spacing={1}
                  justifyContent="flex-end"
                  sx={{ mt: 3 }}
                >
                  <Button
                    startIcon={<RestartAlt />}
                    onClick={resetDefaults}
                    disabled={saving}
                    sx={{ textTransform: "none" }}
                  >
                    Reset to defaults
                  </Button>
                  <Button
                    onClick={discard}
                    disabled={!dirty || saving}
                    sx={{ textTransform: "none" }}
                  >
                    Discard
                  </Button>
                  <Button
                    variant="contained"
                    startIcon={<SaveOutlined />}
                    onClick={() => void save()}
                    disabled={!dirty || saving}
                    sx={{
                      textTransform: "none",
                      bgcolor: "#007499",
                      "&:hover": { bgcolor: "#006180" },
                    }}
                  >
                    {saving ? "Saving…" : "Save permissions"}
                  </Button>
                </Stack>
              </>
            )}
          </CardContent>
        </Card>
      </Box>
    </Box>
  );
}
