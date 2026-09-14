/**
 * Source databases for ETL — add and manage MySQL / PostgreSQL upstream systems.
 */
import { useState, type ReactNode } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Database,
  Plus,
  Trash2,
  Star,
  Server,
  AlertCircle,
  X,
  ChevronRight,
  ChevronDown,
} from 'lucide-react'
import clsx from 'clsx'
import { Link } from 'react-router-dom'
import { useToast } from '../components/ui/Toast'
import {
  etlSourcesService,
  type SourceDatabase,
  type SourceDatabaseCreate,
} from '../services/etlSourcesService'
import { registeredSources } from '../utils/etlSourceScenarios'

const SOURCE_TYPES = [
  { value: 'postgres' as const, label: 'PostgreSQL', defaultPort: 5432 },
  { value: 'mysql' as const, label: 'MySQL', defaultPort: 3306 },
] as const

type SourceForm = {
  source_key: string
  display_name: string
  source_type: 'mysql' | 'postgres'
  host: string
  port: string
  database_name: string
  username: string
  password: string
  source_schema: string
  extractor_profile: string
  is_primary: boolean
}

const EMPTY_FORM: SourceForm = {
  source_key: '',
  display_name: '',
  source_type: 'mysql',
  host: '',
  port: '3306',
  database_name: '',
  username: '',
  password: '',
  source_schema: '',
  extractor_profile: 'minthrm',
  is_primary: true,
}

function slugifyKey(name: string): string {
  return name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_|_$/g, '')
    .slice(0, 48)
}

function inputClass() {
  return 'w-full mt-1.5 px-3 py-2.5 border border-slate-200 rounded-lg text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-teal-500/30 focus:border-teal-500'
}

function labelClass() {
  return 'block text-sm font-medium text-slate-700'
}

function SourceCard({
  source,
  onDelete,
  isDeleting,
}: {
  source: SourceDatabase
  onDelete: () => void
  isDeleting: boolean
}) {
  const isLegacyInline =
    source.id === 0 && (!source.connection_id || source.connection_id === 0)
  const typeLabel = source.source_type === 'postgres' ? 'PostgreSQL' : 'MySQL'

  return (
    <article
      className={clsx(
        'rounded-xl border p-4 sm:p-5',
        source.is_primary
          ? 'border-teal-200 bg-teal-50/30'
          : 'border-slate-200 bg-white',
        isLegacyInline && 'border-amber-200 bg-amber-50/40',
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Database
              className={clsx(
                'w-4 h-4 shrink-0',
                source.is_primary ? 'text-teal-700' : 'text-slate-500',
              )}
              aria-hidden
            />
            <h3 className="font-semibold text-slate-900 truncate">
              {source.display_name}
            </h3>
            {source.is_primary && (
              <span className="inline-flex items-center gap-1 text-xs font-medium text-teal-800 bg-teal-100 px-2 py-0.5 rounded-full">
                <Star className="w-3 h-3 fill-teal-700 text-teal-700" aria-hidden />
                Primary
              </span>
            )}
            <span className="text-xs font-medium text-slate-600 bg-slate-100 px-2 py-0.5 rounded-full">
              {typeLabel}
            </span>
          </div>

          {isLegacyInline ? (
            <p className="text-sm text-amber-900 mt-2">
              Legacy configuration. Add a new source to replace this.
            </p>
          ) : (
            <p className="text-sm text-slate-600 mt-2 flex items-center gap-2">
              <Server className="w-4 h-4 text-slate-500 shrink-0" aria-hidden />
              <span className="truncate font-mono text-xs sm:text-sm">
                {source.username}@{source.host}:{source.port}/{source.database_name}
              </span>
            </p>
          )}

          {!isLegacyInline && source.source_schema && (
            <p className="text-xs text-slate-600 mt-1.5">
              Schema: <span className="font-mono">{source.source_schema}</span>
            </p>
          )}
        </div>

        <button
          type="button"
          onClick={onDelete}
          disabled={isDeleting}
          className="shrink-0 p-2 text-slate-600 rounded-lg transition-colors hover:text-red-900 hover:ring-1 hover:ring-red-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-red-600 disabled:opacity-50"
          title="Remove source"
          aria-label={`Remove ${source.display_name}`}
        >
          <Trash2 className="w-4 h-4" aria-hidden />
        </button>
      </div>
    </article>
  )
}

function FormSection({
  title,
  description,
  children,
}: {
  title: string
  description?: string
  children: ReactNode
}) {
  return (
    <section className="space-y-3">
      <div>
        <h3 className="text-sm font-semibold text-slate-800">{title}</h3>
        {description && <p className="text-xs text-slate-500 mt-0.5">{description}</p>}
      </div>
      {children}
    </section>
  )
}

function AddSourceModal({
  onClose,
  onSaved,
}: {
  onClose: () => void
  onSaved: () => void
}) {
  const toast = useToast()
  const [form, setForm] = useState<SourceForm>({ ...EMPTY_FORM })
  const [testing, setTesting] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const set = (p: Partial<SourceForm>) => setForm(f => ({ ...f, ...p }))

  const handleTypeChange = (source_type: 'mysql' | 'postgres') => {
    const def = SOURCE_TYPES.find(t => t.value === source_type)
    set({
      source_type,
      port: String(def?.defaultPort ?? 5432),
      extractor_profile: source_type === 'postgres' ? 'generic' : 'minthrm',
      source_schema: source_type === 'postgres' ? form.source_schema : '',
    })
  }

  const handleDisplayNameChange = (display_name: string) => {
    const next: Partial<SourceForm> = { display_name }
    if (!form.source_key.trim() || form.source_key === slugifyKey(form.display_name)) {
      next.source_key = slugifyKey(display_name)
    }
    set(next)
  }

  const buildPayload = (): SourceDatabaseCreate => ({
    source_key: form.source_key.trim(),
    display_name: form.display_name.trim(),
    source_type: form.source_type,
    host: form.host.trim(),
    port: parseInt(form.port, 10) || (form.source_type === 'postgres' ? 5432 : 3306),
    database_name: form.database_name.trim(),
    username: form.username.trim(),
    password: form.password,
    source_schema: form.source_schema.trim() || undefined,
    extractor_profile: form.extractor_profile,
    is_primary: form.is_primary,
    priority: form.is_primary ? 0 : 10,
  })

  const canTest =
    form.host.trim() && form.database_name.trim() && form.username.trim() && form.password.trim()

  const canSubmit =
    form.source_key.trim() &&
    form.display_name.trim() &&
    canTest &&
    (form.source_type !== 'postgres' || form.source_schema.trim())

  const handleTest = async () => {
    setTesting(true)
    try {
      const p = buildPayload()
      const res = await etlSourcesService.test({
        source_type: p.source_type,
        host: p.host,
        port: p.port,
        database_name: p.database_name,
        username: p.username,
        password: p.password,
        source_schema: p.source_schema,
      })
      if (res.success) toast.success('Connection successful', res.message)
      else toast.error('Connection failed', res.message)
    } catch (e) {
      toast.error('Connection failed', e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setTesting(false)
    }
  }

  const saveMutation = useMutation({
    mutationFn: () => etlSourcesService.create(buildPayload()),
    onSuccess: () => {
      toast.success('Source saved', 'It will be included in the next ETL run')
      onSaved()
      onClose()
    },
    onError: (e: Error) => toast.error('Could not save source', e.message),
  })

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4">
      <div
        className="absolute inset-0 bg-slate-900/50 backdrop-blur-[2px]"
        onClick={onClose}
        aria-hidden
      />
      <div
        role="dialog"
        aria-labelledby="add-source-title"
        className="relative bg-white rounded-t-2xl sm:rounded-2xl shadow-xl w-full sm:max-w-lg max-h-[92vh] flex flex-col"
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
          <div>
            <h2 id="add-source-title" className="text-lg font-semibold text-slate-900">
              Add source database
            </h2>
            <p className="text-sm text-slate-500 mt-0.5">Credentials are stored encrypted</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-2 hover:bg-slate-100 rounded-lg text-slate-500"
            aria-label="Close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-5 space-y-6">
          <FormSection title="Database type">
            <div className="grid grid-cols-2 gap-2">
              {SOURCE_TYPES.map(t => (
                <button
                  key={t.value}
                  type="button"
                  onClick={() => handleTypeChange(t.value)}
                  className={clsx(
                    'py-3 px-4 rounded-lg border text-sm font-medium transition-all text-left',
                    form.source_type === t.value
                      ? 'border-teal-500 bg-teal-50 text-teal-900 ring-1 ring-teal-500/20'
                      : 'border-slate-200 text-slate-700 hover:border-slate-300 hover:bg-slate-50'
                  )}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </FormSection>

          <FormSection
            title="Connection"
            description="Host and database your HR data lives in"
          >
            <div className="space-y-3">
              <div>
                <label className={labelClass()} htmlFor="src-display-name">
                  Name
                </label>
                <input
                  id="src-display-name"
                  className={inputClass()}
                  placeholder="e.g. Production HR"
                  value={form.display_name}
                  onChange={e => handleDisplayNameChange(e.target.value)}
                />
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div className="col-span-2">
                  <label className={labelClass()} htmlFor="src-host">
                    Host
                  </label>
                  <input
                    id="src-host"
                    className={inputClass()}
                    placeholder="db.example.com"
                    value={form.host}
                    onChange={e => set({ host: e.target.value })}
                  />
                </div>
                <div>
                  <label className={labelClass()} htmlFor="src-port">
                    Port
                  </label>
                  <input
                    id="src-port"
                    type="number"
                    className={inputClass()}
                    value={form.port}
                    onChange={e => set({ port: e.target.value })}
                  />
                </div>
              </div>
              <div>
                <label className={labelClass()} htmlFor="src-db">
                  Database name
                </label>
                <input
                  id="src-db"
                  className={inputClass()}
                  value={form.database_name}
                  onChange={e => set({ database_name: e.target.value })}
                />
              </div>
              {form.source_type === 'postgres' && (
                <div>
                  <label className={labelClass()} htmlFor="src-schema">
                    Schema <span className="text-red-500">*</span>
                  </label>
                  <input
                    id="src-schema"
                    className={inputClass()}
                    placeholder="customer_schema"
                    value={form.source_schema}
                    onChange={e => set({ source_schema: e.target.value })}
                  />
                </div>
              )}
            </div>
          </FormSection>

          <FormSection title="Sign in" description="Read-only user recommended">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className={labelClass()} htmlFor="src-user">
                  Username
                </label>
                <input
                  id="src-user"
                  className={inputClass()}
                  autoComplete="off"
                  value={form.username}
                  onChange={e => set({ username: e.target.value })}
                />
              </div>
              <div>
                <label className={labelClass()} htmlFor="src-pass">
                  Password
                </label>
                <input
                  id="src-pass"
                  type="password"
                  className={inputClass()}
                  autoComplete="new-password"
                  value={form.password}
                  onChange={e => set({ password: e.target.value })}
                />
              </div>
            </div>
          </FormSection>

          <label className="flex items-center gap-3 p-3 rounded-lg border border-slate-200 bg-slate-50/80 cursor-pointer">
            <input
              type="checkbox"
              className="rounded border-slate-300 text-teal-600 focus:ring-teal-500"
              checked={form.is_primary}
              onChange={e => set({ is_primary: e.target.checked })}
            />
            <span className="text-sm text-slate-700">
              <span className="font-medium text-slate-900">Primary source</span>
              <span className="block text-xs text-slate-500 mt-0.5">
                Use when this is the main HR database for staging tables
              </span>
            </span>
          </label>

          <div>
            <button
              type="button"
              onClick={() => setShowAdvanced(v => !v)}
              className="flex items-center gap-1.5 text-sm font-medium text-slate-600 hover:text-slate-900"
            >
              {showAdvanced ? (
                <ChevronDown className="w-4 h-4" />
              ) : (
                <ChevronRight className="w-4 h-4" />
              )}
              Advanced options
            </button>
            {showAdvanced && (
              <div className="mt-3 space-y-3 p-3 rounded-lg border border-slate-100 bg-slate-50/50">
                <div>
                  <label className={labelClass()} htmlFor="src-key">
                    Internal ID
                  </label>
                  <input
                    id="src-key"
                    className={inputClass()}
                    value={form.source_key}
                    onChange={e => set({ source_key: e.target.value })}
                  />
                  <p className="text-xs text-slate-500 mt-1">Used internally by ETL; lowercase letters, numbers, underscores</p>
                </div>
                <div>
                  <label className={labelClass()} htmlFor="src-profile">
                    Extractor profile
                  </label>
                  <select
                    id="src-profile"
                    className={inputClass()}
                    value={form.extractor_profile}
                    onChange={e => set({ extractor_profile: e.target.value })}
                  >
                    <option value="generic">Generic (PostgreSQL / custom layout)</option>
                    <option value="minthrm">MintHRM (legacy MySQL layout)</option>
                  </select>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="border-t border-slate-100 px-5 py-4 flex flex-col-reverse sm:flex-row sm:justify-end gap-2 bg-slate-50/80 rounded-b-2xl">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2.5 text-sm font-medium text-slate-600 hover:bg-slate-200/80 rounded-lg"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleTest}
            disabled={testing || !canTest}
            className="px-4 py-2.5 text-sm font-medium text-teal-800 bg-teal-100 hover:bg-teal-200/80 rounded-lg disabled:opacity-50"
          >
            {testing ? 'Testing…' : 'Test connection'}
          </button>
          <button
            type="button"
            onClick={() => saveMutation.mutate()}
            disabled={saveMutation.isPending || !canSubmit}
            className="px-4 py-2.5 text-sm font-medium text-white bg-teal-600 hover:bg-teal-700 rounded-lg disabled:opacity-50"
          >
            {saveMutation.isPending ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function EtlSources() {
  const qc = useQueryClient()
  const toast = useToast()
  const [showAdd, setShowAdd] = useState(false)

  const { data: sources = [], isLoading } = useQuery({
    queryKey: ['etl-sources'],
    queryFn: etlSourcesService.list,
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => etlSourcesService.remove(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['etl-sources'] })
      qc.invalidateQueries({ queryKey: ['tenant-source'] })
      toast.success('Source removed')
    },
    onError: (e: Error) => toast.error('Delete failed', e.message),
  })

  const registered = registeredSources(sources)
  const legacyOnly = sources.length > 0 && registered.length === 0
  const primary = registered.find(s => s.is_primary)
  const mysqlCount = registered.filter(s => s.source_type === 'mysql').length
  const postgresCount = registered.filter(s => s.source_type === 'postgres').length

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      <header className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
            Source databases
          </h1>
          <p className="text-sm text-slate-600 mt-1.5 leading-relaxed max-w-lg">
            Connect the HR systems you want to pull data from. After saving, run ETL from{' '}
            <Link to="/etl/control" className="text-teal-600 hover:text-teal-700 font-medium">
              ETL Control
            </Link>
            .
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowAdd(true)}
          className="inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 shadow-sm shrink-0"
        >
          <Plus className="w-4 h-4" />
          Add database
        </button>
      </header>

      {registered.length > 0 && (
        <p className="text-sm text-slate-600 bg-slate-50 border border-slate-200 rounded-lg px-4 py-3">
          <span className="font-medium text-slate-800">{registered.length}</span>
          {registered.length === 1 ? ' database' : ' databases'} connected
          {mysqlCount > 0 && (
            <span>
              {' '}
              · {mysqlCount} MySQL
            </span>
          )}
          {postgresCount > 0 && (
            <span>
              {' '}
              · {postgresCount} PostgreSQL
            </span>
          )}
          {primary && (
            <span>
              {' '}
              · Primary: <span className="font-medium">{primary.display_name}</span>
            </span>
          )}
        </p>
      )}

      {legacyOnly && (
        <div className="flex gap-3 px-4 py-3 rounded-lg border border-amber-200 bg-amber-50 text-sm text-amber-900">
          <AlertCircle className="w-5 h-5 shrink-0 text-amber-600 mt-0.5" />
          <p>Legacy configuration detected. Add a new source to use the current setup flow.</p>
        </div>
      )}

      {isLoading ? (
        <div className="space-y-3">
          {[1, 2].map(i => (
            <div
              key={i}
              className="h-24 bg-white border border-slate-200 rounded-xl animate-pulse"
            />
          ))}
        </div>
      ) : sources.length === 0 ? (
        <div className="text-center py-16 bg-white rounded-xl border border-dashed border-slate-300">
          <div className="w-12 h-12 rounded-full bg-teal-50 flex items-center justify-center mx-auto mb-4">
            <Database className="w-6 h-6 text-teal-600" />
          </div>
          <h2 className="text-lg font-semibold text-slate-900">No sources yet</h2>
          <p className="text-sm text-slate-500 mt-1 max-w-sm mx-auto">
            Add your MySQL or PostgreSQL HR database to start loading data into the warehouse.
          </p>
          <button
            type="button"
            onClick={() => setShowAdd(true)}
            className="mt-6 inline-flex items-center gap-2 px-4 py-2.5 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700"
          >
            <Plus className="w-4 h-4" />
            Add your first database
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {sources.map(s => (
            <SourceCard
              key={s.id || s.source_key}
              source={s}
              onDelete={() => {
                if (confirm(`Remove "${s.display_name}"? This deletes stored credentials.`)) {
                  deleteMutation.mutate(s.id)
                }
              }}
              isDeleting={deleteMutation.isPending}
            />
          ))}
        </div>
      )}

      {showAdd && (
        <AddSourceModal
          onClose={() => setShowAdd(false)}
          onSaved={() => {
            qc.invalidateQueries({ queryKey: ['etl-sources'] })
            qc.invalidateQueries({ queryKey: ['tenant-source'] })
          }}
        />
      )}
    </div>
  )
}
