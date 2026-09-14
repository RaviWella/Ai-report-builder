export type TenantBranding = {
  company_name?: string | null;
  logo_url?: string | null;
};

const STORAGE_KEY = "mint_tenant_branding";

export function setTenantBranding(branding: TenantBranding): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(branding));
}

export function getTenantBranding(): TenantBranding | null {
  if (typeof window === "undefined") return null;
  const raw = window.sessionStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as TenantBranding;
  } catch {
    return null;
  }
}

export function clearTenantBranding(): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.removeItem(STORAGE_KEY);
}
