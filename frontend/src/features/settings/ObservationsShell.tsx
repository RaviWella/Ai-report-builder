// Observations: category hub in the body, then tool detail + domain picker.
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link as RouterLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Alert, Box, Breadcrumbs, Button, Card, CardActionArea, CardContent,
  CircularProgress, Link, MenuItem, Stack, TextField, Typography,
} from "@mui/material";
import {
  ArrowBack, DomainOutlined, FunctionsOutlined, HealthAndSafetyOutlined,
  MenuBookOutlined, SettingsOutlined, TranslateOutlined,
} from "@mui/icons-material";
import { authApi, platformApi, type Me, type PlatformTenant } from "../../api/client";
import { getActAsTenant, restoreBaseActAsTenant, setActAsTenant } from "../../auth/session";
import { isSupportAdmin } from "../../auth/roles";

export const OBSERVATION_CATEGORIES: {
  title: string;
  blurb: string;
  path: string;
  icon: ReactNode;
  group: string;
}[] = [
  {
    title: "AI Settings",
    blurb: "AI provider configuration for the selected domain",
    path: "/settings/observations/ai",
    icon: <SettingsOutlined />,
    group: "AI",
  },
  {
    title: "Metrics",
    blurb: "Governed semantic metrics",
    path: "/settings/observations/metrics",
    icon: <FunctionsOutlined />,
    group: "Config",
  },
  {
    title: "Glossary",
    blurb: "Business glossary terms",
    path: "/settings/observations/glossary",
    icon: <MenuBookOutlined />,
    group: "Config",
  },
  {
    title: "Data Health",
    blurb: "Data capture coverage and gaps",
    path: "/settings/observations/data-health",
    icon: <HealthAndSafetyOutlined />,
    group: "Config",
  },
  {
    title: "Legacy SQL Converter",
    blurb: "Convert legacy SQL into rule reports",
    path: "/settings/observations/legacy-sql",
    icon: <TranslateOutlined />,
    group: "Config",
  },
];

function useObservationDomain() {
  const [me, setMe] = useState<Me | null>(null);
  const [tenants, setTenants] = useState<PlatformTenant[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [domain, setDomain] = useState<string>(getActAsTenant() ?? "");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const profile = await authApi.me();
        if (cancelled) return;
        setMe(profile);
        if (isSupportAdmin(profile)) {
          const res = await platformApi.listTenants();
          if (cancelled) return;
          setTenants(res.tenants);
          const initial =
            getActAsTenant()
            || (res.tenants.some((t) => t.subdomain === profile.tenant_id)
              ? profile.tenant_id
              : res.tenants[0]?.subdomain)
            || profile.tenant_id;
          setDomain(initial);
        } else {
          setTenants([{
            subdomain: profile.tenant_id,
            pg_schema: profile.tenant_id,
            datamart_key: profile.tenant_id,
            status: "active",
            provisioned_at: null,
            provisioned_by: null,
            nav_sections: profile.nav_sections ?? {},
          }]);
          setDomain(profile.tenant_id);
        }
      } catch (e: unknown) {
        const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
        if (!cancelled) setError(detail ?? "Failed to load domains.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const onDomainChange = (next: string) => {
    setDomain(next);
    if (isSupportAdmin(me)) setActAsTenant(next);
    else restoreBaseActAsTenant();
  };

  const selectedLabel = useMemo(() => {
    const row = tenants.find((t) => t.subdomain === domain);
    return row ? `${row.subdomain} · ${row.datamart_key}` : domain;
  }, [tenants, domain]);

  return { me, tenants, loading, error, domain, onDomainChange, selectedLabel };
}

export function ObservationsShell() {
  const location = useLocation();
  const isHub = location.pathname === "/settings/observations"
    || location.pathname === "/settings/observations/";

  // On the category hub, drop the observation act-as so no stale tenant context
  // leaks back into the builder.
  useEffect(() => {
    if (isHub) restoreBaseActAsTenant();
  }, [isHub]);

  if (isHub) {
    return <Outlet />;
  }

  return <ObservationDetailFrame />;
}

function ObservationDetailFrame() {
  const navigate = useNavigate();
  const location = useLocation();
  const { me, tenants, loading, error, domain, onDomainChange, selectedLabel } = useObservationDomain();

  const category = OBSERVATION_CATEGORIES.find(
    (c) => location.pathname === c.path || location.pathname.startsWith(`${c.path}/`),
  );

  useEffect(() => {
    if (!loading && domain && isSupportAdmin(me)) {
      setActAsTenant(domain);
    }
  }, [loading, domain, me]);

  if (loading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", py: 8 }}>
        <CircularProgress size={28} />
      </Box>
    );
  }

  return (
    <Box>
      <Button
        startIcon={<ArrowBack />}
        onClick={() => navigate("/settings/observations")}
        sx={{ textTransform: "none", mb: 1.5, color: "#007499" }}
      >
        Back to observations
      </Button>

      <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems={{ sm: "center" }} sx={{ mb: 2 }}>
        <Box sx={{ flex: 1 }}>
          <Breadcrumbs sx={{ mb: 0.5 }}>
            <Link component={RouterLink} to="/settings/observations" underline="hover" color="inherit">
              Observations
            </Link>
            <Typography color="text.primary">{category?.title ?? "Detail"}</Typography>
          </Breadcrumbs>
          <Typography variant="h4" sx={{ mb: 0.25 }}>{category?.title ?? "Observation"}</Typography>
          <Typography variant="body2" color="text.secondary">
            {category?.blurb
              ?? "Inspect this tool for the selected domain."}
            {isSupportAdmin(me)
              ? " Support Admin requests run as that domain."
              : " You can only observe your own domain."}
          </Typography>
        </Box>
        <TextField
          select
          size="small"
          label="Domain"
          value={domain}
          onChange={(e) => onDomainChange(e.target.value)}
          sx={{ minWidth: 280 }}
          slotProps={{
            input: {
              startAdornment: <DomainOutlined sx={{ mr: 1, color: "#9CA3AF", fontSize: 20 }} />,
            },
          }}
        >
          {tenants.map((t) => (
            <MenuItem key={t.subdomain} value={t.subdomain}>
              {t.subdomain}
            </MenuItem>
          ))}
        </TextField>
      </Stack>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      <Alert severity="info" sx={{ mb: 2 }}>
        Viewing as <b>{selectedLabel || "—"}</b>
      </Alert>

      <Box key={domain || "none"}>
        <Outlet />
      </Box>
    </Box>
  );
}

export function ObservationsHome() {
  const navigate = useNavigate();
  const groups = [
    { title: "AI", items: OBSERVATION_CATEGORIES.filter((c) => c.group === "AI") },
    { title: "Config", items: OBSERVATION_CATEGORIES.filter((c) => c.group === "Config") },
  ];

  return (
    <Box sx={{ maxWidth: 960 }}>
      <Typography variant="h4" sx={{ mb: 0.5 }}>Observations</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Choose a category to inspect. You’ll pick the domain on the next screen.
      </Typography>

      <Stack spacing={3}>
        {groups.map((group) => (
          <Box key={group.title}>
            <Typography
              sx={{
                fontSize: "0.72rem",
                fontWeight: 700,
                letterSpacing: "0.06em",
                textTransform: "uppercase",
                color: "#6B7280",
                mb: 1.25,
              }}
            >
              {group.title}
            </Typography>
            <Box
              sx={{
                display: "grid",
                gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" },
                gap: 1.5,
              }}
            >
              {group.items.map((item) => (
                <Card
                  key={item.path}
                  variant="outlined"
                  sx={{
                    borderRadius: 2,
                    borderColor: "#E5E7EB",
                    transition: "border-color 120ms, box-shadow 120ms",
                    "&:hover": {
                      borderColor: "#007499",
                      boxShadow: "0 0 0 1px #00749922",
                    },
                  }}
                >
                  <CardActionArea onClick={() => navigate(item.path)} sx={{ height: "100%" }}>
                    <CardContent sx={{ display: "flex", gap: 1.5, alignItems: "flex-start" }}>
                      <Box
                        sx={{
                          width: 40,
                          height: 40,
                          borderRadius: 2,
                          bgcolor: "#EAF4F7",
                          color: "#007499",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          flexShrink: 0,
                        }}
                      >
                        {item.icon}
                      </Box>
                      <Box>
                        <Typography sx={{ fontWeight: 700, fontSize: "0.95rem", mb: 0.25 }}>
                          {item.title}
                        </Typography>
                        <Typography sx={{ fontSize: "0.8rem", color: "#6B7280" }}>
                          {item.blurb}
                        </Typography>
                      </Box>
                    </CardContent>
                  </CardActionArea>
                </Card>
              ))}
            </Box>
          </Box>
        ))}
      </Stack>
    </Box>
  );
}
