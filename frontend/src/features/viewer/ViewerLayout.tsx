// Standalone Report Viewer shell for END USERS — NO admin sidebar/links.
// Top nav = module names; clicking a module opens a dropdown of its reports;
// clicking a report opens it. Reached from the PHP app's "reports" redirect.
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Box, Button, Chip, Menu, MenuItem, Stack, Typography } from "@mui/material";
import { ArrowDropDown, ArrowBack } from "@mui/icons-material";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
import { authApi, templateApi } from "../../api/client";
import { REPORT_MODULES } from "../../store/builderStore";
import { TenantLogo, resolveCompanyLogoUrl } from "../../components/TenantLogo";

interface Tpl {
  id: string; name: string; module?: string;
  current_published_version_id: string | null; kind?: "report" | "document";
}

function ModuleMenu({ module, reports }: { module: string; reports: Tpl[] }) {
  const navigate = useNavigate();
  const [anchor, setAnchor] = useState<null | HTMLElement>(null);
  const open = Boolean(anchor);
  return (
    <>
      <Button
        onClick={(e) => setAnchor(e.currentTarget)}
        endIcon={<ArrowDropDown />}
        sx={{ color: "#374151", fontWeight: 600, textTransform: "none", px: 1.5 }}
      >
        {module}
      </Button>
      <Menu anchorEl={anchor} open={open} onClose={() => setAnchor(null)}
        anchorOrigin={{ vertical: "bottom", horizontal: "left" }}
        slotProps={{ paper: { sx: { minWidth: 240, mt: 0.5 } } }}>
        {reports.map((r) => (
          <MenuItem key={r.id} onClick={() => { navigate(`/viewer/r/${r.id}`); setAnchor(null); }}
            sx={{ fontSize: "0.85rem" }}>
            <Stack direction="row" spacing={1} alignItems="center" justifyContent="space-between" sx={{ width: "100%" }}>
              <span>{r.name}</span>
              {r.kind === "document" && (
                <Chip size="small" label="Document" sx={{ height: 20, fontSize: "0.62rem" }} />
              )}
            </Stack>
          </MenuItem>
        ))}
        {reports.length === 0 && <MenuItem disabled>No reports</MenuItem>}
      </Menu>
    </>
  );
}

export function ViewerLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const onReport = location.pathname.startsWith("/viewer/r/");
  const { data: me, refetch: refetchMe } = useQuery({ queryKey: ["me"], queryFn: authApi.me });
  const { data: templates = [] } = useQuery({ queryKey: ["templates"], queryFn: templateApi.list });

  useEffect(() => {
    const onRefresh = () => { void refetchMe(); };
    window.addEventListener("rb:token-refreshed", onRefresh);
    return () => window.removeEventListener("rb:token-refreshed", onRefresh);
  }, [refetchMe]);

  // Group published reports by module, ordered by the known module list.
  const byModule = (templates as Tpl[])
    .filter((t) => t.current_published_version_id)
    .reduce<Record<string, Tpl[]>>((acc, t) => {
      const m = t.module || "General";
      (acc[m] ??= []).push(t);
      return acc;
    }, {});
  const order = [...(REPORT_MODULES as readonly string[])];
  const modules = Object.entries(byModule).sort(
    (a, b) => (order.indexOf(a[0]) + 1 || 99) - (order.indexOf(b[0]) + 1 || 99),
  );

  return (
    <Box sx={{ minHeight: "100vh", bgcolor: "background.default" }}>
      {/* Line 1 — logo + back */}
      <Box sx={{ bgcolor: "#fff", px: 3, py: 1.25, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1.25, cursor: "pointer" }} onClick={() => navigate("/viewer")}>
          <TenantLogo
            url={resolveCompanyLogoUrl(me?.logo_url)}
            variant="brand"
            size={32}
            alt={me?.tenant_name ? `${me.tenant_name} logo` : "Company logo"}
          />
          <Box>
            <Typography sx={{ fontWeight: 700, fontSize: "1rem", lineHeight: 1.1 }}>
              {me?.tenant_name ?? "Reports"}
            </Typography>
            <Typography sx={{ fontSize: "0.72rem", color: "#6B7280" }}>Reports</Typography>
          </Box>
        </Box>
        {onReport && (
          <Button size="small" startIcon={<ArrowBack />} onClick={() => navigate(-1)}
            sx={{ textTransform: "none", color: "#374151" }}>
            Back
          </Button>
        )}
      </Box>
      {/* Line 2 — module navigation */}
      <Box sx={{ bgcolor: "#fff", borderBottom: "1px solid #E5E7EB", borderTop: "1px solid #F3F4F6", px: 2, py: 0.5, display: "flex", gap: 0.5, flexWrap: "wrap" }}>
        {modules.map(([mod, reports]) => <ModuleMenu key={mod} module={mod} reports={reports} />)}
      </Box>

      <Box sx={{ p: 3, minWidth: 0, maxWidth: "100%", boxSizing: "border-box" }}>
        {modules.length === 0
          ? <Typography variant="body2">No published reports yet.</Typography>
          : <Outlet />}
      </Box>
    </Box>
  );
}
