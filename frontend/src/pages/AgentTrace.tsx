import { Activity, ArrowRight, GitBranch, ListChecks, RotateCcw } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useMemo } from 'react'
import { TaskPicker } from '../components/TaskHistory'
import { Card, EmptyState, SectionHeader, StatusBadge, formatTime } from '../components/ui'
import { useSession } from '../store/SessionContext'
import type { Task, TaskStatus } from '../types'

const MAIN_FLOW: TaskStatus[] = ['RECEIVED', 'ANALYZING', 'GENERATING', 'VALIDATING', 'SUCCESS']
const BRANCH_FLOW: TaskStatus[] = ['NEED_INFO', 'RETRYING', 'REVIEW_REQUIRED', 'BLOCKED', 'FAILED']

const STATE_DESC: Record<TaskStatus, string> = {
  RECEIVED: '接收需求，尚未开始分析',
  ANALYZING: '解析源/目标地址、协议、动作',
  NEED_INFO: '关键参数缺失，等待用户补充',
  GENERATING: '调用生成模块产出候选配置',
  VALIDATING: 'Python 校验结构、取值、范围与风险',
  RETRYING: '根据校验反馈准备重新生成',
  REVIEW_REQUIRED: '等待人工审核候选配置',
  SUCCESS: '通过检查（未下发设备）',
  FAILED: '自动处理失败，未产出可用配置',
  BLOCKED: '命中严重风险，安全策略拦截',
}

const ACTION_LABEL: Record<string, string> = {
  GENERATE_CONFIG: '生成配置',
  VALIDATE_CONFIG: '调用校验',
  RETRY_GENERATION: '重新生成',
  REQUEST_USER_INFO: '请求补充信息',
  REQUEST_HUMAN_REVIEW: '转人工审核',
  COMPLETE_TASK: '结束任务',
  ABORT_TASK: '终止任务',
}

function useVisited(task: Task | null) {
  return useMemo(() => {
    const counts = new Map<TaskStatus, number>()
    counts.set('RECEIVED', 1)
    task?.events.forEach((event) => {
      const matched = event.message.match(/状态变更：(\w+) → (\w+)/)
      if (matched) {
        const next = matched[2] as TaskStatus
        counts.set(next, (counts.get(next) ?? 0) + 1)
      }
    })
    if (task && !counts.has(task.status)) {
      counts.set(task.status, (counts.get(task.status) ?? 0) + 1)
    }
    return counts
  }, [task])
}

function StateNode({
  state,
  current,
  count,
}: {
  state: TaskStatus
  current: boolean
  count: number
}) {
  const visited = count > 0
  const tone = current
    ? 'border-accent-500 bg-accent-50 ring-2 ring-accent-100'
    : visited
      ? 'border-emerald-200 bg-emerald-50/60'
      : 'border-slate-200 bg-white'
  return (
    <div className={`rounded-lg border p-2.5 ${tone}`}>
      <div className="flex items-center gap-1.5">
        <span
          className={`h-1.5 w-1.5 rounded-full ${
            current ? 'bg-accent-500' : visited ? 'bg-emerald-500' : 'bg-slate-300'
          }`}
        />
        <span className="font-mono text-[11px] font-semibold text-navy-900">{state}</span>
        {count > 1 ? <span className="ml-auto text-[10px] text-slate-400">×{count}</span> : null}
      </div>
      <p className="mt-1 text-[10px] leading-relaxed text-slate-500">{STATE_DESC[state]}</p>
      {!visited ? <p className="mt-1 text-[10px] text-slate-300">未进入</p> : null}
    </div>
  )
}

export function AgentTrace() {
  const { task } = useSession()
  const visited = useVisited(task)

  if (!task) {
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-bold text-navy-900">Agent 任务执行与决策记录</h1>
        <Card>
          <EmptyState
            icon={<GitBranch className="h-5 w-5" />}
            title="还没有可展示的任务"
            desc="先到「智能配置工作台」提交一条需求，执行过程会在这里按真实事件顺序展示。"
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

  const statusEvents = task.events.filter((event) => event.message.includes('状态变更'))
  const retryPercent = task.params.max_retries
    ? Math.round((task.retry_count / task.params.max_retries) * 100)
    : 0

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-navy-900">Agent 任务执行与决策记录</h1>
          <p className="mt-1 text-sm text-slate-600">
            状态节点、决策与日志均由后端真实执行事件生成，未进入的状态不会标记为已完成。
          </p>
        </div>
        <div className="flex items-center gap-3">
          <TaskPicker />
          <StatusBadge status={task.status} label={task.status_label} />
        </div>
      </div>

      <Card>
        <SectionHeader
          title="任务状态机"
          desc="状态转换由 Python 状态机校验；终态（SUCCESS / FAILED）不允许继续自动执行。"
          action={
            <span className="text-[11px] text-slate-500">
              共 {statusEvents.length} 次状态转换 · 重试 {task.retry_count}/{task.params.max_retries}
            </span>
          }
        />
        <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-slate-400">主流程</p>
        <div className="grid gap-2 sm:grid-cols-3 xl:grid-cols-5">
          {MAIN_FLOW.map((state) => (
            <StateNode
              key={state}
              state={state}
              current={task.status === state}
              count={visited.get(state) ?? 0}
            />
          ))}
        </div>

        <p className="mb-2 mt-4 text-[11px] font-medium uppercase tracking-wide text-slate-400">
          分支与终止状态
        </p>
        <div className="grid gap-2 sm:grid-cols-3 xl:grid-cols-5">
          {BRANCH_FLOW.map((state) => (
            <StateNode
              key={state}
              state={state}
              current={task.status === state}
              count={visited.get(state) ?? 0}
            />
          ))}
        </div>

        <div className="mt-4 rounded-lg bg-slate-50 px-3 py-2">
          <div className="flex items-center justify-between text-[11px] text-slate-500">
            <span className="flex items-center gap-1">
              <RotateCcw className="h-3 w-3" /> 自动修正重试进度
            </span>
            <span>
              {task.retry_count} / {task.params.max_retries}
            </span>
          </div>
          <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-slate-200">
            <div
              className={`h-full rounded-full ${retryPercent >= 100 ? 'bg-rose-500' : 'bg-accent-500'}`}
              style={{ width: `${Math.min(100, retryPercent)}%` }}
            />
          </div>
        </div>
      </Card>

      <div className="grid gap-4 xl:grid-cols-[1.15fr_1fr]">
        <Card>
          <SectionHeader
            title="Agent 决策记录"
            desc="每条决策都说明：当前状态、命中的错误代码、选择的行动与原因。"
            action={<span className="text-[11px] text-slate-500">{task.decisions.length} 条</span>}
          />
          {task.decisions.length === 0 ? (
            <EmptyState title="暂无决策记录" desc="任务尚未进入分析阶段。" />
          ) : (
            <ol className="space-y-3">
              {task.decisions.map((decision) => (
                <li key={decision.step} className="relative rounded-lg border border-slate-200 p-3 pl-4">
                  <span className="absolute left-0 top-3 h-[calc(100%-1.5rem)] w-1 rounded-full bg-navy-800/15" />
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded bg-navy-800 px-2 py-0.5 font-mono text-[10px] text-white">
                      {decision.action}
                    </span>
                    <span className="text-xs font-medium text-slate-700">
                      {ACTION_LABEL[decision.action] ?? decision.action}
                    </span>
                    <StatusBadge status={decision.status} />
                    <span className="ml-auto text-[10px] text-slate-400">步骤 {decision.step}</span>
                  </div>
                  <p className="mt-1.5 text-xs leading-relaxed text-slate-700">{decision.reason}</p>
                  <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[10px] text-slate-500">
                    <span>重试 {decision.retry_count} 次</span>
                    <span>·</span>
                    <span>第 {decision.attempt} 次生成</span>
                    {decision.requires_human_review ? (
                      <>
                        <span>·</span>
                        <span className="text-amber-700">需要人工参与</span>
                      </>
                    ) : null}
                    {decision.error_codes.length > 0 ? (
                      <span className="ml-auto font-mono text-rose-600">
                        {decision.error_codes.join(', ')}
                      </span>
                    ) : null}
                  </div>
                </li>
              ))}
            </ol>
          )}
        </Card>

        <Card>
          <SectionHeader
            title="执行日志"
            desc="按时间顺序记录需求接收、解析、生成、校验与状态变更。"
            action={<span className="text-[11px] text-slate-500">{task.events.length} 条</span>}
          />
          <div className="max-h-[32rem] overflow-auto rounded-lg border border-slate-200">
            <table className="min-w-full text-left text-xs">
              <thead className="sticky top-0 bg-slate-50 text-[11px] text-slate-500">
                <tr>
                  <th className="px-2.5 py-2 font-medium">时间</th>
                  <th className="px-2.5 py-2 font-medium">事件</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {task.events.map((event) => (
                  <tr key={event.seq} className="align-top">
                    <td className="whitespace-nowrap px-2.5 py-2 font-mono text-[11px] text-slate-400">
                      {formatTime(event.at)}
                    </td>
                    <td className="px-2.5 py-2">
                      <div className="flex items-start gap-1.5">
                        <span
                          className={`mt-1 h-1.5 w-1.5 shrink-0 rounded-full ${
                            event.level === 'error'
                              ? 'bg-rose-500'
                              : event.level === 'warning'
                                ? 'bg-amber-500'
                                : event.level === 'success'
                                  ? 'bg-emerald-500'
                                  : 'bg-slate-400'
                          }`}
                        />
                        <div>
                          <p className="leading-relaxed text-slate-700">{event.message}</p>
                          {event.detail ? (
                            <p className="mt-0.5 font-mono text-[10px] leading-relaxed text-slate-400">
                              {event.detail}
                            </p>
                          ) : null}
                        </div>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 flex items-start gap-1.5 text-[11px] leading-relaxed text-slate-500">
            <ListChecks className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            日志只保留工具调用结果与状态变化，不记录模型的隐藏思维链，也不记录任何密钥信息。
          </p>
        </Card>
      </div>

      <Card>
        <SectionHeader title="本次任务的原始需求" desc="任务 ID：" action={<span className="font-mono text-[11px] text-slate-400">{task.id}</span>} />
        <pre className="mono-block whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-slate-700">
          {task.requirement}
        </pre>
        <div className="mt-3 grid gap-2 text-[11px] text-slate-500 sm:grid-cols-4">
          <p className="flex items-center gap-1">
            <Activity className="h-3.5 w-3.5" /> 模式：{task.mode_label}
          </p>
          <p>生成次数：{task.attempts.length}</p>
          <p>演示生成调用：{task.usage.demo_generation_calls}</p>
          <p>真实 API 调用：{task.usage.api_calls}</p>
        </div>
      </Card>
    </div>
  )
}
