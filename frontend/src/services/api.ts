import type {
  Health,
  Metrics,
  ReviewDecision,
  Task,
  TaskParams,
  TestCase,
  TestRunResponse,
} from '../types'

export class ApiError extends Error {
  status: number
  constructor(message: string, status = 0) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

const BASE = 'https://llm-acl-backend.onrender.com'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${BASE}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...init,
    })
  } catch {
    throw new ApiError('无法连接后端服务，请确认 FastAPI 已在 https://llm-acl-backend.onrender.com 启动。')
  }

  const text = await response.text()
  let payload: any = null
  if (text) {
    try {
      payload = JSON.parse(text)
    } catch {
      payload = null
    }
  }
  if (!response.ok) {
    const detail =
      (payload && typeof payload.detail === 'string' && payload.detail) ||
      `请求失败（HTTP ${response.status}）`
    throw new ApiError(detail, response.status)
  }
  return payload as T
}

export const api = {
  health: () => request<Health>('/health'),

  createTask: (requirement: string, params: TaskParams) =>
    request<Task>('/tasks', {
      method: 'POST',
      body: JSON.stringify({ requirement, params }),
    }),

  getTask: (id: string) => request<Task>(`/tasks/${id}`),

  listTasks: () => request<{ items: any[] }>('/tasks'),

  submitFeedback: (id: string, message: string) =>
    request<Task>(`/tasks/${id}/feedback`, {
      method: 'POST',
      body: JSON.stringify({ message }),
    }),

  submitReview: (id: string, decision: ReviewDecision, comment: string, reviewer: string) =>
    request<Task>(`/tasks/${id}/review`, {
      method: 'POST',
      body: JSON.stringify({ decision, comment, reviewer }),
    }),

  testCases: () => request<{ items: TestCase[]; total: number; notice: string }>('/test-cases'),

  runTestCases: (caseIds: string[] | null, group: 'basic' | 'validate' | 'agent') =>
    request<TestRunResponse>('/test-cases/run', {
      method: 'POST',
      body: JSON.stringify({ case_ids: caseIds, group }),
    }),

  metrics: () => request<Metrics>('/metrics'),

  runExperiment: () => request<Metrics>('/experiments/run', { method: 'POST' }),

  resetExperiment: () => request<{ status: string; detail: string }>('/experiments/reset', { method: 'POST' }),
}
