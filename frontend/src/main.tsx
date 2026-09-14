import React, { useEffect, useState } from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import { Box, CircularProgress, ThemeProvider, CssBaseline } from "@mui/material";
import theme from "./theme/theme";
import { App } from "./app/App";
import { captureHandoffToken, ensureActAsBaseline, getAccessToken, parseJwtPayload } from "./auth/session";
import { ensureSessionOnBoot, refreshAccessToken, scheduleProactiveRefresh } from "./auth/refresh";
import { SessionExpiredOverlay } from "./components/SessionExpiredOverlay";
import "./index.css";

// Capture the JWT handed off by the parent PHP platform BEFORE the app mounts.
captureHandoffToken();
ensureActAsBaseline();

const queryClient = new QueryClient();

function AuthBoot({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      await ensureSessionOnBoot();

      // Legacy tokens without logo claims: one refresh re-resolves branding from HRIS.
      const bootToken = getAccessToken();
      if (bootToken) {
        const payload = parseJwtPayload(bootToken);
        const hasLogo = payload?.logo_url || payload?.logo_file;
        if (!hasLogo && payload?.hris_origin && payload?.sid) {
          try {
            await refreshAccessToken();
          } catch {
            /* non-fatal */
          }
        }
      }

      scheduleProactiveRefresh();
      if (!cancelled) setReady(true);
    })();
    return () => { cancelled = true; };
  }, []);

  if (!ready) {
    return (
      <Box sx={{ minHeight: "100vh", display: "grid", placeItems: "center" }}>
        <CircularProgress size={28} />
      </Box>
    );
  }
  return <>{children}</>;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <SessionExpiredOverlay />
          <AuthBoot>
            <App />
          </AuthBoot>
        </BrowserRouter>
      </QueryClientProvider>
    </ThemeProvider>
  </React.StrictMode>,
);
