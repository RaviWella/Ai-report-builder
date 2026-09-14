// SSO hand-off from the parent MintHRM (PHP) platform.
//
// The PHP app mints a short-lived JWT (signed with the SHARED JWT_SECRET) and
// redirects the browser to this SPA with the token in the URL *fragment*:
//
//   https://reports.minthrm.com/viewer#access_token=<JWT>&hris_origin=<url>&logo_url=<url?>
//
// The fragment (after '#') is never sent to the server. We read it once on boot,
// stash it in sessionStorage, then strip it from the URL.

const ACCESS_TOKEN_KEY = "access_token";
const HRIS_ORIGIN_KEY = "hris_origin";
const ACT_AS_KEY = "act_as_tenant";
// Act-as value this session was handed off with; Observations may temporarily
// override ACT_AS_KEY, so the baseline is kept to restore afterwards.
const ACT_AS_BASE_KEY = "act_as_tenant_base";
const LOGO_KEY = "company_logo_url";

export function getAccessToken(): string | null {
  return sessionStorage.getItem(ACCESS_TOKEN_KEY);
}

export function setAccessToken(token: string): void {
  sessionStorage.setItem(ACCESS_TOKEN_KEY, token);
}

export function getHrisOrigin(): string | null {
  return sessionStorage.getItem(HRIS_ORIGIN_KEY);
}

export function getTokenExp(): number | null {
  const token = getAccessToken();
  if (!token) return null;
  const payload = parseJwtPayload(token);
  const exp = payload?.exp;
  return typeof exp === "number" ? exp : null;
}

/** True when the JWT (or sessionStorage) carries HRIS refresh binding claims. */
export function tokenSupportsRefresh(token?: string | null): boolean {
  const t = token ?? getAccessToken();
  if (!t) return false;
  const payload = parseJwtPayload(t);
  if (!payload) return false;

  const hrisOrigin =
    (typeof payload.hris_origin === "string" && payload.hris_origin) || getHrisOrigin();
  const sid = payload.sid;
  const ver = payload.ver;

  return Boolean(hrisOrigin) && typeof sid === "string" && sid.length > 0 && ver !== undefined;
}

/** Whether the access token is past exp (+ optional leeway seconds). */
export function isTokenExpired(leewaySec = 0): boolean {
  const exp = getTokenExp();
  if (exp === null) return false;
  return Date.now() / 1000 > exp + leewaySec;
}

export function parseJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const part = token.split(".")[1];
    if (!part) return null;
    const padded = part.replace(/-/g, "+").replace(/_/g, "/");
    const json = decodeURIComponent(
      atob(padded)
        .split("")
        .map((c) => `%${(`00${c.charCodeAt(0).toString(16)}`).slice(-2)}`)
        .join(""),
    );
    return JSON.parse(json) as Record<string, unknown>;
  } catch {
    try {
      const part = token.split(".")[1];
      if (!part) return null;
      return JSON.parse(atob(part.replace(/-/g, "+").replace(/_/g, "/"))) as Record<string, unknown>;
    } catch {
      return null;
    }
  }
}

export function getActAsTenant(): string | null {
  return sessionStorage.getItem(ACT_AS_KEY);
}

/** Remember the hand-off act-as value once per session (empty string = none). */
export function ensureActAsBaseline(): void {
  if (sessionStorage.getItem(ACT_AS_BASE_KEY) === null) {
    sessionStorage.setItem(ACT_AS_BASE_KEY, sessionStorage.getItem(ACT_AS_KEY) ?? "");
  }
}

/** Restore the hand-off act-as value (used when leaving Observations). */
export function restoreBaseActAsTenant(): void {
  ensureActAsBaseline();
  const base = sessionStorage.getItem(ACT_AS_BASE_KEY) ?? "";
  if (base === (sessionStorage.getItem(ACT_AS_KEY) ?? "")) return;
  setActAsTenant(base || null);
}

/** Set or clear X-Act-As-Tenant for Observations (support admin cross-tenant). */
export function setActAsTenant(subdomain: string | null): void {
  if (subdomain && subdomain.trim()) {
    sessionStorage.setItem(ACT_AS_KEY, subdomain.trim());
  } else {
    sessionStorage.removeItem(ACT_AS_KEY);
  }
  window.dispatchEvent(new CustomEvent("rb:act-as-changed", { detail: { subdomain } }));
}

export function clearSession(): void {
  sessionStorage.removeItem(ACCESS_TOKEN_KEY);
  sessionStorage.removeItem(HRIS_ORIGIN_KEY);
  sessionStorage.removeItem(ACT_AS_KEY);
  sessionStorage.removeItem(ACT_AS_BASE_KEY);
  sessionStorage.removeItem(LOGO_KEY);
}

export function markSessionExpired(): void {
  const hrisOrigin = getHrisOrigin();
  clearSession();
  // Keep origin so the overlay can link back to HRIS after clearing auth state.
  if (hrisOrigin) sessionStorage.setItem(HRIS_ORIGIN_KEY, hrisOrigin);
  window.dispatchEvent(new CustomEvent("rb:session-expired"));
}

/** Persist logo URL from JWT claims (used after SSO hand-off and token refresh). */
export function syncLogoFromToken(token: string): void {
  const payload = parseJwtPayload(token);
  const logo = payload?.logo_url ?? payload?.company_logo_url;
  if (typeof logo === "string" && logo.trim()) {
    sessionStorage.setItem(LOGO_KEY, logo.trim());
    return;
  }
  const logoFile = payload?.logo_file ?? payload?.com_logo;
  const origin = payload?.hris_origin;
  if (
    typeof logoFile === "string"
    && logoFile.trim()
    && logoFile !== "0"
    && typeof origin === "string"
    && origin.trim()
  ) {
    sessionStorage.setItem(
      LOGO_KEY,
      `${origin.trim().replace(/\/$/, "")}/uploads/company/200/${logoFile.trim()}`,
    );
  }
}

export function captureHandoffToken(): void {
  const hash = window.location.hash.startsWith("#") ? window.location.hash.slice(1) : "";
  if (!hash) return;
  const params = new URLSearchParams(hash);
  const token = params.get("access_token");
  if (!token) return;

  setAccessToken(token);
  const hrisOrigin = params.get("hris_origin");
  if (hrisOrigin) sessionStorage.setItem(HRIS_ORIGIN_KEY, hrisOrigin);
  const actAs = params.get("act_as");
  if (actAs) sessionStorage.setItem(ACT_AS_KEY, actAs);
  const logoUrl = params.get("logo_url");
  if (logoUrl) {
    sessionStorage.setItem(LOGO_KEY, logoUrl);
  } else {
    syncLogoFromToken(token);
  }

  // Fallback: hris_origin may also be embedded in the JWT payload.
  if (!hrisOrigin) {
    const origin = parseJwtPayload(token)?.hris_origin;
    if (typeof origin === "string" && origin) {
      sessionStorage.setItem(HRIS_ORIGIN_KEY, origin);
    }
  }

  window.history.replaceState(null, "", window.location.pathname + window.location.search);
}
