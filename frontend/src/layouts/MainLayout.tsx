// App shell matching the Payroll Process module: fixed left sidebar (logo box +
// nav) and a top AppBar. Teal #007499 accents, Inter, soft borders.
// Config / AI Settings are admin-only (Observations) and are not shown here.
import { type ReactNode, useEffect, useMemo, useState } from "react";
import { authApi, type Me } from "../api/client";
import {
  AppBar, Avatar, Box, Drawer, List, ListItemButton, ListItemIcon,
  ListItemText, Toolbar, Typography,
} from "@mui/material";
import {
  DescriptionOutlined, BuildOutlined, VisibilityOutlined,
  SchemaOutlined, ReceiptLongOutlined, AutoAwesomeOutlined,
} from "@mui/icons-material";
import { useNavigate, useLocation } from "react-router-dom";
import { TenantLogo, resolveCompanyLogoUrl } from "../components/TenantLogo";
import { DEFAULT_NAV_SECTION_FLAGS, isSectionAllowed, resolveNavFlags } from "../auth/navSections";
import { restoreBaseActAsTenant } from "../auth/session";

const DRAWER_WIDTH = 240;

const NAV = [
  { text: "Templates", icon: <DescriptionOutlined />, path: "/" },
  { text: "Chat", icon: <AutoAwesomeOutlined />, path: "/chat" },
  { text: "Builder", icon: <BuildOutlined />, path: "/builder" },
  { text: "Documents", icon: <ReceiptLongOutlined />, path: "/documents" },
  { text: "Viewer", icon: <VisibilityOutlined />, path: "/viewer" },
];
const FOOTER_NAV = [
  { text: "How it works", icon: <SchemaOutlined />, path: "/how-it-works" },
];

export function MainLayout({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const location = useLocation();
  const isActive = (path: string) =>
    path === "/" ? location.pathname === "/" : location.pathname.startsWith(path);
  const [me, setMe] = useState<Me | null>(null);
  const [meLoaded, setMeLoaded] = useState(false);
  useEffect(() => {
    // Drop any Observations act-as context so the builder always uses the
    // tenant this session was handed off for.
    restoreBaseActAsTenant();
    authApi.me()
      .then(setMe)
      .catch(() => setMe(null))
      .finally(() => setMeLoaded(true));
    const onRefresh = () => { authApi.me().then(setMe).catch(() => {}); };
    window.addEventListener("rb:token-refreshed", onRefresh);
    return () => window.removeEventListener("rb:token-refreshed", onRefresh);
  }, []);

  const navFlags = useMemo(
    () => (meLoaded ? resolveNavFlags(me?.nav_sections) : { ...DEFAULT_NAV_SECTION_FLAGS }),
    [me, meLoaded],
  );
  const visibleNav = useMemo(
    () => NAV.filter((item) => isSectionAllowed(navFlags, item.text)),
    [navFlags],
  );
  const visibleFooter = useMemo(
    () => FOOTER_NAV.filter((item) => isSectionAllowed(navFlags, item.text)),
    [navFlags],
  );

  const itemSx = (active: boolean) => ({
    borderRadius: 2, mb: 0.5, py: 1,
    color: active ? "#007499" : "#374151",
    bgcolor: active ? "#EAF4F7" : "transparent",
    "&:hover": { bgcolor: active ? "#EAF4F7" : "#F3F4F6" },
  });
  const NavItem = ({ item }: { item: { text: string; icon: ReactNode; path: string } }) => {
    const active = isActive(item.path);
    return (
      <ListItemButton onClick={() => navigate(item.path)} sx={itemSx(active)}>
        <ListItemIcon sx={{ minWidth: 36, color: active ? "#007499" : "#9CA3AF" }}>{item.icon}</ListItemIcon>
        <ListItemText primary={item.text} primaryTypographyProps={{ fontSize: "0.85rem", fontWeight: active ? 600 : 500 }} />
      </ListItemButton>
    );
  };

  return (
    <Box sx={{ display: "flex", height: "100vh", overflow: "hidden", bgcolor: "background.default" }}>
      <Drawer
        variant="permanent"
        sx={{
          width: DRAWER_WIDTH, flexShrink: 0,
          "& .MuiDrawer-paper": { width: DRAWER_WIDTH, boxSizing: "border-box", border: "none", borderRight: "1px solid #E5E7EB", bgcolor: "#fff" },
        }}
      >
        <Box sx={{ px: 2, py: 2.25, display: "flex", alignItems: "center", gap: 1.5, borderBottom: "1px solid #E5E7EB" }}>
          <TenantLogo
            url={resolveCompanyLogoUrl(me?.logo_url)}
            variant="brand"
            size={36}
            alt={me?.tenant_name ? `${me.tenant_name} logo` : "Company logo"}
          />
          <Box sx={{ minWidth: 0 }}>
            <Typography noWrap sx={{ fontWeight: 700, fontSize: "0.9rem", lineHeight: 1.1 }}>
              {me?.tenant_name ?? "Reports"}
            </Typography>
            <Typography sx={{ fontSize: "0.68rem", color: "#6B7280" }}>Report Builder</Typography>
          </Box>
        </Box>

        <List sx={{ px: 1.5, py: 1.5 }}>
          {visibleNav.map((item) => <NavItem key={item.path} item={item} />)}
          {visibleFooter.map((item) => <NavItem key={item.path} item={item} />)}
        </List>
      </Drawer>

      <Box sx={{ flexGrow: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        <AppBar position="sticky" elevation={0} sx={{ bgcolor: "#fff", color: "#1A1A1A", borderBottom: "1px solid #E5E7EB" }}>
          <Toolbar sx={{ minHeight: "60px !important", justifyContent: "space-between" }}>
            <Typography sx={{ fontWeight: 600, fontSize: "0.95rem" }}>
              {(me?.tenant_name ?? "Reports")} — Report Builder
            </Typography>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
              <Box sx={{ textAlign: "right" }}>
                <Typography sx={{ fontSize: "0.8rem", fontWeight: 600, lineHeight: 1.1 }}>
                  {me?.name ?? "…"}
                </Typography>
                <Typography sx={{ fontSize: "0.68rem", color: "#6B7280" }}>
                  {me ? `${me.designation}${me.tenant_name ? ` · ${me.tenant_name}` : ""}` : ""}
                </Typography>
              </Box>
              <Avatar sx={{ width: 34, height: 34, bgcolor: "#007499", fontSize: "0.85rem" }}>
                {(me?.name ?? "?").charAt(0).toUpperCase()}
              </Avatar>
            </Box>
          </Toolbar>
        </AppBar>
        <Box sx={{ p: 3, flexGrow: 1, minHeight: 0, minWidth: 0, maxWidth: "100%", overflow: "auto" }}>
          {children}
        </Box>
      </Box>
    </Box>
  );
}
