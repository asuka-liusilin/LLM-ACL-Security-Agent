import { ArrowRight, BookOpen, CheckCircle2, CircleDashed, CircleDot, ShieldAlert } from 'lucide-react'
import { Card, SectionHeader } from '../components/ui'
import { useSession } from '../store/SessionContext'

const ARCH_FLOW = [
  { title: '用户输入', desc: '中文描述访问控制需求' },
  { title: 'Agent 任务调度', desc: '检查参数、规划步骤、选择工具' },
  { title: '生成工具', desc: '演示生成器 / 真实模型 API' },
  { title: 'Python 校验工具', desc: '结构 / 取值 / 范围 / 风险' },
  { title: '结果返回 Agent', desc: '结构化 findings 与错误代码' },
  { title: '状态机约束', desc: '校验行动合法性、限制重试' },
]

const OUTCOMES = [
  { title: '输出候选配置', desc: '通过检查，等待或完成人工审核', tone: 'border-emerald-200 bg-emerald-50 text-emerald-800' },
  { title: '反馈修正', desc: '可修正错误 → 重新生成 → 再次校验', tone: 'border-sky-200 bg-sky-50 text-sky-800' },
  { title: '请求补充信息', desc: '关键参数缺失 → NEED_INFO', tone: 'border-amber-200 bg-amber-50 text-amber-800' },
  { title: '人工审核 / 拦截', desc: '高风险或多次失败 → 停止自动处理', tone: 'border-rose-200 bg-rose-50 text-rose-800' },
]

const TECH = [
  { name: 'React 18 + TypeScript + Vite', usage: '前端页面与交互', status: 'done' },
  { name: 'Tailwind CSS', usage: '统一的视觉样式与响应式布局', status: 'done' },
  { name: 'FastAPI + Pydantic', usage: '后端 API 与结构化数据校验', status: 'done' },
  { name: 'Python 标准库 json / ipaddress / re', usage: '独立规则校验模块', status: 'done' },
  { name: 'pytest', usage: '后端自动化测试（64 项）', status: 'done' },
  { name: 'OpenAI 兼容模型客户端', usage: 'API 模式下的配置生成', status: 'partial' },
  { name: '内存任务存储 + localStorage', usage: '任务历史（重启后清空）', status: 'partial' },
  { name: 'SSE / WebSocket 实时推送', usage: '替代当前的轮询机制', status: 'todo' },
  { name: '数据库持久化', usage: '跨重启保存任务与实验结果', status: 'todo' },
  { name: '厂商配置语法转换', usage: '转换为具体设备命令（如华为 / 思科）', status: 'planned' },
  { name: '网络模拟器验证', usage: '在 GNS3 / EVE-NG 中验证真实语义', status: 'planned' },
]

const STATUS_META: Record<string, { label: string; className: string; icon: typeof CheckCircle2 }> = {
  done: { label: '已实现', className: 'border-emerald-200 bg-emerald-50 text-emerald-700', icon: CheckCircle2 },
  partial: { label: '部分实现', className: 'border-amber-200 bg-amber-50 text-amber-700', icon: CircleDot },
  planned: { label: '计划扩展', className: 'border-sky-200 bg-sky-50 text-sky-700', icon: CircleDashed },
  todo: { label: '暂未实现', className: 'border-slate-200 bg-slate-50 text-slate-600', icon: CircleDashed },
}

const STATES = [
  ['RECEIVED', '接收需求', '任务刚创建，尚未分析'],
  ['ANALYZING', '分析需求', '解析地址、协议、动作；判断信息是否充分'],
  ['NEED_INFO', '请求补充信息', '关键信息缺失，等待用户输入，不生成配置'],
  ['GENERATING', '生成配置', '调用生成工具产出候选配置'],
  ['VALIDATING', '校验配置', '执行四项独立检查，返回结构化 findings'],
  ['RETRYING', '反馈修正', '可修正问题且未超次数时回到生成'],
  ['REVIEW_REQUIRED', '人工审核', '通过检查或无法自动判断时等待人工确认'],
  ['SUCCESS', '通过检查', '终态；表示候选配置被确认，未下发设备'],
  ['FAILED', '处理失败', '终态；重试耗尽且无人工审核，或被审核拒绝'],
  ['BLOCKED', '安全拦截', '命中严重风险，禁止自动通过'],
]

export function About() {
  const { health } = useSession()

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold text-navy-900">项目介绍与技术路线</h1>
        <p className="mt-1 text-sm text-slate-600">
          ACL 配置智能生成与安全校验 Agent 原型
        </p>
      </div>

      <Card>
        <SectionHeader title="项目简介" action={<BookOpen className="h-4 w-4 text-slate-400" />} />
        <p className="text-sm leading-7 text-slate-700">
          本项目面向网络运维中的 ACL 配置任务，探索大语言模型、Python 独立校验与 Agent 任务调度相结合的方法。
        </p>
        <p className="mt-2 text-sm leading-7 text-slate-700">
          系统通过自然语言需求理解和结构化配置生成降低人工编写配置的负担，通过独立规则校验识别已知格式错误和预定义风险，
          并利用 Agent 协调反馈修正与异常处理流程。
        </p>
        <p className="mt-2 text-sm leading-7 text-slate-700">
          本原型仅用于研究思路展示和初步功能验证，不直接向真实网络设备下发配置，也不将校验通过视为绝对安全的保证。
        </p>
        <div className="mt-3 grid gap-2 sm:grid-cols-3">
          <div className="rounded-lg bg-slate-50 px-3 py-2">
            <p className="text-[11px] text-slate-500">当前后端模式</p>
            <p className="mt-0.5 text-sm font-semibold text-navy-900">
              {health?.api_mode_available ? 'API 模式可用' : '演示模式'}
            </p>
          </div>
          <div className="rounded-lg bg-slate-50 px-3 py-2">
            <p className="text-[11px] text-slate-500">统一数据模型</p>
            <p className="mt-0.5 text-sm font-semibold text-navy-900">rules[] + default_action</p>
          </div>
          <div className="rounded-lg bg-slate-50 px-3 py-2">
            <p className="text-[11px] text-slate-500">校验维度</p>
            <p className="mt-0.5 text-sm font-semibold text-navy-900">结构 / 取值 / 范围 / 风险</p>
          </div>
        </div>
      </Card>

      <Card>
        <SectionHeader
          title="技术架构"
          desc="生成与校验分离：模型只负责产出候选配置，规则判断由独立 Python 模块完成。"
        />
        <div className="flex flex-col gap-2 lg:flex-row lg:items-stretch">
          {ARCH_FLOW.map((node, index) => (
            <div key={node.title} className="flex flex-1 items-center gap-2">
              <div className="w-full rounded-lg border border-slate-200 bg-white p-2.5">
                <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                  STEP {index + 1}
                </p>
                <p className="mt-0.5 text-xs font-semibold text-navy-900">{node.title}</p>
                <p className="mt-0.5 text-[10px] leading-relaxed text-slate-500">{node.desc}</p>
              </div>
              {index < ARCH_FLOW.length - 1 ? (
                <ArrowRight className="hidden h-4 w-4 shrink-0 text-slate-300 lg:block" />
              ) : null}
            </div>
          ))}
        </div>

        <p className="mb-2 mt-4 text-[11px] font-medium uppercase tracking-wide text-slate-400">四种出口</p>
        <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
          {OUTCOMES.map((item) => (
            <div key={item.title} className={`rounded-lg border px-3 py-2 ${item.tone}`}>
              <p className="text-xs font-semibold">{item.title}</p>
              <p className="mt-0.5 text-[10px] leading-relaxed opacity-90">{item.desc}</p>
            </div>
          ))}
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-[1.2fr_1fr]">
        <Card>
          <SectionHeader title="技术栈与实际状态" desc="状态按真实代码维护，未接入的部分不会标记为已实现。" />
          <div className="overflow-x-auto rounded-lg border border-slate-200">
            <table className="min-w-full text-left text-xs">
              <thead className="bg-slate-50 text-[11px] text-slate-500">
                <tr>
                  <th className="px-2.5 py-2 font-medium">技术</th>
                  <th className="px-2.5 py-2 font-medium">用途</th>
                  <th className="px-2.5 py-2 font-medium">状态</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {TECH.map((item) => {
                  const meta = STATUS_META[item.status]
                  const Icon = meta.icon
                  return (
                    <tr key={item.name}>
                      <td className="px-2.5 py-2 font-medium text-slate-800">{item.name}</td>
                      <td className="px-2.5 py-2 text-slate-600">{item.usage}</td>
                      <td className="whitespace-nowrap px-2.5 py-2">
                        <span className={`chip border ${meta.className}`}>
                          <Icon className="h-3 w-3" />
                          {meta.label}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </Card>

        <div className="space-y-4">
          <Card>
            <SectionHeader title="任务状态机" desc="未列出的状态转换一律被 Python 状态机拒绝。" />
            <div className="max-h-80 overflow-auto">
              <table className="min-w-full text-left text-[11px]">
                <tbody className="divide-y divide-slate-100">
                  {STATES.map(([code, name, desc]) => (
                    <tr key={code}>
                      <td className="whitespace-nowrap py-1.5 pr-2 font-mono text-slate-700">{code}</td>
                      <td className="whitespace-nowrap py-1.5 pr-2 text-slate-800">{name}</td>
                      <td className="py-1.5 leading-relaxed text-slate-500">{desc}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <Card className="!border-rose-200 !bg-rose-50/40">
            <p className="flex items-start gap-2 text-xs leading-relaxed text-rose-900">
              <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
              <span>
                <span className="font-semibold">安全边界：</span>
                不连接真实设备、不自动下发配置、不要求设备管理员密码、不在前端保存模型 Key、
                不把模型输出直接当作命令执行；高风险配置进入拦截或人工审核，且不能被普通重试绕过。
              </span>
            </p>
          </Card>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <SectionHeader title="已完成的核心能力" />
          <ul className="space-y-2 text-xs leading-relaxed text-slate-700">
            <li className="flex gap-2">
              <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-600" />
              统一 ACL 数据模型（Pydantic），字段类型与额外字段均被约束。
            </li>
            <li className="flex gap-2">
              <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-600" />
              四项独立校验：结构、字段值、授权范围符合度、预定义风险规则，返回错误代码与建议。
            </li>
            <li className="flex gap-2">
              <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-600" />
              状态机管理 10 个状态、限制重试次数、记录每次转换原因与重试计数。
            </li>
            <li className="flex gap-2">
              <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-600" />
              Agent 根据错误类型选择重新生成 / 请求补充 / 转人工，并解释原因。
            </li>
            <li className="flex gap-2">
              <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-600" />
              12 条内置用例 + 三组对比流水线 + 后端指标计算，全部来自真实执行。
            </li>
            <li className="flex gap-2">
              <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-600" />
              演示模式无需 API Key，所有结果标注为演示数据，稳定性可重复。
            </li>
          </ul>
        </Card>

        <Card>
          <SectionHeader title="已知局限与后续工作" />
          <ul className="space-y-2 text-xs leading-relaxed text-slate-700">
            <li className="flex gap-2">
              <CircleDot className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-600" />
              需求解析基于规则，只能处理结构较明确的中文表述；复杂表述会进入 NEED_INFO 或标记无法判断。
            </li>
            <li className="flex gap-2">
              <CircleDot className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-600" />
              风险规则集仅覆盖少量可解释模式（any-any、默认放行、范围扩大等），不能替代完整安全审计。
            </li>
            <li className="flex gap-2">
              <CircleDot className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-600" />
              未校验 ACL 规则顺序、应用方向与设备语义，也没有真实网络环境验证。
            </li>
            <li className="flex gap-2">
              <CircleDot className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-600" />
              API 模式已实现调用与错误处理，但缺少 Key 时不可用；Token 与成本需真实调用后才统计。
            </li>
            <li className="flex gap-2">
              <CircleDot className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-600" />
              任务存储为内存 + localStorage，后端重启后历史详情丢失；实验样本量小，指标仅供参考。
            </li>
            <li className="flex gap-2">
              <CircleDot className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-600" />
              后续计划：接入真实模型进行对比实验、扩展风险规则、支持厂商语法转换与模拟器验证。
            </li>
          </ul>
        </Card>
      </div>
    </div>
  )
}
