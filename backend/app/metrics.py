"""指标统计。

原则：
- 所有数字都来自本机真实执行过的测试结果，没有预先写死的实验数据；
- 分母为零、指标未采集、演示模式下不适用时，明确显示“暂无数据 / 未统计”，绝不填数字；
- 明确区分“校验模块检测到风险”和“Agent 修正成功”，二者不是同一个指标。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from .schemas import CaseRunResult, GroupMetrics, MetricValue, MetricsResponse
from .test_runner import GROUP_META


class RunStore:
    def __init__(self) -> None:
        self._latest: dict[tuple[str, str], CaseRunResult] = {}
        self._recorded_at: Optional[str] = None
        self._mode: Optional[str] = None
        self._runs_count = 0

    def record(self, results: list[CaseRunResult], mode: str = "demo") -> None:
        for item in results:
            self._latest[(item.group, item.case_id)] = item
        self._recorded_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        self._mode = mode
        self._runs_count += len(results)

    def clear(self) -> None:
        self._latest.clear()
        self._recorded_at = None
        self._mode = None
        self._runs_count = 0

    def for_group(self, group: str) -> list[CaseRunResult]:
        return [r for (g, _), r in sorted(self._latest.items()) if g == group]

    def latest_for_case(self, case_id: str) -> dict[str, CaseRunResult]:
        return {g: r for (g, cid), r in self._latest.items() if cid == case_id}

    @property
    def empty(self) -> bool:
        return not self._latest

    @property
    def recorded_at(self) -> Optional[str]:
        return self._recorded_at

    @property
    def mode(self) -> Optional[str]:
        return self._mode


run_store = RunStore()


def _pct(num: int, den: int) -> float:
    return round(num * 100 / den, 1) if den else 0.0


def _rate_metric(
    key: str,
    label: str,
    num: Optional[int],
    den: Optional[int],
    *,
    note: str = "",
    empty_display: str = "暂无数据",
    skipped: Optional[str] = None,
) -> MetricValue:
    if skipped:
        return MetricValue(key=key, label=label, display=skipped, value=None, note=note)
    if den is None or den == 0:
        return MetricValue(
            key=key,
            label=label,
            display=empty_display,
            value=None,
            numerator=num,
            denominator=den,
            note=note or "样本数为 0，未计算比例。",
        )
    value = _pct(num or 0, den)
    return MetricValue(
        key=key,
        label=label,
        display=f"{value:.1f}%",
        value=value,
        numerator=num,
        denominator=den,
        note=note,
    )


def _group_metrics(group: str, runs: list[CaseRunResult], mode: str) -> GroupMetrics:
    meta = GROUP_META[group]
    total = len(runs)

    structure_num = len([r for r in runs if r.structure_valid is True])
    structure_den = len([r for r in runs if r.structure_valid is not None])
    compliance_num = len([r for r in runs if r.compliant is True])
    compliance_den = len([r for r in runs if r.compliant is not None])

    risky = [r for r in runs if r.ground_truth_has_risk]
    risky_measured = [r for r in risky if r.risk_detected is not None]
    detected = [r for r in risky_measured if r.risk_detected]
    missed = len(risky_measured) - len(detected)

    legit = [r for r in runs if not r.ground_truth_has_risk and r.ground_truth_compliant]
    legit_measured = [r for r in legit if r.risk_detected is not None]
    flagged = [r for r in legit_measured if r.risk_detected]

    retried = [r for r in runs if r.attempts > 1]
    retried_fixed = [r for r in retried if r.actual_status == "SUCCESS" and r.compliant is not False]

    avg_time = sum(r.duration_ms for r in runs) / total if total else 0
    avg_calls = sum(r.generation_calls for r in runs) / total if total else 0
    any_tokens = any(r.tokens for r in runs)

    metrics: list[MetricValue] = [
        _rate_metric(
            "structure_valid_rate",
            "原始配置结构有效率",
            structure_num,
            structure_den,
            note="最终（或唯一一次）生成结果通过结构与字段检查的样本比例；未生成配置的样本不计入分母。",
        ),
        _rate_metric(
            "compliance_rate",
            "最终配置需求符合率",
            compliance_num,
            compliance_den,
            note="最终配置在源、目标、动作、协议、端口维度均未偏离需求的样本比例。",
        ),
    ]

    if group == "basic":
        metrics.append(
            _rate_metric(
                "risk_recall",
                "风险检测召回率",
                None,
                None,
                skipped="未统计（A 组不执行校验）",
                note="A 组没有校验环节，无法统计检测能力。",
            )
        )
        metrics.append(
            _rate_metric(
                "risk_miss_rate",
                "危险配置漏检率",
                None,
                None,
                skipped="未统计（A 组不执行校验）",
            )
        )
        metrics.append(
            _rate_metric(
                "false_positive_rate",
                "合法配置误报率",
                None,
                None,
                skipped="未统计（A 组不执行校验）",
            )
        )
        metrics.append(
            _rate_metric(
                "correction_success_rate",
                "反馈修正成功率",
                None,
                None,
                skipped="未统计（A 组不执行修正）",
            )
        )
    else:
        metrics.append(
            _rate_metric(
                "risk_recall",
                "风险检测召回率",
                len(detected),
                len(risky_measured) if risky_measured else None,
                note=f"标注为存在风险的样本 {len(risky)} 个，实际参与统计 {len(risky_measured)} 个。",
            )
        )
        metrics.append(
            _rate_metric(
                "risk_miss_rate",
                "危险配置漏检率",
                missed if risky_measured else None,
                len(risky_measured) if risky_measured else None,
                note="真实存在标注风险、但校验模块未给出中风险及以上结论的样本比例。",
            )
        )
        metrics.append(
            _rate_metric(
                "false_positive_rate",
                "合法配置误报率",
                len(flagged),
                len(legit_measured) if legit_measured else None,
                note=f"标注为合法且符合需求的样本 {len(legit)} 个。",
            )
        )
        if group == "validate":
            metrics.append(
                _rate_metric(
                    "correction_success_rate",
                    "反馈修正成功率",
                    None,
                    None,
                    skipped="未统计（B 组不执行修正）",
                )
            )
        else:
            metrics.append(
                _rate_metric(
                    "correction_success_rate",
                    "反馈修正成功率",
                    len(retried_fixed),
                    len(retried) if retried else None,
                    note=f"进入修正流程的样本 {len(retried)} 个；仅统计“修正后通过校验且满足需求”。",
                )
            )

    # 问题配置是否被“安全处置”（转入审核 / 拦截 / 失败，而不是被当成成功结果）
    problem_runs = [r for r in runs if r.compliant is False or r.ground_truth_has_risk]
    handled = [
        r
        for r in problem_runs
        if r.actual_status in ("REVIEW_REQUIRED", "BLOCKED", "FAILED")
        or (r.actual_status == "SUCCESS" and r.compliant is True)
    ]

    if group == "basic":
        escalation_metric = MetricValue(
            key="escalation_rate",
            label="问题配置安全处置率",
            display="未统计（A 组无处置环节）",
            value=None,
            note="A 组只生成配置，不存在处置环节。",
        )
    else:
        escalation_metric = _rate_metric(
            "escalation_rate",
            "问题配置安全处置率",
            len(handled),
            len(problem_runs) if problem_runs else None,
            note=(
                f"存在问题样本 {len(problem_runs)} 个：转入人工审核、安全拦截或失败，"
                "或修正后确实满足需求，才算安全处置。"
            ),
        )

    metrics.extend(
        [
            escalation_metric,
            MetricValue(
                key="avg_time",
                label="平均任务处理时间",
                display=(f"{avg_time:.2f} ms" if avg_time < 10 else f"{avg_time:.0f} ms") if total else "暂无数据",
                value=round(avg_time, 2) if total else None,
                note="本机演示模式下的进程内耗时（毫秒级），不含真实网络与模型服务延迟。",
            ),
            MetricValue(
                key="avg_calls",
                label="平均生成/模型调用次数",
                display=f"{avg_calls:.2f} 次" if total else "暂无数据",
                value=round(avg_calls, 2) if total else None,
                note="演示模式下为生成器调用次数；真实 API 调用次数单独统计。",
            ),
            MetricValue(
                key="tokens",
                label="Token 使用量",
                display="未统计（演示模式）" if mode == "demo" else ("已记录" if any_tokens else "未提供"),
                value=None,
                note="只有真实调用模型服务且服务返回 usage 时才统计。",
            ),
            MetricValue(
                key="cost",
                label="单任务 API 成本",
                display="未统计",
                value=None,
                note="原型未接入计费接口，不做金额估算。",
            ),
        ]
    )

    return GroupMetrics(
        group=group,
        label=f"{meta['label']}（{total} 个用例）",
        description=meta["description"],
        metrics=metrics,
    )


def compute_metrics() -> MetricsResponse:
    if run_store.empty:
        return MetricsResponse(
            status="NOT_RUN",
            groups=[],
            notices=[
                "尚未运行任何测试或实验，因此没有可用的统计指标。",
                "可在「测试用例与实验」页面运行全部用例或三组对比实验后查看结果。",
            ],
        )

    groups = []
    case_ids: set[str] = set()
    missing_groups: list[str] = []
    for group in ("basic", "validate", "agent"):
        runs = run_store.for_group(group)
        if not runs:
            # 没有跑过的分组不要输出一张全是“暂无数据”的卡片
            missing_groups.append(GROUP_META[group]["label"])
            continue
        case_ids.update(r.case_id for r in runs)
        groups.append(_group_metrics(group, runs, run_store.mode or "demo"))

    notices = [
        "以下指标来自本机真实执行的原型测试，样本规模较小，仅用于分析原型行为，不代表真实大模型在真实网络中的表现。",
    ]
    if missing_groups:
        notices.append("尚未运行的分组：" + "、".join(missing_groups) + "（因此不对应任何统计数字）。")
    if run_store.mode == "demo":
        notices.append(
            "当前结果为演示模式（确定性生成器）自测数据，未调用任何真实大模型，不能作为模型能力结论。"
        )
    notices.append("Token 使用量与 API 成本仅在实际调用模型服务后可统计；演示模式下显示为“未统计”。")
    notices.append(
        "注意：内置用例与校验规则由同一作者设计，演示模式下指标可能接近饱和（例如召回率 100%），"
        "这不能说明方法在真实环境中同样有效；接入真实模型后需要用独立测试集重新评估。"
    )
    notices.append(
        "真值（ground truth）描述的是该用例候选配置的客观属性（是否越权、是否命中风险），"
        "由作者手工标注，不是设备实测数据。"
    )

    return MetricsResponse(
        status="COMPLETED",
        mode=run_store.mode,
        generated_at=run_store.recorded_at,
        case_count=len(case_ids),
        groups=groups,
        notices=notices,
    )
