"""测试用例执行器。

三种流水线对应研究设计中的三组实验：
  A 组（basic）   ：只生成，不校验、不修正 —— 用于对照；
  B 组（validate）：生成后由 Python 校验，但不触发 Agent 修正；
  C 组（agent）   ：Agent 闭环（校验 → 决策 → 有限次修正 / 补充信息 / 人工审核）。

所有结果都来自本机真实执行（演示模式下由确定性生成器产生），
不使用任何预先写死的“实验结果”。
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from .agent import Agent
from .generator import DemoGenerator, FixedConfigGenerator
from .intent_parser import parse_intent
from .schemas import (
    CaseRunResult,
    CheckStatus,
    Intent,
    TaskState,
    TestCaseDefinition,
)
from .states import STATUS_LABELS
from .validator import validate_config

GROUP_META: dict[str, dict[str, str]] = {
    "basic": {
        "id": "A",
        "label": "A 组 · 基础生成",
        "description": "只调用生成模块，不做独立校验与修正，直接评价原始输出。",
    },
    "validate": {
        "id": "B",
        "label": "B 组 · 生成 + 独立校验",
        "description": "生成后由 Python 校验模块检查，但不执行 Agent 自动修正。",
    },
    "agent": {
        "id": "C",
        "label": "C 组 · Agent 闭环",
        "description": "Agent 根据校验结果决定重新生成、请求补充信息或转交人工审核。",
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _evaluation(report) -> tuple[bool, bool | None]:
    """从校验报告中提取评价信息：结构是否有效、是否满足需求。"""
    if not report.config_parsed:
        return None, None
    checks = {c.key: c for c in report.checks}
    struct_ok = checks.get("A") is not None and checks["A"].status == CheckStatus.PASS.value
    fatal_value = [
        f for f in report.findings if f.dimension == "value" and f.severity in ("HIGH", "CRITICAL")
    ]
    structure_valid = bool(struct_ok and not fatal_value)
    if not structure_valid:
        # 结构或字段值不合法时，配置不可用，自然也谈不上“符合需求”
        return False, False
    intent_check = checks.get("C")
    if intent_check is None or intent_check.status == CheckStatus.UNDETERMINED.value:
        return True, None
    return True, intent_check.status == CheckStatus.PASS.value


def _detected(report) -> bool:
    return any(f.severity in ("MEDIUM", "HIGH", "CRITICAL") for f in report.findings)


def _make_generator(case: TestCaseDefinition):
    if case.config_payload is not None:
        return FixedConfigGenerator(case.config_payload, note=case.notes or "测试用例指定的待检查配置。")
    return DemoGenerator()


async def run_case(case: TestCaseDefinition, group: str, step_delay: float = 0.0) -> CaseRunResult:
    if group not in GROUP_META:
        raise ValueError(f"未知的实验分组：{group}")

    started = time.perf_counter()
    intent: Intent = parse_intent(case.requirement)
    generator = _make_generator(case)
    result = CaseRunResult(
        case_id=case.id,
        case_name=case.name,
        group=group,
        group_label=GROUP_META[group]["label"],
        expected_status=case.expected_status,
        ground_truth_has_risk=case.ground_truth_has_risk,
        ground_truth_compliant=case.ground_truth_compliant,
    )

    if group == "basic":
        generation = generator.generate(intent, attempt_index=0, params=case.params)
        result.generation_calls = 1
        result.attempts = 1
        report = validate_config(generation.raw or generation.config, intent, case.params)
        result.structure_valid, result.compliant = _evaluation(report)
        result.risk_detected = None  # A 组不执行校验，不统计检测能力
        ok = generation.config is not None or report.config_parsed
        result.actual_status = "SUCCESS" if ok else "FAILED"
        result.detail = "A 组不执行校验与修正，状态仅表示是否成功生成配置。"
        result.duration_ms = round((time.perf_counter() - started) * 1000, 2)
        _finalize(result, case)
        return result

    if group == "validate":
        generation = generator.generate(intent, attempt_index=0, params=case.params)
        result.generation_calls = 1
        result.attempts = 1
        report = validate_config(generation.raw or generation.config, intent, case.params)
        result.structure_valid, result.compliant = _evaluation(report)
        result.risk_detected = _detected(report)
        result.actual_status = report.status_suggestion
        result.detail = "B 组执行一次校验后直接采用校验建议，不进行自动修正。"
        result.duration_ms = round((time.perf_counter() - started) * 1000, 2)
        _finalize(result, case)
        return result

    # C 组：完整 Agent 闭环
    task = TaskState(
        id=f"case-{case.id}-{_now()}",
        requirement=case.requirement,
        params=case.params,
        origin="test-case",
        test_case_id=case.id,
    )
    agent = Agent(step_delay=step_delay, generator=generator)
    task = await agent.run(task)

    first_validation = task.attempts[0].validation if task.attempts else None
    report = task.final_validation
    result.actual_status = task.status
    result.actual_status_label = STATUS_LABELS.get(task.status, task.status)
    result.codes = sorted(
        {c for a in task.attempts if a.validation for c in a.validation.codes()}
        | {code for d in task.decisions for code in d.error_codes}
    )
    result.attempts = len(task.attempts)
    result.generation_calls = len(task.attempts)
    result.duration_ms = round(task.duration_ms or (time.perf_counter() - started) * 1000, 2)
    result.task_id = task.id
    if report is not None:
        result.structure_valid, result.compliant = _evaluation(report)
        final_passed = report.passed
        result.detail = (
            f"最终状态 {task.status_label}；共生成 {len(task.attempts)} 次，"
            f"重试 {task.retry_count}/{task.params.max_retries} 次。"
        )
    else:
        result.structure_valid = None
        result.compliant = None
        final_passed = False
        result.detail = f"最终状态 {task.status_label}；未生成可校验的配置（需求信息不足）。"
    if first_validation is not None:
        result.risk_detected = _detected(first_validation)
    else:
        result.risk_detected = None

    result.matched_expected = task.status == case.expected_status
    result.missing_codes = [c for c in case.expected_codes if c not in result.codes]
    result.unexpected_codes = [c for c in result.codes if c not in case.expected_codes]
    result.matched_expected = (
        result.matched_expected and not result.missing_codes
    )
    result.detail += " 首次校验" + ("未通过" if first_validation and not first_validation.passed else "通过")
    if first_validation is not None and not first_validation.passed:
        result.detail += "，进入修正/审核流程"
    result.detail += "。"
    _ = final_passed
    return result


def _finalize(result: CaseRunResult, case: TestCaseDefinition) -> None:
    result.codes = sorted(set(result.codes))
    result.matched_expected = result.actual_status == case.expected_status
    result.missing_codes = [c for c in case.expected_codes if c not in result.codes]
    result.unexpected_codes = [c for c in result.codes if c not in case.expected_codes]
    result.actual_status_label = STATUS_LABELS.get(result.actual_status, result.actual_status)
    if not result.matched_expected:
        result.detail += f" 预期 {case.expected_status}，实际 {result.actual_status}。"


async def run_cases(cases: list[TestCaseDefinition], group: str, step_delay: float = 0.0) -> list[CaseRunResult]:
    results: list[CaseRunResult] = []
    for case in cases:
        results.append(await run_case(case, group, step_delay=step_delay))
    return results
