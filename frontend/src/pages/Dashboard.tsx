import { ArrowRight, Bot, Cpu, GitBranch, ShieldAlert, ShieldCheck, Wrench } from 'lucide-react'
import { Link } from 'react-router-dom'
import { FlowSteps } from '../components/FlowSteps'
import { Card, SectionHeader, StatusBadge } from '../components/ui'
import { useSession } from '../store/SessionContext'

function StatCard({
  label,
  value,
  hint,
  tone = 'default',
}: {
  label: string
  value: string
  hint?: string
  tone?: 'default' | 'ok' | 'warn' | 'danger'
}) {
  const toneClass =
    tone === 'ok'
      ? 'text-emerald-700'
      : tone === 'warn'
        ? 'text-amber-700'
        : tone === 'danger'
          ? 'text-rose-700'
          : 'text-navy-900'
  return (
    <Card className="!p-4">
      <p className="label">{label}</p>
      <p className={`mt-2 text-lg font-semibold leading-snug ${toneClass}`}>{value}</p>
      {hint ? <p className="mt-1 text-[11px] leading-relaxed text-slate-500">{hint}</p> : null}
    </Card>
  )
}

const CAPABILITIES = [
  {
    icon: Bot,
    title: '自然语言 → 结构化配置',
    desc: '把“允许某主机访问某服务的 HTTPS”转换为统一 ACL 数据模型，字段固定、可被程序检查。',
  },
  {
    icon: ShieldCheck,
    title: '独立的 Python 校验',
    desc: '校验模块不依赖生成方，检查结构、IP/CIDR、端口、默认策略与授权范围偏差。',
  },
  {
    icon: GitBranch,
    title: '受约束的 Agent 调度',
    desc: '根据错误代码选择重新生成、请求补充信息或转人工审核，重试次数受状态机限制。',
  },
  {
    icon: ShieldAlert,
    title: '高风险不可自动绕过',
    desc: '命中严重风险规则时直接拦截，普通重试不能把危险配置“洗成”通过。',
  },
]

export function Dashboard() {
  const { health, healthError, task } = useSession()

  const report = task?.final_validation ?? null
  const highRisk = report ? (report.summary?.HIGH ?? 0) + (report.summary?.CRITICAL ?? 0) : 0

  const validationText = !task
    ? '尚未校验'
    : !report
      ? '尚未生成配置'
      : report.passed
        ? '未发现中高风险问题'
        : `${report.findings.length} 条问题，最高 ${highRisk > 0 ? '高风险' : '中风险'}`

  const validationTone = !task || !report ? 'default' : report.passed ? 'ok' : highRisk > 0 ? 'danger' : 'warn'

  const callText = !task
    ? '—'
    : task.usage.api_calls > 0
      ? `${task.usage.api_calls} 次真实 API 调用`
      : `0 次真实调用（演示生成 ${task.usage.demo_generation_calls} 次）`

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-navy-900 lg:text-2xl">ACL 智能运维与安全校验 Agent</h1>
          <p className="mt-1.5 max-w-3xl text-sm leading-relaxed text-slate-600">
            面向网络运维的自然语言配置生成、独立安全校验与 Agent 任务调度原型
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to="/workbench" className="btn-accent">
            开始体验
            <ArrowRight className="h-4 w-4" />
          </Link>
          <Link to="/trace" className="btn-ghost">
            查看执行流程
          </Link>
        </div>
      </div>

      {healthError ? (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
          后端未连接：{healthError}。请先在 backend 目录启动 FastAPI（见项目说明）。
        </div>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="运行模式"
          value={health?.api_mode_available ? 'API 模式可用' : '演示模式'}
          hint={
            health?.api_mode_available
              ? `模型：${health.model ?? '未提供'}；API Key 仅保存在后端`
              : '未配置 LLM_API_KEY，使用确定性生成器演示完整流程'
          }
        />
        <StatCard
          label="本次任务状态"
          value={task ? task.status_label : '待开始'}
          hint={
            task
              ? `${task.id} · ${task.mode_label}${task.awaiting_review ? ' · 等待人工审核' : ''}${
                  task.awaiting_user ? ' · 等待补充信息' : ''
                }`
              : '还没有执行任何任务，可先到工作台提交一条需求'
          }
          tone={
            task?.status === 'SUCCESS'
              ? 'ok'
              : task?.status === 'BLOCKED' || task?.status === 'FAILED'
                ? 'danger'
                : task?.status === 'REVIEW_REQUIRED'
                  ? 'warn'
                  : 'default'
          }
        />
        <StatCard
          label="本次任务模型调用次数"
          value={callText}
          hint={
            task
              ? `Token：${task.token_display}（演示模式不计入真实统计）`
              : '演示模式与真实 API 调用分开统计'
          }
        />
        <StatCard
          label="本次任务校验结果"
          value={validationText}
          hint={
            report
              ? `通过 ${report.checks.filter((c) => c.status === 'PASS').length}/4 项检查；通过检查不代表绝对安全`
              : '校验结果由后端 Python 模块生成'
          }
          tone={validationTone as 'default' | 'ok' | 'warn' | 'danger'}
        />
      </div>

      <Card>
        <SectionHeader
          title="系统处理流程"
          desc="节点状态由真实任务状态驱动；未执行的步骤不会显示为已完成。"
          action={task ? <StatusBadge status={task.status} label={task.status_label} /> : undefined}
        />
        <FlowSteps task={task} />
      </Card>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {CAPABILITIES.map((item) => (
          <Card key={item.title} className="!p-4">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-navy-800/5 text-navy-800">
              <item.icon className="h-4 w-4" />
            </span>
            <p className="mt-2.5 text-sm font-semibold text-navy-900">{item.title}</p>
            <p className="mt-1 text-xs leading-relaxed text-slate-500">{item.desc}</p>
          </Card>
        ))}
      </div>

      <div className="grid gap-3 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <SectionHeader title="安全边界说明" desc="以下约束是原型的设计前提，不会因为按钮操作而被绕过。" />
          <ul className="space-y-2 text-sm leading-relaxed text-slate-700">
            <li className="flex gap-2">
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
              系统只生成、检查与展示配置，不连接也不下发任何真实网络设备。
            </li>
            <li className="flex gap-2">
              <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-rose-600" />
              命中预定义严重风险的配置进入安全拦截，不能通过普通重试自动通过。
            </li>
            <li className="flex gap-2">
              <Wrench className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
              校验通过只意味着未命中已实现的检查项，不构成“绝对安全”的结论。
            </li>
            <li className="flex gap-2">
              <Cpu className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" />
              演示模式的生成结果来自确定性规则，不是真实大模型推理结果。
            </li>
          </ul>
        </Card>

        <Card>
          <SectionHeader title="技术路线" desc="生成与校验分离，Agent 只做受约束的调度。" />
          <ol className="space-y-2 text-xs leading-relaxed text-slate-600">
            <li>1. 需求解析：提取源/目标/协议/端口/动作，缺失则请求补充。</li>
            <li>2. 配置生成：输出统一 JSON，不猜测未给出的地址。</li>
            <li>3. 独立校验：结构 → 字段值 → 授权范围 → 风险规则。</li>
            <li>4. 决策与修正：可修正才重试，达到上限即停。</li>
            <li>5. 人工审核：审核通过仅代表确认候选配置。</li>
          </ol>
          <Link to="/about" className="mt-4 inline-flex text-xs font-medium text-accent-600 hover:underline">
            查看完整项目说明与架构 →
          </Link>
        </Card>
      </div>
    </div>
  )
}
