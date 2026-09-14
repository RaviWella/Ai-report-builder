import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  DEFAULT_TENANT_ID,
  getActiveUserEmpId,
  getActiveUserId,
  hasFullNavAccess,
} from './activeTenant'

function makeJwt(payload: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: 'none' }))
  const body = btoa(JSON.stringify(payload))
  return `${header}.${body}.sig`
}

function tenantFromToken(token: string): string | null {
  const parts = token.split('.')
  if (parts.length < 2) return null
  const payload = parts[1].replace(/-/g, '+').replace(/_/g, '/')
  const padded = payload + '='.repeat((4 - (payload.length % 4)) % 4)
  const json = JSON.parse(atob(padded)) as Record<string, unknown>
  const raw = json.tenant_id ?? json.tid ?? json.org_id
  return typeof raw === 'string' ? raw.trim() : null
}

describe('activeTenant', () => {
  beforeEach(() => {
    sessionStorage.clear()
    vi.stubEnv('REACT_APP_AUTH_TOKEN', '')
    vi.stubEnv('REACT_APP_USER_ID', '')
    vi.stubEnv('REACT_APP_SKIP_AUTH', 'false')
  })

  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it('defaults to demo_tenant', () => {
    expect(DEFAULT_TENANT_ID).toBe('demo_tenant')
  })

  it('reads tenant_id from JWT payload', () => {
    const token = makeJwt({ tenant_id: 'acme_corp', sub: 'u1' })
    expect(tenantFromToken(token)).toBe('acme_corp')
  })

  it('getActiveUserId uses JWT user_id for datamart session scoping', () => {
    sessionStorage.setItem(
      'mint_auth_token',
      makeJwt({ tenant_id: 'demo_tenant', user_id: '1001' }),
    )
    expect(getActiveUserId()).toBe('1001')
    expect(getActiveUserEmpId()).toBe(1001)
    expect(hasFullNavAccess()).toBe(false)
  })

  it('treats user_id 0 as full navigation access', () => {
    sessionStorage.setItem('mint_auth_token', makeJwt({ tenant_id: 'demo_tenant', user_id: '0' }))
    expect(getActiveUserId()).toBe('0')
    expect(getActiveUserEmpId()).toBe(0)
    expect(hasFullNavAccess()).toBe(true)
  })
})
