import { BarChart3, ChevronDown, FlaskConical, Play, RefreshCw, HelpCircle } from 'lucide-react'
import { Fragment, useCallback, useEffect, useState } from 'react'
import { api } from '../services/api'
import { Card, EmptyState, SectionHeader, Spinner, StatusBadge, formatDateTime } from '../components/ui'
import { useSession } from '../store/SessionContext'
import type { CaseRunResult, Metrics, TestCase } from '../types'

const GROUPS = [
  { value: 'agent', label: 'C 组 · Agent 闭环' },
  { value: 'validate', label: 'B 组 · 生成 + 独立校验' },
  { value: 'basic', label: 'A 组 · 基础生成' },
] as const

type GroupValue = (typeof GROUPS)[number]['value']

function ResultBadge({ result }: { result: CaseRunResult }) {
  return (
    <span
      className={`chip border ${
        result.matched_expected
          ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
          : 'border-rose-200 bg-rose-50 text-rose-700'
      }`}
    >
      {result.matched_expected ? '符合预期' : '不符合预期'}
    </span>
  )
}

export function TestCasesPage() {
  const { notify } = useSession()
  const [cases, setCases] = useState<TestCase[]>([])
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [group, setGroup] = useState<GroupValue>('agent')
  const [runningId, setRunningId] = useState<string | null>(null)
  const [batch, setBatch] = useState<{ passed: number; total: number; notice: string } | null>(null)
  const [results, setResults] = useState<Record<string, CaseRunResult>>({})
  const [expanded, setExpanded] = useState<string | null>(null)
  const [metricBusy, setMetricBusy] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [caseData, metricData] = await Promise.all([api.testCases(), api.metrics()])
      setCases(caseData.items)
      setMetrics(metricData)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载测试用例失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const runOne = async (caseId: string) => {
    setRunningId(caseId)
    try {
      const data = await api.runTestCases([caseId], group)
      const result = data.results[0]
      setResults((prev) => ({ ...prev, [caseId]: result }))
      setBatch({ passed: data.passed, total: data.total, notice: data.notice })
      setExpanded(caseId)
      setMetrics(await api.metrics())
    } catch (err) {
      notify('error', err instanceof Error ? err.message : '运行用例失败')
    } finally {
      setRunningId(null)
    }
  }

  const runAll = async () => {
    setRunningId('__all__')
    try {
      const data = await api.runTestCases(null, group)
      const map: Record<string, CaseRunResult> = {}
      data.results.forEach((item) => {
        map[item.case_id] = item
      })
      setResults(map)
      setBatch({ passed: data.passed, total: data.total, notice: data.notice })
      setMetrics(await api.metrics())
      notify('success', `${data.group_label} 执行完成：${data.passed}/${data.total} 符合预期。`)
    } catch (err) {
      notify('error', err instanceof Error ? err.message : '批量执行失败')
    } finally {
      setRunningId(null)
    }
  }

  const runExperiment = async () => {
    setMetricBusy(true)
    try {
      const data = await api.runExperiment()
      setMetrics(data)
      notify('success', '三组对比实验已在本机完成，指标来自真实执行结果。')
    } catch (err) {
      notify('error', err instanceof Error ? err.message : '运行实验失败')
    } finally {
      setMetricBusy(false)
    }
  }

  const resetMetrics = async () => {
    setMetricBusy(true)
    try {
      await api.resetExperiment()
      setMetrics(await api.metrics())
      setResults({})
      setBatch(null)
      notify('info', '已清除统计记录。')
    } catch (err) {
      notify('error', err instanceof Error ? err.message : '清除统计失败')
    } finally {
      setMetricBusy(false)
    }
  }

  const matched = Object.values(results).filter((item) => item.matched_expected).length
  const executed = Object.keys(results).length

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold text-navy-900">测试用例与实验评估</h1>
        <p className="mt-1 max-w-3xl text-sm leading-relaxed text-slate-600">
          内置 {cases.length || '若干'} 条人工标注用例，覆盖正常需求、参数错误、授权范围扩大、宽泛放行、反馈修正与安全边界。
          演示模式下的执行结果只反映原型行为，不是真实大模型实验结论。
        </p>
      </div>

      {error ? (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
          加载失败：{error}
          <button type="button" onClick={() => void load()} className="ml-2 underline">
            重试
          </button>
        </div>
      ) : null}

      <Card>
        <SectionHeader
          title="测试执行"
          desc="选择流水线分组后运行单个用例或全部用例；结果会写入指标统计。"
          action={
            <div className="flex flex-wrap items-center gap-2">
              <select
                className="input !w-auto !py-1.5 !text-xs"
                value={group}
                onChange={(event) => {
                  setGroup(event.target.value as GroupValue)
                  setResults({})
                  setBatch(null)
                }}
                disabled={runningId !== null}
              >
                {GROUPS.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
              <button type="button" className="btn-primary !py-1.5 !text-xs" onClick={runAll} disabled={runningId !== null}>
                {runningId === '__all__' ? <Spinner className="!h-3.5 !w-3.5" /> : <Play className="h-3.5 w-3.5" />}
                运行全部用例
              </button>
            </div>
          }
        />

        {batch ? (
          <div className="mb-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs leading-relaxed text-slate-600">
            <p className="font-medium text-slate-800">
              {batch.notice} 本轮 {executed} 条已执行，{matched} 条符合预期（{batch.passed}/{batch.total}）。
            </p>
          </div>
        ) : null}

        {loading ? (
          <div className="flex items-center gap-2 py-6 text-sm text-slate-500">
            <Spinner /> 正在加载测试用例…
          </div>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-slate-200">
            <table className="min-w-full text-left text-xs">
              <thead className="bg-slate-50 text-[11px] text-slate-500">
                <tr>
                  <th className="px-2.5 py-2 font-medium">用例</th>
                  <th className="px-2.5 py-2 font-medium">类别</th>
                  <th className="px-2.5 py-2 font-medium">预期状态</th>
                  <th className="px-2.5 py-2 font-medium">实际状态</th>
                  <th className="px-2.5 py-2 font-medium">结论</th>
                  <th className="px-2.5 py-2 font-medium">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {cases.map((item) => {
                  const result = results[item.id] ?? item.last_results?.[group]
                  const isOpen = expanded === item.id
                  return (
                    <Fragment key={item.id}>
                      <tr className="align-top">
                        <td className="px-2.5 py-2">
                          <p className="font-mono text-[11px] text-slate-500">{item.id}</p>
                          <p className="text-xs font-medium text-slate-800">{item.name}</p>
                        </td>
                        <td className="whitespace-nowrap px-2.5 py-2 text-slate-600">{item.category}</td>
                        <td className="whitespace-nowrap px-2.5 py-2">
                          <StatusBadge status={item.expected_status} label={item.expected_status} />
                        </td>
                        <td className="whitespace-nowrap px-2.5 py-2">
                          {result ? (
                            <StatusBadge
                              status={result.actual_status}
                              label={result.actual_status_label || result.actual_status}
                            />
                          ) : (
                            <span className="text-slate-400">未运行</span>
                          )}
                        </td>
                        <td className="whitespace-nowrap px-2.5 py-2">
                          {result ? <ResultBadge result={result} /> : <span className="text-slate-400">—</span>}
                        </td>
                        <td className="whitespace-nowrap px-2.5 py-2">
                          <div className="flex items-center gap-1.5">
                            <button
                              type="button"
                              className="btn-ghost !px-2 !py-1 !text-[11px]"
                              onClick={() => void runOne(item.id)}
                              disabled={runningId !== null}
                            >
                              {runningId === item.id ? <Spinner className="!h-3 !w-3" /> : <Play className="h-3 w-3" />}
                              运行
                            </button>
                            <button
                              type="button"
                              className="btn-ghost !px-2 !py-1 !text-[11px]"
                              onClick={() => setExpanded(isOpen ? null : item.id)}
                            >
                              <ChevronDown className={`h-3 w-3 transition ${isOpen ? 'rotate-180' : ''}`} />
                              详情
                            </button>
                          </div>
                        </td>
                      </tr>
                      {isOpen ? (
                        <tr className="bg-slate-50/60">
                          <td colSpan={6} className="px-3 py-3">
                            <div className="grid gap-3 lg:grid-cols-2">
                              <div>
                                <p className="label">原始需求 / 待检查配置</p>
                                <p className="mt-1 whitespace-pre-wrap rounded bg-white px-2.5 py-2 text-[11px] leading-relaxed text-slate-700">
                                  {item.requirement}
                                </p>
                                {item.config_payload ? (
                                  <pre className="mono-block mt-2 max-h-40 overflow-auto rounded bg-navy-900 px-2.5 py-2 text-slate-100">
                                    {JSON.stringify(item.config_payload, null, 2)}
                                  </pre>
                                ) : null}
                              </div>
                              <div className="space-y-1.5 text-[11px] leading-relaxed text-slate-600">
                                <p>
                                  <span className="font-medium text-slate-800">测试目标：</span>
                                  {item.target}
                                </p>
                                <p>
                                  <span className="font-medium text-slate-800">预期结果：</span>
                                  {item.expected_status}
                                  {item.expected_codes.length > 0 ? ` · ${item.expected_codes.join(', ')}` : ''}
                                </p>
                                <p>
                                  <span className="font-medium text-slate-800">实际结果：</span>
                                  {result
                                    ? `${result.actual_status}${result.codes.length ? ` · ${result.codes.join(', ')}` : ''}`
                                    : '尚未运行'}
                                </p>
                                {result ? (
                                  <>
                                    <p>
                                      <span className="font-medium text-slate-800">执行说明：</span>
                                      {result.detail}
                                    </p>
                                    <p>
                                      <span className="font-medium text-slate-800">过程指标：</span>
                                      生成 {result.attempts} 次 · 耗时 {result.duration_ms} ms ·
                                      结构有效 {result.structure_valid === null ? '未生成' : result.structure_valid ? '是' : '否'} ·
                                      符合需求 {result.compliant === null ? '无法判断' : result.compliant ? '是' : '否'}
                                    </p>
                                  </>
                                ) : null}
                                <p>
                                  <span className="font-medium text-slate-800">人工标注真值：</span>
                                  存在风险 {item.ground_truth_has_risk ? '是' : '否'} · 符合需求{' '}
                                  {item.ground_truth_compliant ? '是' : '否'}
                                </p>
                                <p className="text-slate-500">{item.notes}</p>
                              </div>
                            </div>
                          </td>
                        </tr>
                      ) : null}
                    </Fragment>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card>
        <SectionHeader
          title="三组实验对比"
          desc="A 基础生成 / B 生成+独立校验 / C Agent 闭环。指标全部由本机真实执行结果计算。"
          action={
            <div className="flex flex-wrap items-center gap-2">
              <button type="button" className="btn-accent !py-1.5 !text-xs" onClick={runExperiment} disabled={metricBusy}>
                {metricBusy ? <Spinner className="!h-3.5 !w-3.5" /> : <BarChart3 className="h-3.5 w-3.5" />}
                运行三组对比实验
              </button>
              <button type="button" className="btn-ghost !py-1.5 !text-xs" onClick={resetMetrics} disabled={metricBusy}>
                <RefreshCw className="h-3.5 w-3.5" />
                清除统计
              </button>
            </div>
          }
        />

        {!metrics || metrics.status === 'NOT_RUN' ? (
          <EmptyState
            icon={<HelpCircle className="h-5 w-5" />}
            title="尚未运行实验，暂时没有统计指标"
            desc="点击「运行三组对比实验」，系统会依次执行 12 条用例 × 3 种流水线，并基于真实结果计算指标。演示模式下 Token 与 API 成本显示为“未统计”。"
          />
        ) : (
          <>
            <div className="mb-3 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
              <span className="chip border border-slate-200 bg-slate-50 text-slate-600">
                {metrics.mode === 'demo' ? '演示模式实验数据' : 'API 模式实验数据'}
              </span>
              <span>样本数：{metrics.case_count} 条用例</span>
              <span>·</span>
              <span>生成时间：{formatDateTime(metrics.generated_at)}</span>
            </div>
            <div className="grid gap-3 xl:grid-cols-3">
              {metrics.groups.map((groupItem) => (
                <div key={groupItem.group} className="rounded-lg border border-slate-200 bg-white p-3">
                  <p className="text-sm font-semibold text-navy-900">{groupItem.label}</p>
                  <p className="mt-0.5 text-[11px] leading-relaxed text-slate-500">{groupItem.description}</p>
                  <dl className="mt-2.5 divide-y divide-slate-100">
                    {groupItem.metrics.map((metric) => (
                      <div key={metric.key} className="py-1.5" title={metric.note}>
                        <div className="flex items-baseline justify-between gap-2">
                          <dt className="text-[11px] text-slate-600">{metric.label}</dt>
                          <dd
                            className={`text-xs font-semibold ${
                              metric.value === null ? 'text-slate-400' : 'text-navy-900'
                            }`}
                          >
                            {metric.display}
                          </dd>
                        </div>
                        {metric.denominator ? (
                          <p className="mt-0.5 text-[10px] text-slate-400">
                            {metric.numerator ?? 0} / {metric.denominator}
                          </p>
                        ) : null}
                      </div>
                    ))}
                  </dl>
                </div>
              ))}
            </div>
          </>
        )}

        {metrics?.notices?.length ? (
          <ul className="mt-3 space-y-1 rounded-lg border border-amber-200 bg-amber-50/60 px-3 py-2 text-[11px] leading-relaxed text-amber-900">
            {metrics.notices.map((notice, index) => (
              <li key={index}>· {notice}</li>
            ))}
          </ul>
        ) : null}
      </Card>

      <Card>
        <SectionHeader title="实验设计说明" />
        <div className="grid gap-3 text-xs leading-relaxed text-slate-600 md:grid-cols-3">
          <div className="rounded-lg bg-slate-50 p-3">
            <p className="flex items-center gap-1.5 font-medium text-slate-800">
              <FlaskConical className="h-3.5 w-3.5" /> A 组：基础生成
            </p>
            <p className="mt-1">
              只调用生成模块，直接评价原始输出。用于观察“没有独立校验”时越权与危险配置会被直接当作结果的问题。
            </p>
          </div>
          <div className="rounded-lg bg-slate-50 p-3">
            <p className="flex items-center gap-1.5 font-medium text-slate-800">
              <FlaskConical className="h-3.5 w-3.5" /> B 组：生成 + 独立校验
            </p>
            <p className="mt-1">
              生成后校验一次，不触发自动修正。可统计风险检测召回率、漏检率与误报率，但无法体现修正能力。
            </p>
          </div>
          <div className="rounded-lg bg-slate-50 p-3">
            <p className="flex items-center gap-1.5 font-medium text-slate-800">
              <FlaskConical className="h-3.5 w-3.5" /> C 组：Agent 闭环
            </p>
            <p className="mt-1">
              校验失败后按规则决定重试、请求补充或转人工审核。可统计反馈修正成功率与问题配置安全处置率。
            </p>
          </div>
        </div>
        <p className="mt-2 text-[11px] leading-relaxed text-slate-500">
          注意：A 组的“实际状态”只表示是否成功生成配置，不代表配置正确；B/C 组的状态来自校验建议与 Agent 决策。
          修正成功率与风险检测率是两个不同指标，前者衡量修复能力，后者衡量发现能力。
        </p>
      </Card>
    </div>
  )
}
