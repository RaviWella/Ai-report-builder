/** Resolve API base URL (build-time env + production split-host fallback). */
const CONFIGURED_API_BASE_URL = process.env.REACT_APP_API_BASE_URL || "";
const CONFIGURED_API_KEY =
  process.env.REACT_APP_API_KEY ||
  (process.env.NODE_ENV === "development" ? "hrm-dev-api-key" : "");
const CONFIGURED_TENANT_ID = process.env.REACT_APP_TENANT_ID || "demo_tenant";
const CONFIGURED_AUTH_TOKEN = process.env.REACT_APP_AUTH_TOKEN || "";
const CONFIGURED_USER_ID =
  process.env.REACT_APP_USER_ID ||
  (process.env.NODE_ENV === "development" ? "default-user" : "");
const CONFIGURED_HR_CURRENCY = process.env.REACT_APP_HR_CURRENCY || "LKR";

function resolveApiBaseUrl(): string {
  const trimmed = CONFIGURED_API_BASE_URL.replace(/\/$/, "");
  if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
    return trimmed;
  }
  // Production: UI and API on separate subdomains (see DEPLOYMENT_GUIDE).
  if (typeof window !== "undefined") {
    const { hostname, protocol } = window.location;
    if (hostname === "mint-analytics-new.minchy.ai") {
      return `${protocol}//mint-analytics-new-api.minchy.ai/api/v1`;
    }
  }
  return trimmed || "/api/v1";
}

export const API_BASE_URL = resolveApiBaseUrl();

export const API_KEY = CONFIGURED_API_KEY;

export const TENANT_ID = CONFIGURED_TENANT_ID;

/** Optional Bearer JWT when MOCK_AUTH_ENABLED=false on API (Phase 9). */
export const AUTH_TOKEN = CONFIGURED_AUTH_TOKEN;

/** Optional X-User-Id for workspace row scoping (matches token user_id when using JWT). */
export const USER_ID = CONFIGURED_USER_ID;

/** Local dev: skip HRIS launch gate; API uses MOCK_AUTH_ENABLED + X-Tenant-Id. */
export const SKIP_AUTH =
  (process.env.REACT_APP_SKIP_AUTH || "").toLowerCase() === "true";

/** When true, new questions show a grounding preview before chat (table confirm). */
export const DATAMART_GROUNDING_CONFIRM =
  (process.env.REACT_APP_DATAMART_GROUNDING_CONFIRM || "false").toLowerCase() ===
  "true";

/** ISO 4217 code for payroll / currency metrics (MintHRM default: LKR). */
export const HR_CURRENCY = CONFIGURED_HR_CURRENCY;
