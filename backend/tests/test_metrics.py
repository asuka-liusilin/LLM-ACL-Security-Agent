"""指标统计测试：空数据、零分母、检测与修正的区分。"""

from __future__ import annotations

import asyncio

from app.metrics import RunStore, compute_metrics, run_store
from app.schemas import CaseRunResult
from app.test_runner import run_cases
from app.testcases import TEST_CASES


def test_metrics_not_run_when_no_data():
    run_store.clear()
    metrics = compute_metrics()
    assert metrics.status == "NOT_RUN"
    assert metrics.groups == []
    assert any("尚未运行" in n for n in metrics.notices)


def test_zero_denominator_does_not_crash():
    store = RunStore()
    store.record(
        [
            CaseRunResult(
                case_id="X-1",
                case_name="无风险样本",
                group="agent",
                group_label="C",
                actual_status="SUCCESS",
                expected_status="SUCCESS",
                structure_valid=True,
                compliant=True,
                risk_detected=None,
                ground_truth_has_risk=False,
                attempts=1,
                duration_ms=1.0,
                generation_calls=1,
            )
        ],
        mode="demo",
    )
    # 直接调用内部计算函数，确保分母为零时不会抛异常
    from app.metrics import _group_metrics

    group = _group_metrics("agent", store.for_group("agent"), "demo")
    by_key = {m.key: m for m in group.metrics}
    assert by_key["risk_recall"].value is None
    assert "暂无" in by_key["risk_recall"].display
    assert by_key["correction_success_rate"].value is None
    assert by_key["false_positive_rate"].value is None


def test_metrics_separate_detection_from_correction():
    run_store.clear()
    all_results = []
    for group in ("basic", "validate", "agent"):
        all_results.extend(asyncio.run(run_cases(list(TEST_CASES), group, step_delay=0)))
    run_store.record(all_results, mode="demo")

    metrics = compute_metrics()
    assert metrics.status == "COMPLETED"
    groups = {g.group: {m.key: m for m in g.metrics} for g in metrics.groups}

    # 检测能力：B/C 组有统计，A 组明确标注未统计
    assert groups["basic"]["risk_recall"].value is None
    assert "未统计" in groups["basic"]["risk_recall"].display
    assert groups["validate"]["risk_recall"].denominator is not None
    assert groups["agent"]["risk_recall"].denominator is not None

    # 修正成功率只在 C 组统计，且分子不可能超过分母
    assert groups["validate"]["correction_success_rate"].value is None
    corr = groups["agent"]["correction_success_rate"]
    assert corr.denominator is not None
    assert (corr.numerator or 0) <= corr.denominator

    # Token / 成本在演示模式下必须是“未统计”，不能编造数字
    for g in metrics.groups:
        by_key = {m.key: m for m in g.metrics}
        assert by_key["tokens"].value is None
        assert "未统计" in by_key["tokens"].display
        assert by_key["cost"].value is None

    assert any("演示模式" in n for n in metrics.notices)


def test_metrics_are_recomputed_from_actual_runs():
    run_store.clear()
    results = asyncio.run(run_cases([TEST_CASES[0]], "agent", step_delay=0))
    run_store.record(results, mode="demo")
    metrics = compute_metrics()
    assert metrics.case_count == 1
    # 只运行了 C 组：未运行的分组不应返回空指标卡
    assert [g.group for g in metrics.groups] == ["agent"]
    group = metrics.groups[0]
    by_key = {m.key: m for m in group.metrics}
    assert by_key["structure_valid_rate"].numerator == 1
    assert by_key["structure_valid_rate"].denominator == 1
