import { ArrowRight, Info, ShieldCheck, ShieldX } from 'lucide-react'
import { Link } from 'react-router-dom'
import { TaskPicker } from '../components/TaskHistory'
import { Card, EmptyState, SEVERITY_LABEL, SEVERITY_STYLE, SectionHeader, StatusBadge } from '../components/ui'
import { CheckCard, SeveritySummary, ValidationBanner } from '../components/ValidationView'
import { useSession } from '../store/SessionContext'
import type { Severity } from '../types'

const DIMENSION_LABEL: Record<string, string> = {
  structure: '结构',
  value: '字段值',
  intent: '需求符合度',
  risk: '风险规则',
}

export function ValidationPage() {
  const { task } = useSession()
  const report = task?.final_validation ?? null

  if (!task || !report) {
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-bold text-navy-900">ACL 配置安全校验报告</h1>
        <Card>
          <EmptyState
            icon={<ShieldX className="h-5 w-5" />}
            title={task ? '本次任务没有可展示的校验报告' : '还没有校验报告'}
            desc={
              task
                ? '该任务可能因需求信息不足而停止，未生成候选配置，因此没有执行校验。'
                : '先在工作台执行一次任务，Python 校验模块会生成结构化报告。'
            }
            action={
              <Link to="/workbench" className="btn-accent">
                前往工作台 <ArrowRight className="h-4 w-4" />
              </Link>
            }
          />
        </Card>
      </div>
    )
  }

  const order: Severity[] = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO']
  const sortedFindings = [...report.findings].sort(
    (a, b) => order.indexOf(a.severity) - order.indexOf(b.severity),
  )

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-navy-900">ACL 配置安全校验报告</h1>
          <p className="mt-1 text-sm text-slate-600">
            报告由后端 Python 校验模块生成，与配置生成环节相互独立；共评估 {report.rules_evaluated} 条规则。
          </p>
        </div>
        <div className="flex items-center gap-3">
          <TaskPicker />
          <StatusBadge status={task.status} label={task.status_label} />
        </div>
      </div>

      <Card>
        <div className="flex flex-wrap items-center gap-3">
          <span
            className={`flex h-10 w-10 items-center justify-center rounded-lg ${
              report.passed ? 'bg-emerald-50 text-emerald-600' : 'bg-rose-50 text-rose-600'
            }`}
          >
            <ShieldCheck className="h-5 w-5" />
          </span>
          <div>
            <p className="text-sm font-semibold text-navy-900">
              {report.passed ? '未发现中高风险问题' : `发现 ${report.findings.length} 条需要关注的问题`}
            </p>
            <p className="mt-0.5 text-xs text-slate-500">
              任务状态：{task.status_label} · 校验建议状态：{report.status_suggestion}
            </p>
          </div>
          <div className="ml-auto">
            <SeveritySummary report={report} />
          </div>
        </div>
        <div className="mt-3 grid gap-2 sm:grid-cols-4">
          {report.checks.map((check) => (
            <div
              key={check.key}
              className={`rounded-lg border px-3 py-2 ${
                check.status === 'PASS'
                  ? 'border-emerald-200 bg-emerald-50/60'
                  : check.status === 'FAIL'
                    ? 'border-rose-200 bg-rose-50/60'
                    : 'border-slate-200 bg-slate-50'
              }`}
            >
              <p className="text-[11px] text-slate-500">
                检查 {check.key} · {check.name}
              </p>
              <p className="mt-0.5 text-sm font-semibold text-navy-900">{check.status_label}</p>
            </div>
          ))}
        </div>
      </Card>

      <div className="grid gap-4 xl:grid-cols-[1.6fr_1fr]">
        <div className="space-y-3">
          <Card>
            <SectionHeader
              title="四个校验维度的详细结果"
              desc="每条检查都包含检查名称、结果、风险等级、问题描述、触发依据与建议处理方式。"
            />
            <div className="space-y-2">
              {report.checks.map((check) => (
                <CheckCard key={check.key} check={check} />
              ))}
            </div>
          </Card>

          <Card>
            <SectionHeader
              title="问题清单"
              desc="按风险等级排序，便于快速定位需要人工确认的条目。"
              action={<span className="text-[11px] text-slate-500">{sortedFindings.length} 条</span>}
            />
            {sortedFindings.length === 0 ? (
              <p className="rounded-lg bg-emerald-50 px-3 py-2 text-xs text-emerald-800">
                当前配置未命中已实现的检查项。请注意：这不等于配置在真实网络中绝对安全。
              </p>
            ) : (
              <div className="overflow-x-auto rounded-lg border border-slate-200">
                <table className="min-w-full text-left text-xs">
                  <thead className="bg-slate-50 text-[11px] text-slate-500">
                    <tr>
                      <th className="px-2.5 py-2 font-medium">错误代码</th>
                      <th className="px-2.5 py-2 font-medium">等级</th>
                      <th className="px-2.5 py-2 font-medium">维度</th>
                      <th className="px-2.5 py-2 font-medium">说明</th>
                      <th className="px-2.5 py-2 font-medium">处理方式</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {sortedFindings.map((finding, index) => (
                      <tr key={`${finding.code}-${index}`} className="align-top">
                        <td className="whitespace-nowrap px-2.5 py-2 font-mono text-[11px] text-slate-700">
                          {finding.code}
                        </td>
                        <td className="whitespace-nowrap px-2.5 py-2">
                          <span className={`chip border ${SEVERITY_STYLE[finding.severity]}`}>
                            {SEVERITY_LABEL[finding.severity]}
                          </span>
                        </td>
                        <td className="whitespace-nowrap px-2.5 py-2 text-slate-600">
                          {DIMENSION_LABEL[finding.dimension] ?? finding.dimension}
                        </td>
                        <td className="px-2.5 py-2 leading-relaxed text-slate-700">{finding.message}</td>
                        <td className="px-2.5 py-2 leading-relaxed text-slate-500">
                          {finding.recommendation || '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>

        <div className="space-y-3">
          <ValidationBanner report={report} />

          <Card>
            <SectionHeader title="校验口径说明" />
            <ul className="space-y-2 text-xs leading-relaxed text-slate-600">
              <li>
                <span className="font-medium text-slate-800">检查 A 结构：</span>
                JSON 可解析、存在 rules 数组、规则字段齐全且类型正确、没有模型之外的字段。
              </li>
              <li>
                <span className="font-medium text-slate-800">检查 B 字段值：</span>
                action / protocol 取值、IP 与 CIDR 合法性（主机位必须为 0）、IPv4 约束、端口范围、默认策略取值。
              </li>
              <li>
                <span className="font-medium text-slate-800">检查 C 需求符合度：</span>
                与需求解析得到的授权范围比较；只能处理结构明确的需求，解析不确定时标记为“无法判断”。
              </li>
              <li>
                <span className="font-medium text-slate-800">检查 D 风险规则：</span>
                当前实现覆盖 BROAD_PERMIT_ANY、PERMIT_ANY_SOURCE、PERMIT_ANY_DESTINATION、DEFAULT_PERMIT 等少量可解释规则。
              </li>
            </ul>
          </Card>

          <Card className="!border-amber-200 !bg-amber-50/50">
            <p className="flex items-start gap-2 text-xs leading-relaxed text-amber-900">
              <Info className="mt-0.5 h-4 w-4 shrink-0" />
              本报告只针对“统一中间数据模型”做静态规则校验。真实网络中，ACL 的效果还与规则顺序、应用接口方向、
              设备默认行为与语法差异有关，因此校验通过不能作为安全结论，也不能替代人工审核与真实测试。
            </p>
          </Card>

          <Card>
            <SectionHeader title="命中风险规则（可解释）" />
            <ul className="space-y-1.5 text-[11px] leading-relaxed text-slate-600">
              <li>
                <span className="font-mono text-slate-800">BROAD_PERMIT_ANY</span> · CRITICAL ·
                任意源到任意目标的 permit，直接拦截。
              </li>
              <li>
                <span className="font-mono text-slate-800">PERMIT_ANY_SOURCE / PERMIT_ANY_DESTINATION</span> ·
                HIGH · 单侧 0.0.0.0/0 放行，收敛范围后可修正。
              </li>
              <li>
                <span className="font-mono text-slate-800">DEFAULT_PERMIT</span> · HIGH · 默认放行，建议改为默认拒绝。
              </li>
              <li>
                <span className="font-mono text-slate-800">SOURCE/DESTINATION_SCOPE_EXCEEDED</span> · HIGH ·
                生成范围大于授权范围。
              </li>
            </ul>
          </Card>
        </div>
      </div>
    </div>
  )
}
