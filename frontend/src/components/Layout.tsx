import {
  BookOpen,
  FlaskConical,
  GitBranch,
  LayoutDashboard,
  ShieldCheck,
  Sparkles,
  Terminal,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { Link, NavLink, useLocation } from 'react-router-dom'
import { useSession } from '../store/SessionContext'
import { ToastHost } from './ui'

const NAV = [
  { to: '/', label: '项目总览', icon: LayoutDashboard, end: true },
  { to: '/workbench', label: '智能配置工作台', icon: Terminal },
  { to: '/trace', label: 'Agent 执行过程', icon: GitBranch },
  { to: '/report', label: '安全校验报告', icon: ShieldCheck },
  { to: '/tests', label: '测试用例与实验', icon: FlaskConical },
  { to: '/about', label: '项目说明', icon: BookOpen },
]

export function Layout({ children }: { children: ReactNode }) {
  const { health, healthError, task } = useSession()
  const location = useLocation()
  const modeLabel = health?.api_mode_available ? 'API 模式可用' : '演示模式'
  const online = Boolean(health) && !healthError

  return (
    <div className="min-h-screen bg-slate-100">
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-60 flex-col bg-navy-900 text-slate-300 lg:flex">
        <Link to="/" className="flex items-center gap-2.5 border-b border-white/10 px-5 py-5">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent-500/15 text-accent-400">
            <ShieldCheck className="h-5 w-5" />
          </span>
          <span>
            <span className="block text-sm font-semibold text-white">ACL Agent</span>
            <span className="block text-[11px] text-slate-400">智能生成 · 独立校验</span>
          </span>
        </Link>

        <nav className="flex-1 space-y-1 px-3 py-4">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm transition ${
                  isActive
                    ? 'bg-white/10 font-medium text-white'
                    : 'text-slate-300 hover:bg-white/5 hover:text-white'
                }`
              }
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-white/10 px-4 py-4 text-[11px] leading-relaxed text-slate-400">
          <p className="flex items-center gap-1.5 text-slate-300">
            <Sparkles className="h-3.5 w-3.5 text-accent-400" />
            本科毕业设计原型
          </p>
          <p className="mt-1.5">只生成与检查配置，不连接、不下发任何真实网络设备。</p>
        </div>
      </aside>

      <div className="lg:pl-60">
        <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/90 backdrop-blur">
          <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-3 px-4 py-3 lg:px-8">
            <div className="min-w-0 flex-1">
              <h1 className="truncate text-sm font-semibold text-navy-900 lg:text-base">
                ACL 智能运维与安全校验 Agent
              </h1>
              <p className="hidden truncate text-[11px] text-slate-500 sm:block">
                自然语言配置生成 · Python 独立校验 · Agent 受约束任务调度
              </p>
            </div>

            <div className="flex items-center gap-2">
              <span
                className={`chip border ${
                  health?.api_mode_available
                    ? 'border-indigo-200 bg-indigo-50 text-indigo-700'
                    : 'border-accent-100 bg-accent-50 text-accent-600'
                }`}
                title={health?.api_mode_available ? `模型：${health.model ?? '未提供'}` : '未配置 LLM_API_KEY'}
              >
                {modeLabel}
              </span>
              <span
                className={`chip border ${
                  online
                    ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                    : 'border-rose-200 bg-rose-50 text-rose-700'
                }`}
                title={healthError ?? '后端 /api/health 正常'}
              >
                <span className={`h-1.5 w-1.5 rounded-full ${online ? 'bg-emerald-500' : 'bg-rose-500'}`} />
                {online ? '后端已连接' : '后端未连接'}
              </span>
              {task ? (
                <Link
                  to="/trace"
                  className="hidden items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-1 text-xs text-slate-600 hover:bg-slate-50 sm:flex"
                >
                  当前任务 · {task.status_label}
                </Link>
              ) : null}
              {location.pathname !== '/about' ? (
                <Link to="/about" className="btn-ghost !px-2.5 !py-1 !text-xs">
                  <BookOpen className="h-3.5 w-3.5" />
                  项目介绍
                </Link>
              ) : null}
            </div>
          </div>

          <nav className="flex gap-1 overflow-x-auto border-t border-slate-100 px-3 pb-2 pt-1 lg:hidden">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `whitespace-nowrap rounded-full px-3 py-1.5 text-xs ${
                    isActive ? 'bg-navy-800 text-white' : 'bg-slate-100 text-slate-600'
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </header>

        <main className="mx-auto max-w-7xl px-4 pb-16 pt-6 lg:px-8">{children}</main>

        <footer className="border-t border-slate-200 bg-white px-4 py-4 text-center text-[11px] leading-relaxed text-slate-500 lg:px-8">
          本原型仅用于研究思路展示与功能验证：不连接真实网络设备、不自动下发配置，
          校验通过不代表配置绝对安全。
        </footer>
      </div>

      <ToastHost />
    </div>
  )
}
