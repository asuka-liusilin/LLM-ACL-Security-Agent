import { AlertOctagon, AlertTriangle, CheckCircle2, HelpCircle, Info, ShieldAlert } from 'lucide-react'
import type { CheckResult, CheckStatus, Finding, Severity, ValidationReport } from '../types'
import { SEVERITY_LABEL, SEVERITY_STYLE, SeverityBadge } from './ui'

const CHECK_STATUS_STYLE: Record<CheckStatus, string> = {
  PASS: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  FAIL: 'border-rose-200 bg-rose-50 text-rose-700',
  NEEDS_REVIEW: 'border-amber-200 bg-amber-50 text-amber-700',
  UNDETERMINED: 'border-slate-200 bg-slate-50 text-slate-600',
}

const CHECK_STATUS_LABEL: Record<CheckStatus, string> = {
  PASS: '通过',
  FAIL: '未通过',
  NEEDS_REVIEW: '需要人工确认',
  UNDETERMINED: '无法判断',
}

function CheckStatusIcon({ status }: { status: CheckStatus }) {
  if (status === 'PASS') return <CheckCircle2 className="h-4 w-4 text-emerald-600" />
  if (status === 'FAIL') return <AlertOctagon className="h-4 w-4 text-rose-600" />
  if (status === 'NEEDS_REVIEW') return <AlertTriangle className="h-4 w-4 text-amber-600" />
  return <HelpCircle className="h-4 w-4 text-slate-500" />
}

export function FindingCard({ finding }: { finding: Finding }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded bg-slate-900 px-2 py-0.5 font-mono text-[11px] text-white">{finding.code}</span>
        <SeverityBadge severity={finding.severity} />
        {finding.retryable ? (
          <span className="chip border border-sky-200 bg-sky-50 text-sky-700">可自动修正</span>
        ) : (
          <span className="chip border border-slate-200 bg-slate-50 text-slate-600">不可自动修正</span>
        )}
        {finding.blocking ? (
          <span className="chip border border-rose-300 bg-rose-50 text-rose-700">
            <ShieldAlert className="h-3 w-3" /> 触发安全拦截
          </span>
        ) : null}
      </div>
      <p className="mt-2 text-sm leading-relaxed text-slate-800">{finding.message}</p>
      {finding.evidence ? (
        <p className="mt-1.5 rounded bg-slate-50 px-2 py-1.5 font-mono text-[11px] leading-relaxed text-slate-600">
          触发依据：{finding.evidence}
        </p>
      ) : null}
      {finding.recommendation ? (
        <p className="mt-1.5 text-xs leading-relaxed text-slate-500">建议处理：{finding.recommendation}</p>
      ) : null}
    </div>
  )
}

export function CheckCard({ check, defaultOpen = true }: { check: CheckResult; defaultOpen?: boolean }) {
  return (
    <details open={defaultOpen} className="group rounded-lg border border-slate-200 bg-white">
      <summary className="flex cursor-pointer list-none flex-wrap items-center gap-2 px-3 py-2.5">
        <span className="flex h-6 w-6 items-center justify-center rounded-md bg-navy-800 font-mono text-[11px] font-bold text-white">
          {check.key}
        </span>
        <span className="text-sm font-semibold text-navy-900">{check.name}</span>
        <span className={`chip border ${CHECK_STATUS_STYLE[check.status]}`}>
          <CheckStatusIcon status={check.status} />
          {check.status_label || CHECK_STATUS_LABEL[check.status]}
        </span>
        {check.severity ? (
          <span className={`chip border ${SEVERITY_STYLE[check.severity]}`}>
            最高 {SEVERITY_LABEL[check.severity]}
          </span>
        ) : null}
        <span className="ml-auto text-xs text-slate-400 group-open:hidden">展开</span>
      </summary>
      <div className="border-t border-slate-100 px-3 py-3">
        <p className="text-xs leading-relaxed text-slate-600">{check.summary}</p>
        {check.findings.length > 0 ? (
          <div className="mt-2 space-y-2">
            {check.findings.map((finding, index) => (
              <FindingCard key={`${finding.code}-${index}`} finding={finding} />
            ))}
          </div>
        ) : (
          <p className="mt-2 rounded bg-slate-50 px-2 py-1.5 text-[11px] text-slate-500">
            该维度没有发现问题条目。
          </p>
        )}
      </div>
    </details>
  )
}

export function SeveritySummary({ report }: { report: ValidationReport }) {
  const order: Severity[] = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO']
  return (
    <div className="flex flex-wrap items-center gap-2">
      {order.map((severity) => (
        <span
          key={severity}
          className={`chip border ${
            report.summary?.[severity]
              ? SEVERITY_STYLE[severity]
              : 'border-slate-200 bg-white text-slate-400'
          }`}
        >
          {SEVERITY_LABEL[severity]} {report.summary?.[severity] ?? 0}
        </span>
      ))}
      <span className="text-xs text-slate-500">共 {report.findings.length} 条检查项</span>
    </div>
  )
}

export function ValidationBanner({ report }: { report: ValidationReport }) {
  const critical = (report.summary?.CRITICAL ?? 0) + (report.summary?.HIGH ?? 0)
  const tone = report.passed
    ? 'border-emerald-200 bg-emerald-50 text-emerald-900'
    : critical > 0
      ? 'border-rose-200 bg-rose-50 text-rose-900'
      : 'border-amber-200 bg-amber-50 text-amber-900'
  const Icon = report.passed ? CheckCircle2 : critical > 0 ? AlertOctagon : Info
  return (
    <div className={`rounded-lg border px-3 py-2.5 text-sm ${tone}`}>
      <div className="flex items-start gap-2">
        <Icon className="mt-0.5 h-4 w-4 shrink-0" />
        <div>
          <p className="font-semibold">
            {report.passed ? '未发现中高风险问题（不代表绝对安全）' : '存在需要关注的问题'}
          </p>
          <p className="mt-0.5 text-xs leading-relaxed opacity-90">
            校验范围仅覆盖已实现的四项检查：结构、字段值、授权范围与预定义风险规则。
            ACL 规则顺序、应用位置与设备语义不在检查范围内。
          </p>
        </div>
      </div>
    </div>
  )
}
