import { Check, Circle, Loader2 } from 'lucide-react'
import type { Task, TaskStatus } from '../types'

interface StepDef {
  key: string
  title: string
  desc: string
}

export const PIPELINE_STEPS: StepDef[] = [
  { key: 'input', title: '自然语言需求', desc: '运维人员用中文描述访问控制目标与范围' },
  { key: 'plan', title: 'Agent 任务规划', desc: '检查必要参数、规划生成与校验步骤' },
  { key: 'generate', title: '大模型生成 ACL', desc: '输出统一数据模型的结构化配置' },
  { key: 'validate', title: 'Python 独立校验', desc: '结构、字段值、授权范围与风险规则' },
  { key: 'decide', title: 'Agent 根据结果决策', desc: '通过 / 修正 / 补充信息 / 转人工审核' },
  { key: 'output', title: '输出与处理结果', desc: '待审核配置、拦截原因或需补充的字段' },
]

const STATUS_STEP: Record<TaskStatus, { active: number; done: number[]; note?: string }> = {
  RECEIVED: { active: 0, done: [] },
  ANALYZING: { active: 1, done: [0] },
  NEED_INFO: { active: 1, done: [0], note: '缺少必要信息，等待用户补充（未生成配置）' },
  GENERATING: { active: 2, done: [0, 1] },
  VALIDATING: { active: 3, done: [0, 1, 2] },
  RETRYING: { active: 2, done: [0, 1, 3], note: '根据校验反馈回到生成步骤' },
  REVIEW_REQUIRED: { active: 5, done: [0, 1, 2, 3, 4], note: '已生成候选配置，等待人工审核' },
  SUCCESS: { active: 5, done: [0, 1, 2, 3, 4, 5] },
  FAILED: { active: 5, done: [0, 1, 2, 3, 4], note: '自动处理失败，未产生可采用的配置' },
  BLOCKED: { active: 5, done: [0, 1, 2, 3, 4], note: '命中严重风险，安全策略已拦截' },
}

export function FlowSteps({ task }: { task?: Task | null }) {
  const mapping = task ? STATUS_STEP[task.status] : null
  const active = mapping?.active ?? -1
  const done = new Set(mapping?.done ?? [])

  return (
    <div>
      <ol className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
        {PIPELINE_STEPS.map((step, index) => {
          const isDone = done.has(index)
          const isActive = active === index && !isDone
          const state = isDone ? 'done' : isActive ? 'active' : 'idle'
          return (
            <li
              key={step.key}
              className={`relative rounded-lg border p-3 transition ${
                state === 'done'
                  ? 'border-emerald-200 bg-emerald-50/60'
                  : state === 'active'
                    ? 'border-accent-400 bg-accent-50 shadow-card'
                    : 'border-slate-200 bg-white'
              }`}
              data-state={state}
            >
              <div className="flex items-center gap-2">
                {state === 'done' ? (
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500 text-white">
                    <Check className="h-3 w-3" />
                  </span>
                ) : state === 'active' ? (
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-accent-500 text-white">
                    <Loader2 className="h-3 w-3 animate-spin" />
                  </span>
                ) : (
                  <span className="flex h-5 w-5 items-center justify-center rounded-full border border-slate-300 text-slate-400">
                    <Circle className="h-2 w-2" />
                  </span>
                )}
                <span className="text-[11px] font-semibold text-slate-500">STEP {index + 1}</span>
              </div>
              <p className="mt-2 text-sm font-semibold text-navy-900">{step.title}</p>
              <p className="mt-1 text-[11px] leading-relaxed text-slate-500">{step.desc}</p>
            </li>
          )
        })}
      </ol>
      <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-500">
        {task ? (
          <>
            <span className="chip border border-slate-200 bg-white">
              当前状态：{task.status_label}（{task.status}）
            </span>
            {task.retry_count > 0 ? (
              <span className="chip border border-orange-200 bg-orange-50 text-orange-700">
                已修正 {task.retry_count} / {task.params.max_retries} 次
              </span>
            ) : null}
            {mapping?.note ? <span className="text-slate-600">{mapping.note}</span> : null}
          </>
        ) : (
          <span>当前没有执行中的任务：流程节点会在提交需求后按真实状态逐步点亮。</span>
        )}
      </div>
    </div>
  )
}
