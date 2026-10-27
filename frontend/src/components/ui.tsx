import { Check, Copy, Info, Loader2, TriangleAlert, X } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { useSession } from '../store/SessionContext'
import type { Severity, TaskStatus } from '../types'

export function Card({
  children,
  className = '',
  padded = true,
}: {
  children: ReactNode
  className?: string
  padded?: boolean
}) {
  return <section className={`card ${padded ? 'card-pad' : ''} ${className}`}>{children}</section>
}

export function SectionHeader({
  title,
  desc,
  action,
}: {
  title: string
  desc?: string
  action?: ReactNode
}) {
  return (
    <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h2 className="section-title">{title}</h2>
        {desc ? <p className="mt-1 text-sm text-slate-500">{desc}</p> : null}
      </div>
      {action}
    </div>
  )
}

export function EmptyState({
  title,
  desc,
  icon,
  action,
}: {
  title: string
  desc?: string
  icon?: ReactNode
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-slate-300 bg-slate-50/60 px-6 py-10 text-center">
      {icon ? <div className="mb-2 text-slate-400">{icon}</div> : null}
      <p className="text-sm font-medium text-slate-700">{title}</p>
      {desc ? <p className="mt-1 max-w-md text-xs leading-relaxed text-slate-500">{desc}</p> : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  )
}

export function Spinner({ className = '' }: { className?: string }) {
  return <Loader2 className={`h-4 w-4 animate-spin ${className}`} />
}

const STATUS_STYLE: Record<TaskStatus, string> = {
  RECEIVED: 'bg-slate-100 text-slate-700 border-slate-200',
  ANALYZING: 'bg-sky-50 text-sky-700 border-sky-200',
  NEED_INFO: 'bg-amber-50 text-amber-700 border-amber-200',
  GENERATING: 'bg-indigo-50 text-indigo-700 border-indigo-200',
  VALIDATING: 'bg-cyan-50 text-cyan-700 border-cyan-200',
  RETRYING: 'bg-orange-50 text-orange-700 border-orange-200',
  REVIEW_REQUIRED: 'bg-amber-100 text-amber-800 border-amber-300',
  SUCCESS: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  FAILED: 'bg-rose-50 text-rose-700 border-rose-200',
  BLOCKED: 'bg-rose-100 text-rose-800 border-rose-300',
}

export function StatusBadge({ status, label }: { status: TaskStatus | string; label?: string }) {
  const style = STATUS_STYLE[status as TaskStatus] ?? 'bg-slate-100 text-slate-700 border-slate-200'
  return (
    <span className={`chip border ${style}`}>
      <span className="h-1.5 w-1.5 rounded-full bg-current opacity-70" />
      {label ?? status}
    </span>
  )
}

export const SEVERITY_STYLE: Record<Severity, string> = {
  INFO: 'bg-slate-100 text-slate-600 border-slate-200',
  LOW: 'bg-sky-50 text-sky-700 border-sky-200',
  MEDIUM: 'bg-amber-50 text-amber-700 border-amber-200',
  HIGH: 'bg-orange-100 text-orange-800 border-orange-300',
  CRITICAL: 'bg-rose-100 text-rose-800 border-rose-300',
}

export const SEVERITY_LABEL: Record<Severity, string> = {
  INFO: '提示',
  LOW: '低风险',
  MEDIUM: '中风险',
  HIGH: '高风险',
  CRITICAL: '严重风险',
}

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span className={`chip border ${SEVERITY_STYLE[severity]}`}>
      {SEVERITY_LABEL[severity]} · {severity}
    </span>
  )
}

export function Toggle({
  checked,
  onChange,
  label,
  desc,
  disabled,
}: {
  checked: boolean
  onChange: (next: boolean) => void
  label: string
  desc?: string
  disabled?: boolean
}) {
  return (
    <label
      className={`flex cursor-pointer items-start gap-3 rounded-lg border border-slate-200 p-3 transition hover:border-slate-300 ${
        disabled ? 'cursor-not-allowed opacity-60' : ''
      }`}
    >
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={`mt-0.5 h-5 w-9 shrink-0 rounded-full p-0.5 transition ${
          checked ? 'bg-accent-500' : 'bg-slate-300'
        }`}
      >
        <span
          className={`block h-4 w-4 rounded-full bg-white shadow transition ${checked ? 'translate-x-4' : ''}`}
        />
      </button>
      <span>
        <span className="block text-sm font-medium text-slate-800">{label}</span>
        {desc ? <span className="mt-0.5 block text-xs leading-relaxed text-slate-500">{desc}</span> : null}
      </span>
    </label>
  )
}

export function CopyButton({ text, label = '复制' }: { text: string; label?: string }) {
  const [done, setDone] = useState(false)
  const { notify } = useSession()

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setDone(true)
      window.setTimeout(() => setDone(false), 1600)
    } catch {
      notify('error', '浏览器不允许访问剪贴板，请手动选择文本复制。')
    }
  }

  return (
    <button type="button" onClick={copy} className="btn-ghost !px-2.5 !py-1 !text-xs">
      {done ? <Check className="h-3.5 w-3.5 text-emerald-600" /> : <Copy className="h-3.5 w-3.5" />}
      {done ? '已复制' : label}
    </button>
  )
}

export function ToastHost() {
  const { toasts, dismissToast } = useSession()
  return (
    <div className="pointer-events-none fixed right-4 top-4 z-50 flex w-80 flex-col gap-2">
      {toasts.map((toast) => {
        const tone =
          toast.kind === 'success'
            ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
            : toast.kind === 'error'
              ? 'border-rose-200 bg-rose-50 text-rose-800'
              : 'border-sky-200 bg-sky-50 text-sky-800'
        const Icon = toast.kind === 'success' ? Check : toast.kind === 'error' ? TriangleAlert : Info
        return (
          <div
            key={toast.id}
            className={`pointer-events-auto flex items-start gap-2 rounded-lg border px-3 py-2.5 text-sm shadow-card ${tone}`}
            role="status"
          >
            <Icon className="mt-0.5 h-4 w-4 shrink-0" />
            <p className="flex-1 leading-relaxed">{toast.message}</p>
            <button type="button" onClick={() => dismissToast(toast.id)} aria-label="关闭提示">
              <X className="h-3.5 w-3.5 opacity-60 hover:opacity-100" />
            </button>
          </div>
        )
      })}
    </div>
  )
}

export function formatTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleTimeString('zh-CN', { hour12: false })
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleString('zh-CN', { hour12: false })
}
