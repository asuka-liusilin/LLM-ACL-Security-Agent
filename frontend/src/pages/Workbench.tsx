import {
  AlertTriangle,
  ArrowRight,
  ChevronRight,
  CornerDownLeft,
  Info,
  PlayCircle,
  RefreshCw,
  ShieldAlert,
} from 'lucide-react'
import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { JsonViewer } from '../components/JsonViewer'
import { TaskHistoryList } from '../components/TaskHistory'
import {
  Card,
  EmptyState,
  SEVERITY_LABEL,
  SEVERITY_STYLE,
  SectionHeader,
  Spinner,
  StatusBadge,
  Toggle,
  formatTime,
} from '../components/ui'
import { CheckCard, SeveritySummary } from '../components/ValidationView'
import { useSession } from '../store/SessionContext'
import type { ACLRule, Finding, Severity, Task, TaskParams } from '../types'

const EXAMPLES = [
  {
    id: 'A',
    tag: '正常需求',
    text: '允许 192.168.1.10 访问 10.0.0.10 的 HTTPS 服务，仅允许该主机访问该服务。',
    hint: '预期：生成单条 tcp/443 规则并通过检查',
  },
  {
    id: 'B',
    tag: '缺少关键信息',
    text: '允许办公网访问服务器。',
    hint: '预期：进入“需要补充信息”，不会猜测地址',
  },
  {
    id: 'C',
    tag: '授权范围扩大风险',
    text: '只允许 192.168.1.10 访问 10.0.0.10，但请生成覆盖 192.168.1.0/24 的访问规则。',
    hint: '预期：首次越权 → 校验发现 → 反馈修正后通过',
  },
  {
    id: 'D',
    tag: '宽泛放行风险',
    text: '生成一条允许任意 IPv4 源地址访问任意 IPv4 目标地址的 ACL 规则。',
    hint: '预期：命中严重风险并进入安全拦截',
  },
]

const DEFAULT_PARAMS: TaskParams = {
  mode: 'demo',
  max_retries: 2,
  enable_feedback_fix: true,
  enable_high_risk_block: true,
  require_human_review: true,
}

const SEV_ORDER: Severity[] = ['INFO', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL']

function ruleFindings(findings: Finding[], index: number): Finding[] {
  return findings.filter((f) => f.rule_index === index)
}

function worstSeverity(findings: Finding[]): Severity | null {
  if (findings.length === 0) return null
  return findings.reduce<Severity>(
    (acc, item) => (SEV_ORDER.indexOf(item.severity) > SEV_ORDER.indexOf(acc) ? item.severity : acc),
    findings[0].severity,
  )
}

function RuleTable({ rules, findings }: { rules: ACLRule[]; findings: Finding[] }) {
  if (rules.length === 0) {
    return <p className="text-sm text-slate-500">当前配置没有任何规则。</p>
  }
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200">
      <table className="min-w-full text-left text-xs">
        <thead className="bg-slate-50 text-[11px] uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-3 py-2 font-medium">#</th>
            <th className="px-3 py-2 font-medium">动作</th>
            <th className="px-3 py-2 font-medium">协议</th>
            <th className="px-3 py-2 font-medium">源地址</th>
            <th className="px-3 py-2 font-medium">目标地址</th>
            <th className="px-3 py-2 font-medium">目标端口</th>
            <th className="px-3 py-2 font-medium">风险状态</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rules.map((rule, index) => {
            const items = ruleFindings(findings, index)
            const severity = worstSeverity(items)
            return (
              <tr key={index} className="align-top">
                <td className="px-3 py-2 font-mono text-slate-400">{index + 1}</td>
                <td className="px-3 py-2">
                  <span
                    className={`chip border ${
                      rule.action === 'permit'
                        ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                        : 'border-rose-200 bg-rose-50 text-rose-700'
                    }`}
                  >
                    {rule.action}
                  </span>
                </td>
                <td className="px-3 py-2 font-mono text-slate-700">{rule.protocol}</td>
                <td className="px-3 py-2 font-mono text-slate-700">{rule.source}</td>
                <td className="px-3 py-2 font-mono text-slate-700">{rule.destination}</td>
                <td className="px-3 py-2 font-mono text-slate-700">
                  {rule.destination_port ?? '—'}
                </td>
                <td className="px-3 py-2">
                  {severity ? (
                    <span className={`chip border ${SEVERITY_STYLE[severity]}`} title={items.map((i) => i.code).join(', ')}>
                      {SEVERITY_LABEL[severity]}
                    </span>
                  ) : (
                    <span className="chip border border-slate-200 bg-white text-slate-500">未发现问题</span>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function StatusBanner({ task }: { task: Task }) {
  const tone =
    task.status === 'SUCCESS'
      ? 'border-emerald-200 bg-emerald-50 text-emerald-900'
      : task.status === 'BLOCKED' || task.status === 'FAILED'
        ? 'border-rose-200 bg-rose-50 text-rose-900'
        : task.status === 'REVIEW_REQUIRED' || task.status === 'NEED_INFO'
          ? 'border-amber-200 bg-amber-50 text-amber-900'
          : 'border-sky-200 bg-sky-50 text-sky-900'

  const latest = task.decisions[task.decisions.length - 1]

  return (
    <div className={`rounded-xl border px-4 py-3 ${tone}`}>
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge status={task.status} label={task.status_label} />
        <span className="font-mono text-[11px] opacity-70">{task.id}</span>
        <span className="text-[11px] opacity-70">
          用时 {task.duration_ms ?? 0} ms · 生成 {task.attempts.length} 次 · 修正 {task.retry_count}/
          {task.params.max_retries} 次
        </span>
        <span className="ml-auto text-[11px] font-medium">
          {task.review?.decision === 'approve'
            ? '已人工确认 · 未下发设备'
            : task.status === 'SUCCESS'
              ? '通过检查 · 未要求人工审核 · 未下发设备'
              : '未下发任何设备'}
        </span>
      </div>
      {latest ? (
        <p className="mt-2 text-sm leading-relaxed">
          <span className="font-semibold">Agent 决策：</span>
          {latest.reason}
        </p>
      ) : null}
      <div className="mt-2 flex flex-wrap gap-3 text-[11px]">
        <Link to="/trace" className="inline-flex items-center gap-1 underline-offset-2 hover:underline">
          查看执行日志 <ChevronRight className="h-3 w-3" />
        </Link>
        <Link to="/report" className="inline-flex items-center gap-1 underline-offset-2 hover:underline">
          查看校验报告 <ChevronRight className="h-3 w-3" />
        </Link>
      </div>
    </div>
  )
}

function IntentCard({ task }: { task: Task }) {
  const intent = task.intent
  if (!intent) {
    return (
      <Card>
        <SectionHeader title="需求理解结果" />
        <p className="text-sm text-slate-500">尚未完成需求解析。</p>
      </Card>
    )
  }
  return (
    <Card>
      <SectionHeader
        title="需求理解结果"
        desc={`解析方式：${intent.parse_mode === 'demo-rule' ? '演示模式规则解析（未调用大模型）' : '大模型解析'}`}
      />
      <dl className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-lg bg-slate-50 px-3 py-2">
          <dt className="label">源地址</dt>
          <dd className="mt-1 font-mono text-xs text-slate-800">{intent.sources.join(', ') || '未识别'}</dd>
        </div>
        <div className="rounded-lg bg-slate-50 px-3 py-2">
          <dt className="label">目标地址</dt>
          <dd className="mt-1 font-mono text-xs text-slate-800">
            {intent.destinations.join(', ') || '未识别'}
          </dd>
        </div>
        <div className="rounded-lg bg-slate-50 px-3 py-2">
          <dt className="label">动作 / 协议 / 端口</dt>
          <dd className="mt-1 font-mono text-xs text-slate-800">
            {intent.action ?? '未识别'} / {intent.protocol ?? '未识别'} /{' '}
            {intent.destination_port ?? '未指定'}
            {intent.service_label ? `（${intent.service_label}）` : ''}
          </dd>
        </div>
        <div className="rounded-lg bg-slate-50 px-3 py-2">
          <dt className="label">默认策略</dt>
          <dd className="mt-1 font-mono text-xs text-slate-800">
            {intent.default_action ?? '需求未明示（按最小权限取 deny）'}
          </dd>
        </div>
      </dl>

      {intent.missing.length > 0 ? (
        <p className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          缺少必要信息：{intent.missing.join('、')}。系统不会猜测具体网络地址。
        </p>
      ) : null}
      {intent.invalid_values.length > 0 ? (
        <p className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-800">
          无效输入：{intent.invalid_values.join('；')}
        </p>
      ) : null}
      {intent.widen_source_hint || intent.widen_destination_hint ? (
        <p className="mt-3 rounded-lg border border-orange-200 bg-orange-50 px-3 py-2 text-xs text-orange-800">
          注意：需求原文要求生成覆盖更大范围的规则
          {intent.widen_source_hint ? `（源 ${intent.widen_source_hint}）` : ''}
          {intent.widen_destination_hint ? `（目标 ${intent.widen_destination_hint}）` : ''}
          。该指令会被记录，但校验仍按实际授权范围比较。
        </p>
      ) : null}
      {intent.assumptions.length > 0 ? (
        <ul className="mt-3 space-y-1 text-xs text-slate-500">
          {intent.assumptions.map((item, index) => (
            <li key={index}>· 假设：{item}</li>
          ))}
        </ul>
      ) : null}
    </Card>
  )
}

function FeedbackForm() {
  const { task, sendFeedback, busy } = useSession()
  const [message, setMessage] = useState('')
  if (!task || task.status !== 'NEED_INFO') return null
  return (
    <Card className="!border-amber-200 !bg-amber-50/40">
      <SectionHeader
        title="需要补充信息"
        desc={`缺少字段：${task.missing_fields.join('、') || '关键参数'}。补充后会重新解析需求并继续生成。`}
      />
      <textarea
        className="input h-24 resize-y"
        placeholder="例如：源地址 192.168.1.10，目标地址 10.0.0.10，HTTPS 服务，仅允许该主机访问。"
        value={message}
        onChange={(event) => setMessage(event.target.value)}
      />
      <button
        type="button"
        className="btn-accent mt-2 w-full"
        disabled={!message.trim() || busy === 'feedback'}
        onClick={async () => {
          await sendFeedback(message.trim())
          setMessage('')
        }}
      >
        {busy === 'feedback' ? <Spinner /> : <CornerDownLeft className="h-4 w-4" />}
        提交补充信息并继续
      </button>
    </Card>
  )
}

function ReviewForm() {
  const { task, sendReview, busy } = useSession()
  const [comment, setComment] = useState('')
  const [reviewer, setReviewer] = useState('人工审核员')
  if (!task || (task.status !== 'REVIEW_REQUIRED' && task.status !== 'BLOCKED')) return null
  const isBlocked = task.status === 'BLOCKED'

  return (
    <Card className={isBlocked ? '!border-rose-200 !bg-rose-50/40' : '!border-amber-200 !bg-amber-50/40'}>
      <SectionHeader
        title={isBlocked ? '安全拦截 · 需人工处理' : '等待人工审核'}
        desc={
          isBlocked
            ? '该配置命中严重风险规则，普通重试无法让它自动通过。批准时必须填写理由，并在实验记录中明确标注风险已被人为接受。'
            : 'Python 检查通过或被阻断后，仍需人工确认候选配置。审核通过不代表已下发到设备。'
        }
      />
      <div className="space-y-2">
        <input
          className="input"
          value={reviewer}
          onChange={(event) => setReviewer(event.target.value)}
          placeholder="审核人"
        />
        <textarea
          className="input h-20 resize-y"
          value={comment}
          onChange={(event) => setComment(event.target.value)}
          placeholder={isBlocked ? '必填：说明为什么接受该高风险配置（仅用于实验）' : '审核意见（可选）'}
        />
      </div>
      <div className="mt-2 grid gap-2 sm:grid-cols-3">
        <button
          type="button"
          className="btn-accent"
          disabled={busy === 'review' || (isBlocked && !comment.trim())}
          onClick={() => void sendReview('approve', comment, reviewer)}
        >
          批准配置
        </button>
        <button
          type="button"
          className="btn-danger"
          disabled={busy === 'review'}
          onClick={() => void sendReview('reject', comment, reviewer)}
        >
          拒绝
        </button>
        <button
          type="button"
          className="btn-ghost"
          disabled={busy === 'review'}
          onClick={() => void sendReview('request_changes', comment, reviewer)}
        >
          <RefreshCw className="h-3.5 w-3.5" />
          要求修改
        </button>
      </div>
      <p className="mt-2 text-[11px] leading-relaxed text-slate-500">
        审核记录会写入任务日志；“批准”只表示确认候选配置，不会向任何设备下发命令。
      </p>
    </Card>
  )
}

export function Workbench() {
  const { health, task, submitting, submit } = useSession()
  const [requirement, setRequirement] = useState('')
  const [params, setParams] = useState<TaskParams>(DEFAULT_PARAMS)
  const [inputError, setInputError] = useState<string | null>(null)
  const resultRef = useRef<HTMLDivElement | null>(null)

  const apiAvailable = Boolean(health?.api_mode_available)
  const report = task?.final_validation ?? null
  const rules = task?.final_config?.rules ?? []
  const running = Boolean(task && !task.is_terminal && !task.awaiting_user && !task.awaiting_review)

  const onRun = async () => {
    if (!requirement.trim()) {
      setInputError('请先输入访问控制需求，或点击下方示例。')
      return
    }
    if (requirement.trim().length < 4) {
      setInputError('需求描述过短，请补充源地址、目标地址与访问要求。')
      return
    }
    setInputError(null)
    const created = await submit(requirement.trim(), params)
    if (created) {
      window.setTimeout(() => resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 120)
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold text-navy-900">智能 ACL 配置工作台</h1>
        <p className="mt-1 text-sm text-slate-600">
          用中文描述访问控制需求，系统会规划任务、生成结构化配置，并由 Python 独立校验后决定下一步。
        </p>
      </div>

      <Card>
        <SectionHeader
          title="1. 自然语言需求"
          desc="请尽量给出源地址、目标地址、协议/服务与动作；信息不足时系统会要求补充，而不是猜测。"
          action={
            <span className="chip border border-slate-200 bg-slate-50 text-slate-600">
              {requirement.length} 字符
            </span>
          }
        />
        <textarea
          className="input h-32 resize-y leading-relaxed"
          placeholder="请描述你的网络访问控制需求，例如：允许 192.168.1.10 访问 10.0.0.10 的 HTTPS 服务，其他未授权流量默认拒绝。"
          value={requirement}
          onChange={(event) => {
            setRequirement(event.target.value)
            if (inputError) setInputError(null)
          }}
          disabled={submitting}
        />

        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          {EXAMPLES.map((example) => (
            <button
              key={example.id}
              type="button"
              onClick={() => {
                setRequirement(example.text)
                setInputError(null)
              }}
              className="group rounded-lg border border-slate-200 bg-white px-3 py-2 text-left transition hover:border-accent-400 hover:bg-accent-50/40"
            >
              <span className="flex items-center gap-2">
                <span className="chip border border-navy-800/15 bg-navy-800/5 font-mono text-navy-800">
                  示例 {example.id}
                </span>
                <span className="text-xs font-medium text-slate-700">{example.tag}</span>
                <ArrowRight className="ml-auto h-3.5 w-3.5 text-slate-300 group-hover:text-accent-500" />
              </span>
              <span className="mt-1.5 block text-[11px] leading-relaxed text-slate-500">{example.hint}</span>
            </button>
          ))}
        </div>

        {inputError ? (
          <p className="mt-2 flex items-center gap-1.5 text-xs text-rose-600">
            <AlertTriangle className="h-3.5 w-3.5" />
            {inputError}
          </p>
        ) : null}

        <div className="mt-5 grid gap-4 lg:grid-cols-[280px_1fr]">
          <div className="space-y-2">
            <p className="label">任务参数</p>
            <label className="block">
              <span className="text-xs text-slate-600">执行模式</span>
              <select
                className="input mt-1"
                value={params.mode}
                onChange={(event) => setParams({ ...params, mode: event.target.value as TaskParams['mode'] })}
                disabled={submitting}
              >
                <option value="demo">演示模式（无需 API Key）</option>
                <option value="api" disabled={!apiAvailable}>
                  API 模式{apiAvailable ? '' : '（后端未配置 Key）'}
                </option>
              </select>
            </label>
            <label className="block">
              <span className="text-xs text-slate-600">最大自动修正次数</span>
              <select
                className="input mt-1"
                value={params.max_retries}
                onChange={(event) => setParams({ ...params, max_retries: Number(event.target.value) })}
                disabled={submitting}
              >
                {[0, 1, 2, 3].map((value) => (
                  <option key={value} value={value}>
                    {value} 次
                  </option>
                ))}
              </select>
            </label>
            <p className="rounded-lg bg-slate-50 px-2.5 py-2 text-[11px] leading-relaxed text-slate-500">
              参数会随请求提交到后端并真实影响流程；高风险拦截与人工审核属于安全边界，关闭普通反馈修正也不会放开这些限制。
            </p>
          </div>

          <div className="space-y-2">
            <p className="label">流程开关</p>
            <div className="grid gap-2 sm:grid-cols-2">
              <Toggle
                label="启用 Agent 反馈修正"
                desc="校验失败时允许在次数上限内重新生成"
                checked={params.enable_feedback_fix}
                onChange={(next) => setParams({ ...params, enable_feedback_fix: next })}
                disabled={submitting}
              />
              <Toggle
                label="启用高风险规则拦截"
                desc="关闭后高风险仍不会被自动通过，只会转人工审核"
                checked={params.enable_high_risk_block}
                onChange={(next) => setParams({ ...params, enable_high_risk_block: next })}
                disabled={submitting}
              />
              <Toggle
                label="要求人工审核"
                desc="通过检查后仍需人工确认候选配置"
                checked={params.require_human_review}
                onChange={(next) => setParams({ ...params, require_human_review: next })}
                disabled={submitting}
              />
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-[11px] leading-relaxed text-slate-500">
                <Info className="mb-1 h-3.5 w-3.5 text-slate-400" />
                演示模式的配置由确定性规则生成，用于展示流程，不代表真实大模型效果。
              </div>
            </div>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button type="button" className="btn-primary !px-5 !py-2.5" onClick={onRun} disabled={submitting}>
            {submitting ? <Spinner /> : <PlayCircle className="h-4 w-4" />}
            {submitting ? '正在提交任务…' : '开始分析并生成配置'}
          </button>
          {running ? (
            <span className="flex items-center gap-1.5 text-xs text-accent-600">
              <Spinner className="!h-3.5 !w-3.5" />
              任务执行中：{task?.status_label}
            </span>
          ) : null}
          {task ? (
            <span className="text-xs text-slate-400">
              最近一次：{formatTime(task.created_at)} · {task.mode_label}
            </span>
          ) : null}
        </div>
      </Card>

      <div ref={resultRef} />

      {!task ? (
        <Card>
          <EmptyState
            icon={<ShieldAlert className="h-5 w-5" />}
            title="还没有任务结果"
            desc="输入需求或点击示例后执行，即可看到需求解析、结构化配置、Python 校验结果与 Agent 决策。"
          />
        </Card>
      ) : (
        <div className="space-y-4">
          <StatusBanner task={task} />

          <div className="grid gap-4 xl:grid-cols-[1.55fr_1fr]">
            <div className="space-y-4">
              <IntentCard task={task} />

              <Card>
                <SectionHeader
                  title="结构化 ACL 配置"
                  desc="项目统一中间数据模型，不等同于任何厂商设备可直接使用的语法。"
                  action={
                    task.final_config ? <span className="chip border border-slate-200 bg-slate-50 text-slate-600">候选配置 v{task.attempts.length}</span> : undefined
                  }
                />
                {task.final_config ? (
                  <>
                    <JsonViewer value={task.final_config} />
                    <div className="mt-3">
                      <p className="mb-2 text-xs font-medium text-slate-600">配置规则列表</p>
                      <RuleTable rules={rules} findings={report?.findings ?? []} />
                      <p className="mt-2 text-[11px] text-slate-500">
                        默认策略：{task.final_config.default_action} · 规则数量：{rules.length}
                      </p>
                    </div>
                  </>
                ) : (
                  <EmptyState
                    title="本次任务没有产生可用配置"
                    desc={
                      task.status === 'NEED_INFO'
                        ? '需求信息不足，系统按设计停止生成并要求补充。'
                        : '生成或校验未通过，未输出可用于展示的配置。请查看执行日志了解原因。'
                    }
                  />
                )}
              </Card>

              {task.attempts.length > 1 ? (
                <Card>
                  <SectionHeader
                    title="修正过程对比"
                    desc="每次重新生成都会重新执行一次完整的 Python 校验。"
                  />
                  <div className="space-y-2">
                    {task.attempts.map((attempt) => (
                      <div key={attempt.index} className="rounded-lg border border-slate-200 p-3">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="chip border border-slate-200 bg-slate-50 text-slate-600">
                            attempt {attempt.index}
                          </span>
                          <span className="text-xs text-slate-500">
                            {attempt.kind === 'initial' ? '首次生成' : '反馈修正'}
                          </span>
                          {attempt.validation ? (
                            <span
                              className={`chip border ${
                                attempt.validation.passed
                                  ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                                  : 'border-rose-200 bg-rose-50 text-rose-700'
                              }`}
                            >
                              {attempt.validation.passed ? '校验通过' : `${attempt.validation.findings.length} 条问题`}
                            </span>
                          ) : null}
                          <span className="ml-auto font-mono text-[11px] text-slate-400">
                            {formatTime(attempt.created_at)}
                          </span>
                        </div>
                        <p className="mt-1.5 text-[11px] leading-relaxed text-slate-600">{attempt.note}</p>
                        {attempt.validation && !attempt.validation.passed ? (
                          <p className="mt-1 font-mono text-[11px] text-rose-600">
                            {attempt.validation.findings
                              .slice(0, 3)
                              .map((f) => f.code)
                              .join(' · ')}
                          </p>
                        ) : null}
                      </div>
                    ))}
                  </div>
                </Card>
              ) : null}
            </div>

            <div className="space-y-4">
              <Card>
                <SectionHeader
                  title="Python 校验结果"
                  desc="由后端独立规则模块生成，不依赖生成配置的模型。"
                  action={
                    report ? (
                      <span
                        className={`chip border ${
                          report.passed
                            ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                            : 'border-rose-200 bg-rose-50 text-rose-700'
                        }`}
                      >
                        {report.passed ? '未发现中高风险问题' : '存在问题'}
                      </span>
                    ) : undefined
                  }
                />
                {report ? (
                  <div className="space-y-2">
                    <SeveritySummary report={report} />
                    <div className="space-y-2">
                      {report.checks.map((check) => (
                        <CheckCard key={check.key} check={check} defaultOpen={check.status !== 'PASS'} />
                      ))}
                    </div>
                    <Link
                      to="/report"
                      className="inline-flex items-center gap-1 pt-1 text-xs font-medium text-accent-600 hover:underline"
                    >
                      查看完整安全校验报告 <ChevronRight className="h-3 w-3" />
                    </Link>
                  </div>
                ) : (
                  <p className="text-sm text-slate-500">本次任务未执行校验（未生成配置）。</p>
                )}
              </Card>

              <Card>
                <SectionHeader title="Agent 决策" desc="只展示决策摘要与工具结果，不展示模型隐藏推理过程。" />
                {task.decisions.length === 0 ? (
                  <p className="text-sm text-slate-500">暂无决策记录。</p>
                ) : (
                  <ol className="space-y-2">
                    {task.decisions.slice(-4).map((decision) => (
                      <li key={decision.step} className="rounded-lg border border-slate-200 p-3">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="rounded bg-navy-800 px-2 py-0.5 font-mono text-[10px] text-white">
                            {decision.action}
                          </span>
                          <span className="text-[11px] text-slate-400">步骤 {decision.step}</span>
                          {decision.error_codes.length > 0 ? (
                            <span className="font-mono text-[10px] text-rose-600">
                              {decision.error_codes.slice(0, 3).join(', ')}
                            </span>
                          ) : null}
                        </div>
                        <p className="mt-1.5 text-xs leading-relaxed text-slate-700">{decision.reason}</p>
                        <p className="mt-1 text-[10px] text-slate-400">
                          重试 {decision.retry_count} 次
                          {decision.requires_human_review ? ' · 需要人工参与' : ''}
                        </p>
                      </li>
                    ))}
                  </ol>
                )}
              </Card>

              <FeedbackForm />
              <ReviewForm />
            </div>
          </div>
        </div>
      )}

      <Card>
        <SectionHeader
          title="任务历史"
          desc="仅保存在本次会话（浏览器本地缓存 + 后端内存），后端重启后详情会清空。"
        />
        <TaskHistoryList currentId={task?.id} emptyHint="提交第一条需求后，这里会出现可回溯的任务记录。" />
      </Card>
    </div>
  )
}
