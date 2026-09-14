import { useEffect, useState } from "react";
import { Box, Button, Typography } from "@mui/material";
import { getHrisOrigin } from "../auth/session";

function resumeHrisHref(origin: string): string {
  const path = `${window.location.pathname}${window.location.search}`;
  const base = origin.replace(/\/$/, "");
  return `${base}/site/resumeReportBuilder?rb_path=${encodeURIComponent(path)}`;
}

export function SessionExpiredOverlay() {
  const [open, setOpen] = useState(false);
  const [hrisHref, setHrisHref] = useState<string | null>(null);

  useEffect(() => {
    const onExpired = () => {
      const origin = getHrisOrigin();
      setHrisHref(origin ? resumeHrisHref(origin) : null);
      setOpen(true);
    };
    window.addEventListener("rb:session-expired", onExpired);
    return () => window.removeEventListener("rb:session-expired", onExpired);
  }, []);

  if (!open) return null;

  return (
    <Box
      sx={{
        position: "fixed",
        inset: 0,
        zIndex: 9999,
        bgcolor: "rgba(15, 23, 42, 0.55)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        p: 2,
      }}
    >
      <Box
        sx={{
          bgcolor: "#fff",
          borderRadius: 2,
          p: 3,
          maxWidth: 420,
          width: "100%",
          border: "1px solid #E5E7EB",
          textAlign: "center",
        }}
      >
        <Typography sx={{ fontWeight: 700, fontSize: "1.05rem", mb: 1 }}>
          Session ended
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2.5 }}>
          Sign in to MintHRM to continue on this report.
        </Typography>
        {hrisHref ? (
          <Button
            variant="contained"
            href={hrisHref}
            sx={{ bgcolor: "#007499", "&:hover": { bgcolor: "#005f7a" } }}
          >
            Return to MintHRM
          </Button>
        ) : (
          <Typography variant="caption" color="text.secondary">
            Close this tab and re-open Report Builder from MintHRM.
          </Typography>
        )}
      </Box>
    </Box>
  );
}
