/**
 * DatabaseManager — source connection configuration UI for MintHRM.
 * Ported from mint-analytics DatabaseManager.tsx.
 * Lets HR analysts connect to any customer database (MySQL, PostgreSQL,
 * SQL Server) to run ad-hoc queries and build visualizations.
 *
 * v2: Supports designating any saved connection as the ETL source.
 */
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Plus, Database, ChevronDown, Table, X,
  Server, CheckCircle2, AlertCircle, Layers, Link2,
  FolderOpen, Folder, Trash2, RefreshCw, Activity,
  Zap, ZapOff,
} from 'lucide-react'
import clsx from 'clsx'
import { databaseConnectionService, type DatabaseConnectionOut, type TableInfo } from '../services/databaseConnectionService'
import { useToast } from '../components/ui/Toast'

// ── Constants ────────────────────────────────────────────────────

const DATABASE_ENGINES = [
  { value: 'postgres',  label: 'PostgreSQL', icon: '🐘', defaultPort: 5432 },
  { value: 'mysql',     label: 'MySQL',      icon: '🐬', defaultPort: 3306 },
  { value: 'sqlserver', label: 'SQL Server', icon: '📊', defaultPort: 1433 },
]

const ENGINE_COLORS: Record<string, { bg: string; text: string }> = {
  postgres:  { bg: 'bg-blue-100',   text: 'text-blue-700'   },
  mysql:     { bg: 'bg-orange-100', text: 'text-orange-700' },
  sqlserver: { bg: 'bg-red-100',    text: 'text-red-700'    },
}

const EMPTY_FORM = {
  name: '', engine: 'postgres', host: '', port: '5432',
  dbname: '', user: '', password: '',
  ssh_enabled: false, ssh_host: '', ssh_port: '22',
  ssh_username: '', ssh_auth_method: 'key' as 'key' | 'password',
  ssh_password: '', ssh_private_key: '', ssh_key_passphrase: '',
}

// ── Schema-grouped table list ────────────────────────────────────

function SchemaGroupedTables({ tables }: { tables: TableInfo[] }) {
  const groups = tables.reduce<Record<string, TableInfo[]>>((acc, t) => {
    const s = t.schema || '(no schema)'
    ;(acc[s] ??= []).push(t)
    return acc
  }, {})
  const schemas = Object.keys(groups).sort()
  const multi = schemas.length > 1
  const [open, setOpen] = useState<Set<string>>(() => new Set(schemas.slice(0, 1)))
  const toggle = (s: string) => setOpen(p => { const n = new Set(p); n.has(s) ? n.delete(s) : n.add(s); return n })

  return (
    <div>
      <h4 className="text-sm font-semibold text-slate-900 flex items-center gap-2 mb-4">
        <Layers className="w-4 h-4 text-slate-500" />
        Tables ({tables.length})
        {multi && <span className="text-xs font-normal text-slate-400">— {schemas.length} schemas</span>}
      </h4>
      <div className="space-y-4">
        {schemas.map(schema => {
          const isOpen = open.has(schema)
          return (
            <div key={schema}>
              {multi && (
                <button onClick={() => toggle(schema)} className="flex items-center gap-2 mb-2 w-full text-left">
                  {isOpen ? <FolderOpen className="w-4 h-4 text-amber-500" /> : <Folder className="w-4 h-4 text-amber-400" />}
                  <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">{schema}</span>
                  <span className="text-xs text-slate-400 bg-slate-200 px-1.5 py-0.5 rounded-full">{groups[schema].length}</span>
                  <ChevronDown className={clsx('w-3.5 h-3.5 text-slate-400 ml-auto transition-transform', !isOpen && '-rotate-90')} />
                </button>
              )}
              {(!multi || isOpen) && (
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                  {groups[schema].map(t => (
                    <div key={t.id} className="flex items-center gap-3 p-3 bg-white rounded-xl border border-slate-200 hover:border-teal-300 hover:shadow-md transition-all">
                      <div className="w-10 h-10 bg-slate-100 rounded-lg flex items-center justify-center">
                        <Table className="w-5 h-5 text-slate-500" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <span className="text-sm font-medium text-slate-900 truncate block">{t.display_name || t.name}</span>
                        <span className="text-xs text-slate-500">{t.field_count} columns</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Database card ────────────────────────────────────────────────

function DatabaseCard({
  db, isExpanded, onToggle, metadata, metaLoading, onDelete, onHealthCheck, isDeleting,
  isEtlSource, onSetEtlSource, onClearEtlSource, isSettingEtlSource,
}: {
  db: DatabaseConnectionOut
  isExpanded: boolean
  onToggle: () => void
  metadata?: { tables: TableInfo[] }
  metaLoading: boolean
  onDelete: () => void
  onHealthCheck: () => void
  isDeleting: boolean
  isEtlSource: boolean
  onSetEtlSource: () => void
  onClearEtlSource: () => void
  isSettingEtlSource: boolean
}) {
  const ec = ENGINE_COLORS[db.engine] ?? ENGINE_COLORS.postgres
  const engineLabel = DATABASE_ENGINES.find(e => e.value === db.engine)?.label ?? db.engine

  return (
    <div className={clsx(
      'bg-white rounded-xl border transition-all duration-200',
      isEtlSource
        ? 'border-teal-400 shadow-md shadow-teal-100 ring-1 ring-teal-300'
        : 'border-slate-200 hover:shadow-lg hover:shadow-teal-100'
    )}>
      {/* ETL source banner */}
      {isEtlSource && (
        <div className="flex items-center gap-2 px-4 py-2 bg-teal-50 border-b border-teal-200 rounded-t-xl">
          <Zap className="w-3.5 h-3.5 text-teal-600" />
          <span className="text-xs font-semibold text-teal-700">Active ETL Source</span>
          <span className="text-xs text-teal-500 ml-auto">ETL runs pull data from this connection</span>
        </div>
      )}

      {/* Header row */}
      <div className="flex items-center justify-between p-4 cursor-pointer hover:bg-slate-50" onClick={onToggle}>
        <div className="flex items-center gap-4">
          <ChevronDown className={clsx('w-5 h-5 text-slate-400 transition-transform', !isExpanded && '-rotate-90')} />
          <div className={clsx('flex items-center justify-center w-12 h-12 rounded-xl', ec.bg)}>
            <Database className={clsx('w-6 h-6', ec.text)} />
          </div>
          <div>
            <h3 className="font-semibold text-slate-900">{db.name}</h3>
            <div className="flex items-center gap-3 mt-1">
              <span className={clsx('inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium', ec.bg, ec.text)}>
                {engineLabel}
              </span>
              <span className="text-xs text-slate-500">{db.host}:{db.port}/{db.database_name}</span>
              {db.ssh_enabled && (
                <span className="inline-flex items-center gap-1 text-xs text-teal-600 bg-teal-50 px-2 py-0.5 rounded-full">
                  <Server className="w-3 h-3" /> SSH
                </span>
              )}
              <span className="flex items-center gap-1 text-xs">
                {db.is_healthy !== false
                  ? <><CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" /><span className="text-emerald-600">Connected</span></>
                  : <><AlertCircle  className="w-3.5 h-3.5 text-red-500"     /><span className="text-red-600">Unhealthy</span></>}
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
          {/* ETL source toggle */}
          {isEtlSource ? (
            <button
              onClick={onClearEtlSource}
              disabled={isSettingEtlSource}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-teal-700 bg-teal-100 hover:bg-teal-200 rounded-lg transition-colors disabled:opacity-50"
              title="Remove as ETL source"
            >
              <ZapOff className="w-3.5 h-3.5" />
              ETL Source
            </button>
          ) : (
            <button
              onClick={onSetEtlSource}
              disabled={isSettingEtlSource}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-600 bg-slate-100 hover:bg-teal-100 hover:text-teal-700 rounded-lg transition-colors disabled:opacity-50"
              title="Use as ETL source"
            >
              <Zap className="w-3.5 h-3.5" />
              Set ETL Source
            </button>
          )}
          <button
            onClick={onHealthCheck}
            className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
            title="Check connection health"
          >
            <Activity className="w-4 h-4 text-slate-400 hover:text-teal-600 transition-colors" />
          </button>
          <button
            onClick={() => { if (confirm(`Delete "${db.name}"? This cannot be undone.`)) onDelete() }}
            disabled={isDeleting}
            className="p-2 hover:bg-red-50 rounded-lg transition-colors"
            title="Delete connection"
          >
            <Trash2 className="w-4 h-4 text-slate-400 hover:text-red-500 transition-colors" />
          </button>
        </div>
      </div>

      {/* Expanded table browser */}
      {isExpanded && (
        <div className="border-t border-slate-200 p-4 bg-slate-50">
          {metaLoading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
              {Array.from({ length: 8 }).map((_, i) => (
                <div key={i} className="flex items-center gap-3 p-3 bg-white rounded-xl border border-slate-200 animate-pulse">
                  <div className="w-10 h-10 bg-slate-200 rounded-lg" />
                  <div className="flex-1 space-y-2">
                    <div className="h-3.5 bg-slate-200 rounded w-3/4" />
                    <div className="h-2.5 bg-slate-100 rounded w-1/2" />
                  </div>
                </div>
              ))}
            </div>
          ) : metadata ? (
            <SchemaGroupedTables tables={metadata.tables} />
          ) : null}
        </div>
      )}
    </div>
  )
}

// ── Add Connection Modal ─────────────────────────────────────────

function AddConnectionModal({
  onClose,
  onSubmit,
  isPending,
  isError,
  errorMessage,
}: {
  onClose: () => void
  onSubmit: (form: typeof EMPTY_FORM) => void
  isPending: boolean
  isError: boolean
  errorMessage: string
}) {
  const [form, setForm] = useState({ ...EMPTY_FORM })
  const set = (patch: Partial<typeof EMPTY_FORM>) => setForm(f => ({ ...f, ...patch }))

  const handleEngineChange = (engine: string) => {
    const def = DATABASE_ENGINES.find(e => e.value === engine)
    set({ engine, port: String(def?.defaultPort ?? 5432) })
  }

  const canSubmit = form.name && form.host && form.dbname && form.user && form.password

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">

        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between sticky top-0 bg-white z-10">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-teal-100 rounded-xl">
              <Database className="w-5 h-5 text-teal-600" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-slate-900">Add Database Connection</h2>
              <p className="text-sm text-slate-500">Connect a new data source</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-slate-100 rounded-lg transition-colors">
            <X className="w-5 h-5 text-slate-400" />
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-4 space-y-4">

          {/* Display name */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Display Name</label>
            <input
              type="text" value={form.name}
              onChange={e => set({ name: e.target.value })}
              className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 focus:bg-white transition-all"
              placeholder="My HR Database"
            />
          </div>

          {/* Engine picker */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Database Type</label>
            <div className="grid grid-cols-3 gap-2 mb-2">
              {DATABASE_ENGINES.map(e => (
                <button
                  key={e.value}
                  onClick={() => handleEngineChange(e.value)}
                  className={clsx(
                    'flex items-center gap-2 p-3 rounded-xl border-2 text-sm font-medium transition-all',
                    form.engine === e.value
                      ? 'border-teal-500 bg-teal-50 text-teal-700'
                      : 'border-slate-200 hover:border-slate-300 text-slate-700'
                  )}
                >
                  <span className="text-lg">{e.icon}</span>
                  {e.label}
                </button>
              ))}
            </div>
          </div>

          {/* Host + Port */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Host</label>
              <input
                type="text" value={form.host}
                onChange={e => set({ host: e.target.value })}
                className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 focus:bg-white transition-all"
                placeholder="localhost"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Port</label>
              <input
                type="number" value={form.port}
                onChange={e => set({ port: e.target.value })}
                className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 focus:bg-white transition-all"
              />
            </div>
          </div>

          {/* Database name */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Database Name</label>
            <input
              type="text" value={form.dbname}
              onChange={e => set({ dbname: e.target.value })}
              className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 focus:bg-white transition-all"
              placeholder="hrm_db"
            />
          </div>

          {/* Username */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Username</label>
            <input
              type="text" value={form.user}
              onChange={e => set({ user: e.target.value })}
              className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 focus:bg-white transition-all"
              placeholder="db_user"
            />
          </div>

          {/* Password */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Password</label>
            <input
              type="password" value={form.password}
              onChange={e => set({ password: e.target.value })}
              className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 focus:bg-white transition-all"
              placeholder="••••••••"
            />
          </div>

          {/* SSH Tunnel */}
          <details className="rounded-xl border border-slate-200 bg-slate-50 group" open={form.ssh_enabled}>
            <summary className="flex items-center justify-between cursor-pointer px-4 py-3 text-sm font-medium text-slate-700 select-none">
              <span className="flex items-center gap-2">
                <Server className="w-4 h-4 text-slate-500" />
                SSH Tunnel
                {form.ssh_enabled && (
                  <span className="text-xs px-2 py-0.5 rounded-full bg-teal-100 text-teal-700">enabled</span>
                )}
              </span>
              <ChevronDown className="w-4 h-4 text-slate-400 transition-transform group-open:rotate-180" />
            </summary>
            <div className="px-4 pb-4 space-y-3">
              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox" checked={form.ssh_enabled}
                  onChange={e => set({ ssh_enabled: e.target.checked })}
                  className="rounded border-slate-300 text-teal-600 focus:ring-teal-500"
                />
                Connect through an SSH bastion
              </label>

              {form.ssh_enabled && (
                <>
                  <div className="grid grid-cols-3 gap-3">
                    <div className="col-span-2">
                      <label className="block text-xs font-medium text-slate-600 mb-1">Bastion Host</label>
                      <input
                        type="text" value={form.ssh_host}
                        onChange={e => set({ ssh_host: e.target.value })}
                        className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
                        placeholder="bastion.example.com"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-slate-600 mb-1">Port</label>
                      <input
                        type="number" value={form.ssh_port}
                        onChange={e => set({ ssh_port: e.target.value })}
                        className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
                        placeholder="22"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1">SSH Username</label>
                    <input
                      type="text" value={form.ssh_username}
                      onChange={e => set({ ssh_username: e.target.value })}
                      className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
                      placeholder="ubuntu"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1">Auth Method</label>
                    <div className="flex gap-4 text-sm">
                      {(['key', 'password'] as const).map(m => (
                        <label key={m} className="flex items-center gap-2">
                          <input
                            type="radio" name="ssh_auth_method"
                            checked={form.ssh_auth_method === m}
                            onChange={() => set({ ssh_auth_method: m })}
                            className="text-teal-600 focus:ring-teal-500"
                          />
                          {m === 'key' ? 'Private Key' : 'Password'}
                        </label>
                      ))}
                    </div>
                  </div>

                  {form.ssh_auth_method === 'key' ? (
                    <>
                      <div>
                        <label className="block text-xs font-medium text-slate-600 mb-1">Private Key (PEM)</label>
                        <textarea
                          value={form.ssh_private_key}
                          onChange={e => set({ ssh_private_key: e.target.value })}
                          rows={5}
                          className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-xs font-mono focus:outline-none focus:ring-2 focus:ring-teal-500"
                          placeholder={'-----BEGIN OPENSSH PRIVATE KEY-----\n...\n-----END OPENSSH PRIVATE KEY-----'}
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-slate-600 mb-1">
                          Key Passphrase <span className="text-slate-400">(optional)</span>
                        </label>
                        <input
                          type="password" value={form.ssh_key_passphrase}
                          onChange={e => set({ ssh_key_passphrase: e.target.value })}
                          className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
                          placeholder="••••••••"
                        />
                      </div>
                    </>
                  ) : (
                    <div>
                      <label className="block text-xs font-medium text-slate-600 mb-1">SSH Password</label>
                      <input
                        type="password" value={form.ssh_password}
                        onChange={e => set({ ssh_password: e.target.value })}
                        className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
                        placeholder="••••••••"
                      />
                    </div>
                  )}
                </>
              )}
            </div>
          </details>

          {isError && (
            <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 text-red-700 rounded-xl text-sm">
              <AlertCircle className="w-4 h-4 shrink-0" />
              {errorMessage || 'Failed to connect to the database'}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-100 bg-slate-50 flex justify-end gap-3 sticky bottom-0">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-200 rounded-xl transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={() => onSubmit(form)}
            disabled={isPending || !canSubmit}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-teal-600 hover:bg-teal-700 rounded-xl disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isPending ? (
              <>
                <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Connecting…
              </>
            ) : (
              <><Link2 className="w-4 h-4" />Connect Database</>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Main page ────────────────────────────────────────────────────

export default function DatabaseManager() {
  const qc = useQueryClient()
  const toast = useToast()
  const [showAdd, setShowAdd] = useState(false)
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [search, setSearch] = useState('')

  const { data: connections = [], isLoading } = useQuery({
    queryKey: ['connections'],
    queryFn: databaseConnectionService.list,
  })

  const { data: etlSource } = useQuery({
    queryKey: ['etl-source'],
    queryFn: databaseConnectionService.getEtlSource,
  })

  const { data: metadata, isLoading: metaLoading } = useQuery({
    queryKey: ['connection-metadata', expandedId],
    queryFn: () => databaseConnectionService.getMetadata(expandedId!),
    enabled: !!expandedId,
  })

  const createMutation = useMutation({
    mutationFn: databaseConnectionService.create,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['connections'] })
      toast.success('Database connected', 'Your connection has been saved')
      setShowAdd(false)
    },
    onError: (err: Error) => {
      toast.error('Connection failed', err.message)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => databaseConnectionService.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['connections'] })
      qc.invalidateQueries({ queryKey: ['etl-source'] })
      toast.success('Connection removed')
      setExpandedId(null)
    },
    onError: () => toast.error('Delete failed'),
  })

  const healthMutation = useMutation({
    mutationFn: (id: number) => databaseConnectionService.checkHealth(id),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['connections'] })
      res.success
        ? toast.success('Connection healthy', 'Database is reachable')
        : toast.error('Connection unhealthy', res.message)
    },
  })

  const setEtlSourceMutation = useMutation({
    mutationFn: (id: number | null) => databaseConnectionService.setEtlSource(id),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['etl-source'] })
      if (res.source_connection_id) {
        toast.success('ETL source updated', `"${res.source_connection_name}" is now the active ETL source`)
      } else {
        toast.success('ETL source cleared', 'Reverted to legacy inline connection settings')
      }
    },
    onError: (err: Error) => toast.error('Failed to update ETL source', err.message),
  })

  const handleCreate = (form: typeof EMPTY_FORM) => {
    createMutation.mutate({
      name: form.name,
      engine: form.engine as 'postgres' | 'mysql' | 'sqlserver',
      host: form.host,
      port: parseInt(form.port, 10),
      database_name: form.dbname,
      username: form.user,
      password: form.password,
      ssh_enabled: form.ssh_enabled,
      ...(form.ssh_enabled && {
        ssh_host: form.ssh_host,
        ssh_port: parseInt(form.ssh_port, 10) || 22,
        ssh_username: form.ssh_username,
        ssh_auth_method: form.ssh_auth_method,
        ssh_password: form.ssh_auth_method === 'password' ? form.ssh_password : undefined,
        ssh_private_key: form.ssh_auth_method === 'key' ? form.ssh_private_key : undefined,
        ssh_key_passphrase: form.ssh_auth_method === 'key' ? form.ssh_key_passphrase : undefined,
      }),
    })
  }

  const filtered = connections.filter(c =>
    c.name.toLowerCase().includes(search.toLowerCase()) ||
    c.host.toLowerCase().includes(search.toLowerCase())
  )
  const healthy = connections.filter(c => c.is_healthy !== false).length
  const activeEtlId = etlSource?.source_connection_id ?? null

  return (
    <div className="p-6 space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800 flex items-center gap-2">
            <Database className="w-6 h-6 text-teal-600" />
            Database Connections
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Connect to any customer database to run ad-hoc queries and build HR visualizations.
            Mark one connection as the <strong>ETL Source</strong> to drive the HR data pipeline.
          </p>
        </div>
        <button
          onClick={() => setShowAdd(true)}
          className="flex items-center gap-2 px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white text-sm font-medium rounded-xl transition-colors shadow-sm"
        >
          <Plus className="w-4 h-4" />
          Add Database
        </button>
      </div>

      {/* ETL source banner */}
      {etlSource && (
        <div className={clsx(
          'flex items-center gap-3 px-4 py-3 rounded-xl border text-sm',
          etlSource.source_connection_id
            ? 'bg-teal-50 border-teal-200 text-teal-800'
            : 'bg-amber-50 border-amber-200 text-amber-800'
        )}>
          {etlSource.source_connection_id ? (
            <>
              <Zap className="w-4 h-4 text-teal-600 shrink-0" />
              <span>
                ETL source: <strong>{etlSource.source_connection_name}</strong>
                <span className="ml-2 text-xs opacity-70">({etlSource.source_connection_engine})</span>
              </span>
              <button
                onClick={() => setEtlSourceMutation.mutate(null)}
                disabled={setEtlSourceMutation.isPending}
                className="ml-auto text-xs text-teal-600 hover:text-teal-800 underline"
              >
                Clear
              </button>
            </>
          ) : (
            <>
              <AlertCircle className="w-4 h-4 text-amber-500 shrink-0" />
              <span>No dynamic ETL source set — using legacy inline connection from tenant registry.</span>
            </>
          )}
        </div>
      )}

      {/* Stats bar */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: 'Total Connections', value: connections.length, color: 'text-teal-600' },
          { label: 'Healthy',           value: healthy,            color: 'text-emerald-600' },
          { label: 'Unhealthy',         value: connections.length - healthy, color: 'text-red-500' },
        ].map(s => (
          <div key={s.label} className="bg-white rounded-xl border border-slate-200 p-4">
            <p className="text-xs text-slate-500 uppercase tracking-wide">{s.label}</p>
            <p className={clsx('text-2xl font-bold mt-1', s.color)}>{s.value}</p>
          </div>
        ))}
      </div>

      {/* Search */}
      <div className="relative">
        <input
          type="text" value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search connections…"
          className="w-full pl-10 pr-4 py-2.5 bg-white border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 transition-all"
        />
        <RefreshCw className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
      </div>

      {/* Connection list */}
      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-20 bg-white rounded-xl border border-slate-200 animate-pulse" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 bg-white rounded-2xl border border-slate-200">
          <div className="w-16 h-16 bg-teal-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <Database className="w-8 h-8 text-teal-600" />
          </div>
          <h3 className="text-xl font-semibold text-slate-900 mb-2">
            {search ? 'No connections found' : 'No databases connected'}
          </h3>
          <p className="text-slate-500 mb-6 max-w-sm mx-auto">
            {search ? 'Try a different search term' : 'Add your first database connection to start analyzing HR data'}
          </p>
          {!search && (
            <button
              onClick={() => setShowAdd(true)}
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-teal-600 text-white font-medium rounded-xl hover:bg-teal-700 transition-colors"
            >
              <Plus className="w-5 h-5" />
              Add Database
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          {filtered.map(conn => (
            <DatabaseCard
              key={conn.id}
              db={conn}
              isExpanded={expandedId === conn.id}
              onToggle={() => setExpandedId(expandedId === conn.id ? null : conn.id)}
              metadata={expandedId === conn.id ? metadata : undefined}
              metaLoading={expandedId === conn.id && metaLoading}
              onDelete={() => deleteMutation.mutate(conn.id)}
              onHealthCheck={() => healthMutation.mutate(conn.id)}
              isDeleting={deleteMutation.isPending}
              isEtlSource={activeEtlId === conn.id}
              onSetEtlSource={() => setEtlSourceMutation.mutate(conn.id)}
              onClearEtlSource={() => setEtlSourceMutation.mutate(null)}
              isSettingEtlSource={setEtlSourceMutation.isPending}
            />
          ))}
        </div>
      )}

      {/* Add modal */}
      {showAdd && (
        <AddConnectionModal
          onClose={() => setShowAdd(false)}
          onSubmit={handleCreate}
          isPending={createMutation.isPending}
          isError={createMutation.isError}
          errorMessage={(createMutation.error as Error)?.message ?? ''}
        />
      )}
    </div>
  )
}
