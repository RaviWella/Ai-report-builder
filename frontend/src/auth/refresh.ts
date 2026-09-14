import {
  getAccessToken,
  getTokenExp,
  isTokenExpired,
  markSessionExpired,
  setAccessToken,
  syncLogoFromToken,
  tokenSupportsRefresh,
} from "./session";

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api/v1";
/** Refresh this many seconds before JWT exp. */
const REFRESH_MARGIN_SEC = 120;
/** After a failed refresh, wait before trying again (avoids hammering HRIS/API). */
const REFRESH_FAIL_BACKOFF_MS = 30_000;

let refreshPromise: Promise<string> | null = null;
let proactiveTimer: ReturnType<typeof setTimeout> | null = null;
let visibilityHookInstalled = false;
let refreshFailBackoffUntil = 0;

class RefreshError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
    this.name = "RefreshError";
  }
}

function isRefreshUnauthorized(error: unknown): boolean {
  return error instanceof RefreshError && error.status === 401;
}

export async function refreshAccessToken(): Promise<string> {
  if (!tokenSupportsRefresh()) {
    throw new Error("Token does not support refresh");
  }

  if (Date.now() < refreshFailBackoffUntil) {
    throw new Error("Refresh backoff");
  }

  if (refreshPromise) return refreshPromise;

  refreshPromise = (async () => {
    const token = getAccessToken();
    if (!token) throw new Error("No access token");

    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!res.ok) {
      refreshFailBackoffUntil = Date.now() + REFRESH_FAIL_BACKOFF_MS;
      throw new RefreshError("Refresh failed", res.status);
    }

    refreshFailBackoffUntil = 0;
    const data = (await res.json()) as { access_token?: string };
    if (!data.access_token) throw new Error("No access_token in refresh response");

    setAccessToken(data.access_token);
    syncLogoFromToken(data.access_token);
    window.dispatchEvent(new CustomEvent("rb:token-refreshed"));
    scheduleNextRefresh();
    return data.access_token;
  })().finally(() => {
    refreshPromise = null;
  });

  return refreshPromise;
}

function clearProactiveTimer(): void {
  if (proactiveTimer !== null) {
    clearTimeout(proactiveTimer);
    proactiveTimer = null;
  }
}

function scheduleNextRefresh(): void {
  clearProactiveTimer();
  if (!tokenSupportsRefresh()) return;

  const exp = getTokenExp();
  if (!exp) return;

  const delayMs = Math.max(0, (exp - REFRESH_MARGIN_SEC) * 1000 - Date.now());
  proactiveTimer = setTimeout(() => {
    void runProactiveRefresh();
  }, delayMs);
}

/** Refresh now if the token is inside the pre-expiry window (or past it). */
async function runProactiveRefresh(): Promise<void> {
  if (!tokenSupportsRefresh()) return;

  const exp = getTokenExp();
  if (!exp) return;

  const secLeft = exp - Date.now() / 1000;
  // Too early — reschedule for the correct fire time.
  if (secLeft > REFRESH_MARGIN_SEC) {
    scheduleNextRefresh();
    return;
  }

  try {
    await refreshAccessToken();
  } catch (error) {
    // A refresh 401 means the HRIS session was rejected, even if access JWT
    // expiry has not arrived yet. Other failures remain retryable.
    if (isRefreshUnauthorized(error) || isTokenExpired(0)) {
      markSessionExpired();
    } else {
      clearProactiveTimer();
      proactiveTimer = setTimeout(() => {
        void runProactiveRefresh();
      }, REFRESH_FAIL_BACKOFF_MS);
    }
  }
}

function refreshOnTabVisible(): void {
  if (document.visibilityState !== "visible") return;
  if (!getAccessToken() || !tokenSupportsRefresh()) return;

  const exp = getTokenExp();
  if (!exp) return;

  const secLeft = exp - Date.now() / 1000;
  if (secLeft < REFRESH_MARGIN_SEC) {
    void runProactiveRefresh();
    return;
  }
  scheduleNextRefresh();
}

export function scheduleProactiveRefresh(): void {
  if (!getAccessToken() || !tokenSupportsRefresh()) return;
  scheduleNextRefresh();

  if (!visibilityHookInstalled) {
    visibilityHookInstalled = true;
    document.addEventListener("visibilitychange", refreshOnTabVisible);
  }
}

/**
 * Run once on app boot (after SSO hash capture). Refreshes an expired or
 * near-expiry token before React Query fires API calls — avoids a 401 storm
 * that shows "Session ended" while refresh would still succeed.
 */
export async function ensureSessionOnBoot(): Promise<void> {
  const token = getAccessToken();
  if (!token) return;

  if (!tokenSupportsRefresh()) {
    if (isTokenExpired(0)) markSessionExpired();
    return;
  }

  const exp = getTokenExp();
  if (!exp) return;

  const secLeft = exp - Date.now() / 1000;
  if (secLeft >= REFRESH_MARGIN_SEC) return;

  try {
    await refreshAccessToken();
  } catch (error) {
    if (isRefreshUnauthorized(error) || isTokenExpired(0)) {
      markSessionExpired();
    }
  }
}

/** Call when refresh is impossible or failed — show overlay only if the access token is dead. */
export async function handleAuthFailure(): Promise<void> {
  if (tokenSupportsRefresh()) {
    try {
      await refreshAccessToken();
      return;
    } catch (error) {
      if (!isRefreshUnauthorized(error) && !isTokenExpired(0)) return;
    }
  } else if (!isTokenExpired(0)) {
    return;
  }
  markSessionExpired();
}
