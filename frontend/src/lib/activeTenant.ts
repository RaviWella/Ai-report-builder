/**
 * Active MintHRM tenant for API headers (warehouse + datamart).
 *
 * Resolution order:
 * 1. Explicit tenant from login (`setActiveTenantId`)
 * 2. `tenant_id` claim from Bearer JWT (session or env)
 * 3. `REACT_APP_TENANT_ID` (dev)
 * 4. `demo_tenant`
 */
import { AUTH_TOKEN, SKIP_AUTH, TENANT_ID as ENV_TENANT_ID, USER_ID as ENV_USER_ID } from '../env'

export const DEFAULT_TENANT_ID = 'demo_tenant'

const STORAGE_TENANT_KEY = 'mint_active_tenant_id'
const STORAGE_TOKEN_KEY = 'mint_auth_token'

function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const parts = token.split('.')
    if (parts.length < 2) return null
    const payload = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    const padded = payload + '='.repeat((4 - (payload.length % 4)) % 4)
    const json = JSON.parse(atob(padded)) as Record<string, unknown>
    return json && typeof json === 'object' ? json : null
  } catch {
    return null
  }
}

function tenantIdFromJwt(token: string): string | null {
  const json = decodeJwtPayload(token)
  if (!json) return null
  const raw = json.tenant_id ?? json.tid ?? json.org_id
  if (typeof raw !== 'string') return null
  const tid = raw.trim()
  return tid || null
}

/** MinHRM `user_emp_id` is stored in JWT as `user_id` (string). */
export function userIdFromJwt(token: string): string | null {
  const json = decodeJwtPayload(token)
  if (!json) return null
  const raw = json.user_id ?? json.user_emp_id ?? json.employee_id ?? json.uid ?? json.sub
  if (raw == null) return null
  const id = String(raw).trim()
  return id || null
}

function userEmpIdFromJwt(token: string): number | null {
  const id = userIdFromJwt(token)
  if (!id) return null
  const n = Number(id)
  return Number.isFinite(n) ? n : null
}

export function getStoredAuthToken(): string | null {
  const fromEnv = (AUTH_TOKEN || '').trim()
  if (typeof window === 'undefined') {
    return fromEnv || null
  }
  const fromSession = window.sessionStorage.getItem(STORAGE_TOKEN_KEY)?.trim()
  return fromSession || fromEnv || null
}

export function setStoredAuthToken(token: string): void {
  if (typeof window === 'undefined') return
  const t = token.trim()
  if (t) {
    window.sessionStorage.setItem(STORAGE_TOKEN_KEY, t)
  } else {
    window.sessionStorage.removeItem(STORAGE_TOKEN_KEY)
  }
}

/** Resolve tenant without reading localStorage override (JWT / env / default). */
export function resolveTenantFromAuth(): string {
  const token = getStoredAuthToken()
  if (token) {
    const fromJwt = tenantIdFromJwt(token)
    if (fromJwt) return fromJwt
  }
  const fromEnv = (ENV_TENANT_ID || '').trim()
  if (fromEnv) return fromEnv
  return DEFAULT_TENANT_ID
}

/** Active user id for API headers and datamart session scoping (from JWT or env). */
export function getActiveUserId(): string | null {
  const token = getStoredAuthToken()
  if (token) {
    const fromJwt = userIdFromJwt(token)
    if (fromJwt) return fromJwt
  }
  const fromEnv = (ENV_USER_ID || '').trim()
  return fromEnv || null
}

/**
 * MinHRM launch maps `user_emp_id` → JWT `user_id`.
 * `0` = warehouse admin (full navigation); any other value = customized reports only.
 */
export function getActiveUserEmpId(): number | null {
  const token = getStoredAuthToken()
  if (token) {
    const fromJwt = userEmpIdFromJwt(token)
    if (fromJwt != null) return fromJwt
  }
  const fromEnv = (ENV_USER_ID || '').trim()
  if (fromEnv) {
    const n = Number(fromEnv)
    if (Number.isFinite(n)) return n
  }
  return null
}

export function hasFullNavAccess(): boolean {
  const empId = getActiveUserEmpId()
  if (empId === null) {
    return SKIP_AUTH
  }
  return empId === 0
}

export function getActiveTenantId(): string {
  if (typeof window !== 'undefined') {
    const stored = window.localStorage.getItem(STORAGE_TENANT_KEY)?.trim()
    if (stored) return stored
  }
  return resolveTenantFromAuth()
}

export function setActiveTenantId(tenantId: string): void {
  const tid = tenantId.trim()
  if (!tid) return
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(STORAGE_TENANT_KEY, tid)
  }
}

export function clearActiveTenantId(): void {
  if (typeof window !== 'undefined') {
    window.localStorage.removeItem(STORAGE_TENANT_KEY)
  }
}

/**
 * After login: persist token + tenant so API uses the user's warehouse (`hrm_wh_*`).
 */
export function applyUserAuth(
  tenantId: string,
  authToken?: string | null,
  opts?: { reloadPage?: boolean },
): void {
  setActiveTenantId(tenantId.trim() || DEFAULT_TENANT_ID)
  const token = authToken ?? getStoredAuthToken()
  if (token) {
    setStoredAuthToken(token)
  }
  if (opts?.reloadPage && typeof window !== 'undefined') {
    window.location.reload()
  }
}

/** @deprecated Use applyUserAuth */
export function applyActiveTenantSwitch(
  tenantId: string,
  opts?: { reloadPage?: boolean },
): void {
  applyUserAuth(tenantId, null, opts)
}

/** On app load: if no explicit tenant, align localStorage with JWT tenant when present. */
export function syncActiveTenantFromAuth(): string {
  const resolved = resolveTenantFromAuth()
  if (typeof window === 'undefined') {
    return resolved
  }
  const stored = window.localStorage.getItem(STORAGE_TENANT_KEY)?.trim()
  if (!stored && resolved !== DEFAULT_TENANT_ID) {
    window.localStorage.setItem(STORAGE_TENANT_KEY, resolved)
  }
  return getActiveTenantId()
}
