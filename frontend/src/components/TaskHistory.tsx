import { History, ListFilter } from 'lucide-react'
import { useSession } from '../store/SessionContext'
import type { Task } from '../types'
import { EmptyState, StatusBadge, formatDateTime } from './ui'

export function TaskHistoryList({
  currentId,
  onOpen,
  emptyHint,
}: {
  currentId?: string
  onOpen?: (task: Task) => void
  emptyHint?: string
}) {
  const { history, selectTask, clearHistory } = useSession()

  if (history.length === 0) {
    return (
      <EmptyState
        icon={<History className="h-5 w-5" />}
        title="本次会话还没有任务记录"
        desc={
          emptyHint ??
          '在工作台提交一条需求后，任务会出现在这里。历史仅保存在浏览器本地，后端重启后任务详情会清空。'
        }
      />
    )
  }

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs text-slate-500">共 {history.length} 条（仅本次会话，最多保留 8 条）</span>
        <button type="button" onClick={clearHistory} className="text-xs text-slate-500 hover:text-rose-600">
          清空历史
        </button>
      </div>
      <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white">
        {history.map((item) => (
          <li key={item.id}>
            <button
              type="button"
              onClick={async () => {
                await selectTask(item.id)
                onOpen?.(item)
              }}
              className={`flex w-full flex-col gap-1.5 px-3 py-2.5 text-left transition hover:bg-slate-50 ${
                item.id === currentId ? 'bg-accent-50/60' : ''
              }`}
            >
              <div className="flex items-center gap-2">
                <StatusBadge status={item.status} label={item.status_label} />
                <span className="font-mono text-[11px] text-slate-400">{item.id}</span>
                <span className="ml-auto text-[11px] text-slate-400">{formatDateTime(item.created_at)}</span>
              </div>
              <p className="line-clamp-2 text-xs leading-relaxed text-slate-600">{item.requirement}</p>
              <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-400">
                <span>{item.mode_label}</span>
                <span>·</span>
                <span>生成 {item.attempts.length} 次</span>
                {item.retry_count > 0 ? (
                  <>
                    <span>·</span>
                    <span>修正 {item.retry_count} 次</span>
                  </>
                ) : null}
                {item.final_validation ? (
                  <>
                    <span>·</span>
                    <span>{item.final_validation.findings.length} 条检查项</span>
                  </>
                ) : null}
              </div>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function TaskPicker() {
  const { history, task, selectTask } = useSession()
  if (history.length === 0) return null
  return (
    <label className="flex items-center gap-2 text-xs text-slate-500">
      <ListFilter className="h-3.5 w-3.5" />
      切换任务
      <select
        className="input !w-auto !py-1 !text-xs"
        value={task?.id ?? ''}
        onChange={(event) => {
          if (event.target.value) void selectTask(event.target.value)
        }}
      >
        <option value="">请选择</option>
        {history.map((item) => (
          <option key={item.id} value={item.id}>
            {item.id} · {item.status_label} · {item.requirement.slice(0, 18)}
          </option>
        ))}
      </select>
    </label>
  )
}
