// Company logo from HRIS (JWT `logo_url` / `logo_file` + `hris_origin`).
// Loads the public HRIS URL directly (Payroll Platform pattern); falls back to
// the authenticated /auth/company-logo proxy when direct load fails.
import { useCallback, useEffect, useState } from "react";
import { Box, Typography } from "@mui/material";
import { getAccessToken } from "../auth/session";

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api/v1";

export function resolveCompanyLogoUrl(meLogo?: string | null): string | null {
  const fromMe = meLogo?.trim();
  if (fromMe) return fromMe;
  return sessionStorage.getItem("company_logo_url")?.trim() || null;
}

export function TenantLogo({
  url,
  size = 34,
  alt = "Company logo",
  variant = "icon",
}: {
  url?: string | null;
  size?: number;
  alt?: string;
  variant?: "icon" | "brand";
}) {
  const logoUrl = url?.trim() || null;
  const isBrand = variant === "brand";
  const [src, setSrc] = useState<string | null>(logoUrl);
  const [failed, setFailed] = useState(false);
  const [proxyTried, setProxyTried] = useState(false);

  const tryProxy = useCallback(async () => {
    const token = getAccessToken();
    if (!token) {
      setFailed(true);
      return;
    }
    setProxyTried(true);
    try {
      const res = await fetch(`${API_BASE}/auth/company-logo`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        setFailed(true);
        return;
      }
      const blob = await res.blob();
      setSrc(URL.createObjectURL(blob));
    } catch {
      setFailed(true);
    }
  }, []);

  useEffect(() => {
    setFailed(false);
    setProxyTried(false);
    if (logoUrl) {
      setSrc(logoUrl);
      return;
    }
    // No URL in session yet — backend may still resolve logo from logo_file claim.
    if (getAccessToken()) {
      void tryProxy();
    } else {
      setSrc(null);
    }
  }, [logoUrl, tryProxy]);

  const handleError = useCallback(() => {
    if (src?.startsWith("blob:") || proxyTried) {
      setFailed(true);
      return;
    }
    void tryProxy();
  }, [src, proxyTried, tryProxy]);

  if (src && !failed) {
    return (
      <Box
        component="img"
        src={src}
        alt={alt}
        onError={handleError}
        referrerPolicy="no-referrer"
        sx={{
          width: isBrand ? "auto" : size,
          maxWidth: isBrand ? 140 : size,
          height: size,
          borderRadius: isBrand ? "6px" : "10px",
          objectFit: "contain",
          bgcolor: "#fff",
          border: isBrand ? "none" : "1px solid #E5E7EB",
          p: isBrand ? 0 : 0.25,
          flexShrink: 0,
        }}
      />
    );
  }

  return (
    <Box
      sx={{
        width: size,
        height: size,
        borderRadius: "10px",
        bgcolor: "#007499",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        flexShrink: 0,
      }}
    >
      <Typography sx={{ color: "#fff", fontWeight: 700, fontSize: size <= 32 ? "0.82rem" : "0.9rem" }}>
        AI
      </Typography>
    </Box>
  );
}
