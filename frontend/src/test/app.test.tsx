import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import { Workbench } from '../pages/Workbench'
import { SessionProvider } from '../store/SessionContext'
import type { Task } from '../types'

const HEALTH = {
  status: 'ok',
  mode: 'demo',
  api_mode_available: false,
  model: null,
  version: '0.1.0',
  notices: ['本原型只生成与检查配置，不连接、不下发任何真实网络设备。'],
}

function makeTask(overrides: Partial<Task> = {}): Task {
  return {
    id: 'task-test01',
    requirement: '允许 192.168.1.10 访问 10.0.0.10 的 HTTPS 服务。',
    params: {
      mode: 'demo',
      max_retries: 2,
      enable_feedback_fix: true,
      enable_high_risk_block: true,
      require_human_review: true,
    },
    status: 'REVIEW_REQUIRED',
    status_label: '需要人工审核',
    created_at: new Date().toISOString(),
    started_at: new Date().toISOString(),
    finished_at: new Date().toISOString(),
    duration_ms: 320,
    intent: {
      text: '允许 192.168.1.10 访问 10.0.0.10 的 HTTPS 服务。',
      parse_mode: 'demo-rule',
      action: 'permit',
      protocol: 'tcp',
      destination_port: 443,
      sources: ['192.168.1.10/32'],
      destinations: ['10.0.0.10/32'],
      default_action: null,
      missing: [],
      invalid_values: [],
      assumptions: [],
      notes: [],
      widen_source_hint: null,
      widen_destination_hint: null,
      any_any: false,
      stubborn_widen: false,
      service_label: 'HTTPS',
    },
    attempts: [
      {
        index: 1,
        kind: 'initial',
        note: '演示模式生成',
        raw: '{}',
        config: {
          rules: [
            {
              action: 'permit',
              protocol: 'tcp',
              source: '192.168.1.10/32',
              destination: '10.0.0.10/32',
              destination_port: 443,
            },
          ],
          default_action: 'deny',
        },
        validation: {
          passed: true,
          status_suggestion: 'SUCCESS',
          findings: [],
          checks: [
            { key: 'A', name: 'JSON 结构与字段完整性', status: 'PASS', status_label: '通过', severity: null, summary: 'ok', findings: [] },
            { key: 'B', name: '字段值合法性', status: 'PASS', status_label: '通过', severity: null, summary: 'ok', findings: [] },
            { key: 'C', name: '授权范围与需求符合度', status: 'PASS', status_label: '通过', severity: null, summary: 'ok', findings: [] },
            { key: 'D', name: '预定义高风险规则', status: 'PASS', status_label: '通过', severity: null, summary: 'ok', findings: [] },
          ],
          summary: { INFO: 0, LOW: 0, MEDIUM: 0, HIGH: 0, CRITICAL: 0 },
          rules_evaluated: 1,
          config_parsed: true,
        },
        created_at: new Date().toISOString(),
        generation_source: 'demo',
        error: null,
      },
    ],
    events: [
      { seq: 1, at: new Date().toISOString(), level: 'info', status: 'RECEIVED', message: '接收用户需求。', detail: null },
      { seq: 2, at: new Date().toISOString(), level: 'info', status: 'ANALYZING', message: '状态变更：RECEIVED → ANALYZING。开始分析需求。', detail: null },
      { seq: 3, at: new Date().toISOString(), level: 'warning', status: 'REVIEW_REQUIRED', message: '状态变更：VALIDATING → REVIEW_REQUIRED。等待人工审核。', detail: null },
    ],
    decisions: [
      {
        step: 1,
        status: 'REVIEW_REQUIRED',
        error_codes: [],
        action: 'REQUEST_HUMAN_REVIEW',
        reason: 'Python 校验未发现中高风险问题，但按任务参数仍需人工审核。',
        requires_human_review: true,
        retry_count: 0,
        attempt: 1,
      },
    ],
    missing_fields: [],
    review: null,
    usage: { demo_generation_calls: 1, api_calls: 0, prompt_tokens: null, completion_tokens: null },
    retry_count: 0,
    origin: 'manual',
    test_case_id: null,
    deployed: false,
    final_config: {
      rules: [
        {
          action: 'permit',
          protocol: 'tcp',
          source: '192.168.1.10/32',
          destination: '10.0.0.10/32',
          destination_port: 443,
        },
      ],
      default_action: 'deny',
    },
    final_validation: null,
    token_display: '未统计（演示模式）',
    mode_label: '演示模式',
    is_terminal: false,
    awaiting_user: false,
    awaiting_review: true,
    ...overrides,
  }
}

function jsonResponse(body: unknown, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }),
  )
}

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    if (url.endsWith('/api/health')) return jsonResponse(HEALTH)
    if (url.includes('/api/tasks') && init?.method === 'POST') return jsonResponse(makeTask(), 201)
    if (url.includes('/api/tasks/')) return jsonResponse(makeTask())
    if (url.includes('/api/metrics')) {
      return jsonResponse({ status: 'NOT_RUN', mode: null, generated_at: null, case_count: 0, groups: [], notices: [] })
    }
    if (url.includes('/api/test-cases')) return jsonResponse({ items: [], total: 0, notice: '' })
    return jsonResponse({ detail: 'not found' }, 404)
  }))
})

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe('页面基础渲染', () => {
  it('后端不可用时显示可读提示而不是崩溃', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('network down'))))
    render(<App />)
    expect(await screen.findByText(/后端未连接/)).toBeInTheDocument()
  })

  it('总览页可以加载并显示导航', async () => {
    render(<App />)
    const headings = await screen.findAllByRole('heading', { name: 'ACL 智能运维与安全校验 Agent' })
    expect(headings.length).toBeGreaterThan(0)
    expect(screen.getAllByRole('link', { name: '智能配置工作台' }).length).toBeGreaterThan(0)
    expect((await screen.findAllByText('演示模式')).length).toBeGreaterThan(0)
  })

  it('示例需求可以填入输入框', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <SessionProvider>
          <Workbench />
        </SessionProvider>
      </MemoryRouter>,
    )
    const example = await screen.findByText('正常需求')
    await user.click(example)
    const textarea = screen.getByPlaceholderText(/请描述你的网络访问控制需求/) as HTMLTextAreaElement
    expect(textarea.value).toContain('192.168.1.10')
  })

  it('提交任务后展示结构化配置与校验结果', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <SessionProvider>
          <Workbench />
        </SessionProvider>
      </MemoryRouter>,
    )
    const textarea = screen.getByPlaceholderText(/请描述你的网络访问控制需求/)
    await user.type(textarea, '允许 192.168.1.10 访问 10.0.0.10 的 HTTPS 服务。')
    await user.click(screen.getByRole('button', { name: /开始分析并生成配置/ }))

    await waitFor(() => expect(screen.getByText('结构化 ACL 配置')).toBeInTheDocument())
    expect(screen.getByText('Python 校验结果')).toBeInTheDocument()
    expect(screen.getAllByText('192.168.1.10/32').length).toBeGreaterThan(0)
    expect(screen.getAllByText('需要人工审核').length).toBeGreaterThan(0)
  })

  it('任务历史可以打开并展示缓存结果', async () => {
    const user = userEvent.setup()
    const cached = makeTask()
    localStorage.setItem('acl-agent-history-v1', JSON.stringify([cached]))
    render(
      <MemoryRouter>
        <SessionProvider>
          <Workbench />
        </SessionProvider>
      </MemoryRouter>,
    )
    expect(await screen.findByText('共 1 条（仅本次会话，最多保留 8 条）')).toBeInTheDocument()
    const item = screen.getByRole('button', { name: /允许 192.168.1.10 访问/ })
    await user.click(item)
    expect(await screen.findByText('未下发任何设备')).toBeInTheDocument()
  })

  it('空输入不会提交并给出提示', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <SessionProvider>
          <Workbench />
        </SessionProvider>
      </MemoryRouter>,
    )
    await user.click(screen.getByRole('button', { name: /开始分析并生成配置/ }))
    expect(await screen.findByText('请先输入访问控制需求，或点击下方示例。')).toBeInTheDocument()
  })
})
