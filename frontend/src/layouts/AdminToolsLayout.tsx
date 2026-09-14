// Admin console shell for Permission handler + Observations.
// Intentionally separate from the Report Builder MainLayout sidebar.
import { type ReactNode, useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import {
  AppBar, Avatar, Box, Drawer, List, ListItemButton, ListItemIcon,
  ListItemText, Toolbar, Typography,
} from "@mui/material";
import {
  AdminPanelSettingsOutlined, TravelExploreOutlined,
} from "@mui/icons-material";
import { authApi, type Me } from "../api/client";
import { TenantLogo, resolveCompanyLogoUrl } from "../components/TenantLogo";
import { restoreBaseActAsTenant } from "../auth/session";

const DRAWER_WIDTH = 260;

const NAV = [
  {
    text: "Permission handler",
    path: "/settings/permissions",
    icon: <AdminPanelSettingsOutlined />,
  },
  {
    text: "Observations",
    path: "/settings/observations",
    icon: <TravelExploreOutlined />,
  },
];

export function AdminToolsLayout({ children }: { children?: ReactNode }) {
  const location = useLocation();
  const [me, setMe] = useState<Me | null>(null);

  useEffect(() => {
    authApi.me().then(setMe).catch(() => setMe(null));
  }, []);

  // Permission handler should not keep a cross-tenant act-as context.
  useEffect(() => {
    if (location.pathname.startsWith("/settings/permissions")) {
      restoreBaseActAsTenant();
    }
  }, [location.pathname]);

  const isActive = (path: string) =>
    path === "/settings/observations"
      ? location.pathname.startsWith("/settings/observations")
      : location.pathname === path || location.pathname.startsWith(`${path}/`);

  const itemSx = (active: boolean) => ({
    borderRadius: 2,
    mb: 0.5,
    py: 1,
    color: active ? "#007499" : "#374151",
    bgcolor: active ? "#EAF4F7" : "transparent",
    "&:hover": { bgcolor: active ? "#EAF4F7" : "#F3F4F6" },
  });

  return (
    <Box sx={{ display: "flex", height: "100vh", overflow: "hidden", bgcolor: "background.default" }}>
      <Drawer
        variant="permanent"
        sx={{
          width: DRAWER_WIDTH,
          flexShrink: 0,
          "& .MuiDrawer-paper": {
            width: DRAWER_WIDTH,
            boxSizing: "border-box",
            border: "none",
            borderRight: "1px solid #E5E7EB",
            bgcolor: "#fff",
          },
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
              Admin tools
            </Typography>
            <Typography sx={{ fontSize: "0.68rem", color: "#6B7280" }}>Report Builder</Typography>
          </Box>
        </Box>

        <List sx={{ px: 1.5, py: 1.5 }}>
          {NAV.map((item) => {
            const active = isActive(item.path);
            return (
              <ListItemButton
                key={item.path}
                component={NavLink}
                to={item.path}
                end={item.path === "/settings/permissions"}
                sx={itemSx(active)}
              >
                <ListItemIcon sx={{ minWidth: 36, color: active ? "#007499" : "#9CA3AF" }}>
                  {item.icon}
                </ListItemIcon>
                <ListItemText
                  primary={item.text}
                  slotProps={{ primary: { fontSize: "0.85rem", fontWeight: active ? 600 : 500 } }}
                />
              </ListItemButton>
            );
          })}
        </List>
      </Drawer>

      <Box sx={{ flexGrow: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        <AppBar position="sticky" elevation={0} sx={{ bgcolor: "#fff", color: "#1A1A1A", borderBottom: "1px solid #E5E7EB" }}>
          <Toolbar sx={{ minHeight: "60px !important", justifyContent: "space-between" }}>
            <Typography sx={{ fontWeight: 600, fontSize: "0.95rem" }}>
              {(me?.tenant_name ?? "Reports")} — Admin tools
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
        <Box sx={{ p: 3, flexGrow: 1, minHeight: 0, overflow: "auto" }}>
          {children ?? <Outlet />}
        </Box>
      </Box>
    </Box>
  );
}
