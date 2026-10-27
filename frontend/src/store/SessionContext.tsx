import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { api, ApiError } from '../services/api'
import type { Health, ReviewDecision, Task, TaskParams } from '../types'

const HISTORY_KEY = 'acl-agent-history-v1'
const HISTORY_LIMIT = 8

export interface ToastItem {
  id: number
  kind: 'success' | 'error' | 'info'
  message: string
}

interface SessionValue {
  health: Health | null
  healthError: string | null
  refreshHealth: () => Promise<void>
  task: Task | null
  history: Task[]
  submitting: boolean
  busy: string | null
  toasts: ToastItem[]
  notify: (kind: ToastItem['kind'], message: string) => void
  dismissToast: (id: number) => void
  submit: (requirement: string, params: TaskParams) => Promise<Task | null>
  sendFeedback: (message: string) => Promise<void>
  sendReview: (decision: ReviewDecision, comment: string, reviewer: string) => Promise<void>
  selectTask: (id: string) => Promise<void>
  clearHistory: () => void
}

const SessionContext = createContext<SessionValue | null>(null)

function loadHistory(): Task[] {
  try {
    const raw = localStorage.getItem(HISTORY_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed.slice(0, HISTORY_LIMIT) : []
  } catch {
    return []
  }
}

function saveHistory(items: Task[]) {
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(items.slice(0, HISTORY_LIMIT)))
  } catch {
    /* 本地存储不可用时忽略，不影响主流程 */
  }
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [health, setHealth] = useState<Health | null>(null)
  const [healthError, setHealthError] = useState<string | null>(null)
  const [task, setTask] = useState<Task | null>(null)
  const [history, setHistory] = useState<Task[]>(() => loadHistory())
  const [submitting, setSubmitting] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)
  const [toasts, setToasts] = useState<ToastItem[]>([])
  const timerRef = useRef<number | null>(null)

  const notify = useCallback((kind: ToastItem['kind'], message: string) => {
    const id = Date.now() + Math.random()
    setToasts((prev) => [...prev, { id, kind, message }])
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, 5200)
  }, [])

  const dismissToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const refreshHealth = useCallback(async () => {
    try {
      const data = await api.health()
      setHealth(data)
      setHealthError(null)
    } catch (error) {
      setHealth(null)
      setHealthError(error instanceof Error ? error.message : '后端状态未知')
    }
  }, [])

  useEffect(() => {
    void refreshHealth()
  }, [refreshHealth])

  const stopPolling = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current)
      timerRef.current = null
    }
  }, [])

  const upsertHistory = useCallback((next: Task) => {
    setHistory((prev) => {
      const others = prev.filter((item) => item.id !== next.id)
      const merged = [next, ...others].slice(0, HISTORY_LIMIT)
      saveHistory(merged)
      return merged
    })
  }, [])

  const startPolling = useCallback(
    (taskId: string) => {
      stopPolling()
      let ticks = 0
      timerRef.current = window.setInterval(async () => {
        ticks += 1
        try {
          const latest = await api.getTask(taskId)
          setTask((current) => (current && current.id === latest.id ? latest : current))
          upsertHistory(latest)
          const settled =
            latest.is_terminal || latest.status === 'NEED_INFO' || latest.status === 'REVIEW_REQUIRED' || latest.status === 'BLOCKED'
          if (settled || ticks > 120) stopPolling()
        } catch (error) {
          stopPolling()
          if (error instanceof ApiError && error.status === 404) {
            notify('error', '任务在后端已不存在（后端可能重启过），当前展示的是本地缓存结果。')
          } else {
            notify('error', error instanceof Error ? error.message : '轮询任务状态失败')
          }
        }
      }, 650)
    },
    [notify, stopPolling, upsertHistory],
  )

  useEffect(() => () => stopPolling(), [stopPolling])

  const submit = useCallback(
    async (requirement: string, params: TaskParams) => {
      if (submitting) return null
      setSubmitting(true)
      try {
        const created = await api.createTask(requirement, params)
        setTask(created)
        upsertHistory(created)
        startPolling(created.id)
        return created
      } catch (error) {
        notify('error', error instanceof Error ? error.message : '创建任务失败')
        return null
      } finally {
        setSubmitting(false)
      }
    },
    [notify, startPolling, submitting, upsertHistory],
  )

  const sendFeedback = useCallback(
    async (message: string) => {
      if (!task) return
      setBusy('feedback')
      try {
        const updated = await api.submitFeedback(task.id, message)
        setTask(updated)
        upsertHistory(updated)
        startPolling(updated.id)
        notify('success', '已提交补充信息，任务继续处理。')
      } catch (error) {
        notify('error', error instanceof Error ? error.message : '提交补充信息失败')
      } finally {
        setBusy(null)
      }
    },
    [notify, startPolling, task, upsertHistory],
  )

  const sendReview = useCallback(
    async (decision: ReviewDecision, comment: string, reviewer: string) => {
      if (!task) return
      setBusy('review')
      try {
        const updated = await api.submitReview(task.id, decision, comment, reviewer)
        setTask(updated)
        upsertHistory(updated)
        notify('success', '审核意见已提交。审核通过只代表确认候选配置，未下发任何设备。')
      } catch (error) {
        notify('error', error instanceof Error ? error.message : '提交审核意见失败')
      } finally {
        setBusy(null)
      }
    },
    [notify, task, upsertHistory],
  )

  const selectTask = useCallback(
    async (id: string) => {
      stopPolling()
      const cached = history.find((item) => item.id === id) ?? null
      if (cached) setTask(cached)
      try {
        const latest = await api.getTask(id)
        setTask(latest)
        upsertHistory(latest)
        if (!latest.is_terminal && latest.status !== 'NEED_INFO' && latest.status !== 'REVIEW_REQUIRED') {
          startPolling(latest.id)
        }
      } catch (error) {
        if (cached) {
          notify('info', '后端没有这条任务记录（重启后内存会清空），当前展示本地缓存。')
        } else {
          notify('error', error instanceof Error ? error.message : '读取任务失败')
        }
      }
    },
    [history, notify, startPolling, stopPolling, upsertHistory],
  )

  const clearHistory = useCallback(() => {
    stopPolling()
    setHistory([])
    setTask(null)
    saveHistory([])
    notify('info', '已清空本次会话的任务历史（不影响后端记录）。')
  }, [notify, stopPolling])

  const value = useMemo<SessionValue>(
    () => ({
      health,
      healthError,
      refreshHealth,
      task,
      history,
      submitting,
      busy,
      toasts,
      notify,
      dismissToast,
      submit,
      sendFeedback,
      sendReview,
      selectTask,
      clearHistory,
    }),
    [
      health,
      healthError,
      refreshHealth,
      task,
      history,
      submitting,
      busy,
      toasts,
      notify,
      dismissToast,
      submit,
      sendFeedback,
      sendReview,
      selectTask,
      clearHistory,
    ],
  )

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}

export function useSession(): SessionValue {
  const ctx = useContext(SessionContext)
  if (!ctx) throw new Error('useSession 必须在 SessionProvider 内使用')
  return ctx
}
