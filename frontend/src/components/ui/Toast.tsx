import { createContext, useContext, useState, useCallback, ReactNode } from 'react'
import { CheckCircle, AlertCircle, AlertTriangle, Info, X } from 'lucide-react'
import clsx from 'clsx'

export type ToastType = 'success' | 'error' | 'warning' | 'info'

interface Toast {
  id: string
  type: ToastType
  title: string
  message?: string
  duration?: number
}

interface ToastContextType {
  toasts: Toast[]
  addToast: (toast: Omit<Toast, 'id'>) => void
  removeToast: (id: string) => void
  success: (title: string, message?: string) => void
  error: (title: string, message?: string) => void
  warning: (title: string, message?: string) => void
  info: (title: string, message?: string) => void
}

const ToastContext = createContext<ToastContextType | null>(null)

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within a ToastProvider')
  return ctx
}

const CONFIG = {
  success: {
    icon: <CheckCircle className="w-4 h-4" aria-hidden />,
    iconBg: 'bg-emerald-100',
    iconColor: 'text-emerald-700',
    frame: 'border-emerald-200 bg-white',
    title: 'text-emerald-950',
    message: 'text-emerald-900/80',
  },
  error: {
    icon: <AlertCircle className="w-4 h-4" aria-hidden />,
    iconBg: 'bg-red-100',
    iconColor: 'text-red-700',
    frame: 'border-red-200 bg-white',
    title: 'text-red-950',
    message: 'text-red-900/80',
  },
  warning: {
    icon: <AlertTriangle className="w-4 h-4" aria-hidden />,
    iconBg: 'bg-amber-100',
    iconColor: 'text-amber-700',
    frame: 'border-amber-200 bg-white',
    title: 'text-amber-950',
    message: 'text-amber-900/80',
  },
  info: {
    icon: <Info className="w-4 h-4" aria-hidden />,
    iconBg: 'bg-teal-100',
    iconColor: 'text-teal-700',
    frame: 'border-teal-200 bg-white',
    title: 'text-teal-950',
    message: 'text-teal-900/80',
  },
}

function ToastItem({ toast, onRemove }: { toast: Toast; onRemove: () => void }) {
  const c = CONFIG[toast.type]
  return (
    <div
      role="status"
      className={clsx(
        'rounded-lg border p-3 min-w-[280px] max-w-sm shadow-sm',
        c.frame,
      )}
    >
      <div className="flex items-start gap-2.5">
        <div className={clsx('p-1.5 rounded-md flex-shrink-0', c.iconBg, c.iconColor)}>
          {c.icon}
        </div>
        <div className="flex-1 min-w-0 pt-0.5">
          <p className={clsx('text-sm font-medium', c.title)}>{toast.title}</p>
          {toast.message && (
            <p className={clsx('text-xs mt-0.5', c.message)}>{toast.message}</p>
          )}
        </div>
        <button
          type="button"
          onClick={onRemove}
          aria-label="Dismiss notification"
          className="p-0.5 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded transition-colors flex-shrink-0 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-teal-600"
        >
          <X className="w-3.5 h-3.5" aria-hidden />
        </button>
      </div>
    </div>
  )
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const removeToast = useCallback((id: string) => setToasts(p => p.filter(t => t.id !== id)), [])

  const addToast = useCallback((toast: Omit<Toast, 'id'>) => {
    const id = Math.random().toString(36).substring(2, 9)
    setToasts(p => [...p, { ...toast, id }])
    const dur = toast.duration ?? 4000
    if (dur > 0) setTimeout(() => removeToast(id), dur)
  }, [removeToast])

  const success = useCallback((title: string, message?: string) => addToast({ type: 'success', title, message }), [addToast])
  const error   = useCallback((title: string, message?: string) => addToast({ type: 'error',   title, message, duration: 6000 }), [addToast])
  const warning = useCallback((title: string, message?: string) => addToast({ type: 'warning', title, message }), [addToast])
  const info    = useCallback((title: string, message?: string) => addToast({ type: 'info',    title, message }), [addToast])

  return (
    <ToastContext.Provider value={{ toasts, addToast, removeToast, success, error, warning, info }}>
      {children}
      <div
        className="fixed bottom-4 right-4 flex flex-col gap-2"
        style={{ zIndex: 'var(--z-toast, 50)' }}
        aria-live="polite"
        aria-relevant="additions"
      >
        {toasts.map(t => <ToastItem key={t.id} toast={t} onRemove={() => removeToast(t.id)} />)}
      </div>
    </ToastContext.Provider>
  )
}
