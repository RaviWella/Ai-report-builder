/**
 * SourceConnection — configure the ETL source database (MintHRM MySQL / Postgres).
 */
import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Database, CheckCircle2, AlertCircle, Link2, Save } from 'lucide-react'
import clsx from 'clsx'
import { useToast } from '../components/ui/Toast'
import { TENANT_ID } from '../env'
import {
  tenantSourceService,
  type SourceType,
  type TenantSourcePayload,
} from '../services/tenantSourceService'

const SOURCE_TYPES: { value: SourceType; label: string; icon: string; port: number }[] = [
  { value: 'mysql', label: 'MySQL / MintHRM', icon: '🐬', port: 3306 },
  { value: 'postgres', label: 'PostgreSQL', icon: '🐘', port: 5432 },
]

const EMPTY = {
  display_name: '',
  source_type: 'mysql' as SourceType,
  mysql_host: '',
  mysql_port: '3306',
  mysql_db: '',
  mysql_user: '',
  mysql_password: '',
}

function apiErrorMessage(err: unknown): string {
  if (err && typeof err === 'object' && 'response' in err) {
    const detail = (err as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return detail.map((d: { msg?: string }) => d.msg ?? '').filter(Boolean).join(', ')
    }
  }
  return err instanceof Error ? err.message : 'Request failed'
}

export default function SourceConnection() {
  const qc = useQueryClient()
  const toast = useToast()
  const [form, setForm] = useState({ ...EMPTY })
  const set = (patch: Partial<typeof EMPTY>) => setForm(f => ({ ...f, ...patch }))

  const { data: source, isLoading } = useQuery({
    queryKey: ['tenant-source'],
    queryFn: tenantSourceService.get,
  })

  useEffect(() => {
    if (!source?.configured) return
    setForm({
      display_name: source.display_name ?? '',
      source_type: (source.source_type as SourceType) || 'mysql',
      mysql_host: source.mysql_host ?? '',
      mysql_port: String(source.mysql_port ?? (source.source_type === 'postgres' ? 5432 : 3306)),
      mysql_db: source.mysql_db ?? '',
      mysql_user: source.mysql_user ?? '',
      mysql_password: '',
    })
  }, [source])

  const testMutation = useMutation({
    mutationFn: () =>
      tenantSourceService.test({
        source_type: form.source_type,
        mysql_host: form.mysql_host,
        mysql_port: parseInt(form.mysql_port, 10) || undefined,
        mysql_db: form.mysql_db,
        mysql_user: form.mysql_user,
        mysql_password: form.mysql_password,
      }),
    onSuccess: res => toast.success('Connection successful', res.message),
    onError: err => toast.error('Connection failed', apiErrorMessage(err)),
  })

  const saveMutation = useMutation({
    mutationFn: () => {
      const payload: TenantSourcePayload = {
        display_name: form.display_name || `MintHRM (${form.mysql_db})`,
        source_type: form.source_type,
        mysql_host: form.mysql_host,
        mysql_port: parseInt(form.mysql_port, 10) || undefined,
        mysql_db: form.mysql_db,
        mysql_user: form.mysql_user,
      }
      if (form.mysql_password) payload.mysql_password = form.mysql_password
      return tenantSourceService.save(payload)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tenant-source'] })
      toast.success('Source saved', 'ETL will use this database on the next run')
      set({ mysql_password: '' })
    },
    onError: err => toast.error('Save failed', apiErrorMessage(err)),
  })

  const handleEngineChange = (st: SourceType) => {
    const def = SOURCE_TYPES.find(s => s.value === st)
    set({ source_type: st, mysql_port: String(def?.port ?? 3306) })
  }

  const needsPassword = !source?.configured && !form.mysql_password
  const canTest =
    form.mysql_host && form.mysql_db && form.mysql_user && form.mysql_password
  const canSave =
    form.mysql_host &&
    form.mysql_db &&
    form.mysql_user &&
    (form.mysql_password || source?.has_password)

  return (
    <div className="p-6 max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-800 flex items-center gap-2">
          <Database className="w-6 h-6 text-teal-600" />
          Source Database
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Connect your MintHRM (or HR) source. ETL reads from here and loads into the PostgreSQL
          analytics warehouse — this is not the warehouse itself.
        </p>
      </div>

      <div className="flex items-center gap-2 text-xs text-slate-500 bg-slate-100 rounded-lg px-3 py-2">
        <span className="font-medium text-slate-600">Tenant:</span> {TENANT_ID}
        {source?.extractor_profile && (
          <>
            <span className="text-slate-300">|</span>
            <span>Extractor: {source.extractor_profile}</span>
          </>
        )}
      </div>

      {source?.configured && (
        <div className="flex items-start gap-3 p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-sm">
          <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
          <div>
            <p className="font-medium text-emerald-900">Source configured</p>
            <p className="text-emerald-700 mt-0.5">
              {source.mysql_user}@{source.mysql_host}:{source.mysql_port}/{source.mysql_db}
              {source.last_etl_at && (
                <span className="block text-emerald-600 text-xs mt-1">
                  Last ETL: {new Date(source.last_etl_at).toLocaleString()}
                </span>
              )}
            </p>
          </div>
        </div>
      )}

      {!source?.configured && !isLoading && (
        <div className="flex items-start gap-3 p-4 bg-amber-50 border border-amber-200 rounded-xl text-sm">
          <AlertCircle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
          <div>
            <p className="font-medium text-amber-900">No source configured</p>
            <p className="text-amber-700 mt-0.5">
              Enter your MintHRM MySQL credentials, then test and save before running ETL.
            </p>
          </div>
        </div>
      )}

      <div className="bg-white border border-slate-200 rounded-2xl p-6 space-y-4 shadow-sm">
        {isLoading ? (
          <p className="text-slate-400 text-sm animate-pulse">Loading…</p>
        ) : (
          <>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Display name</label>
              <input
                type="text"
                value={form.display_name}
                onChange={e => set({ display_name: e.target.value })}
                className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
                placeholder="Production MintHRM"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Source type</label>
              <div className="grid grid-cols-2 gap-2">
                {SOURCE_TYPES.map(t => (
                  <button
                    key={t.value}
                    type="button"
                    onClick={() => handleEngineChange(t.value)}
                    className={clsx(
                      'flex items-center gap-2 p-3 rounded-xl border-2 text-sm font-medium transition-all',
                      form.source_type === t.value
                        ? 'border-teal-500 bg-teal-50 text-teal-700'
                        : 'border-slate-200 hover:border-slate-300 text-slate-700'
                    )}
                  >
                    <span className="text-lg">{t.icon}</span>
                    {t.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">Host</label>
                <input
                  type="text"
                  value={form.mysql_host}
                  onChange={e => set({ mysql_host: e.target.value })}
                  className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
                  placeholder="172.x.x.x"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">Port</label>
                <input
                  type="number"
                  value={form.mysql_port}
                  onChange={e => set({ mysql_port: e.target.value })}
                  className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Database name</label>
              <input
                type="text"
                value={form.mysql_db}
                onChange={e => set({ mysql_db: e.target.value })}
                className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Username</label>
              <input
                type="text"
                value={form.mysql_user}
                onChange={e => set({ mysql_user: e.target.value })}
                className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">
                Password
                {source?.has_password && (
                  <span className="text-slate-400 font-normal ml-1">(leave blank to keep)</span>
                )}
              </label>
              <input
                type="password"
                value={form.mysql_password}
                onChange={e => set({ mysql_password: e.target.value })}
                className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
              />
              {needsPassword && (
                <p className="text-xs text-amber-600 mt-1">Password required for first-time setup</p>
              )}
            </div>

            <div className="flex flex-wrap gap-3 pt-2 border-t border-slate-100">
              <button
                type="button"
                onClick={() => testMutation.mutate()}
                disabled={!canTest || testMutation.isPending}
                className="flex items-center gap-2 px-4 py-2.5 border border-slate-200 rounded-xl text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
              >
                <Link2 className="w-4 h-4" />
                {testMutation.isPending ? 'Testing…' : 'Test connection'}
              </button>
              <button
                type="button"
                onClick={() => saveMutation.mutate()}
                disabled={!canSave || saveMutation.isPending}
                className="flex items-center gap-2 px-4 py-2.5 bg-teal-600 hover:bg-teal-700 text-white rounded-xl text-sm font-medium disabled:opacity-50"
              >
                <Save className="w-4 h-4" />
                {saveMutation.isPending ? 'Saving…' : 'Save source'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
