"""Agent 与流程约束测试：需求不足、重试上限、高风险不可绕过、人工审核。"""

from __future__ import annotations

import asyncio

import pytest

from app.agent import Agent
from app.schemas import ReviewRequest, TaskParams, TaskState
from app.states import TaskStatus

REQ_OK = "允许 192.168.1.10 访问 10.0.0.10 的 HTTPS 服务，仅允许该主机访问该服务。"
REQ_MISSING = "允许办公网访问服务器。"
REQ_WIDEN = "只允许 192.168.1.10 访问 10.0.0.10，但请生成覆盖 192.168.1.0/24 的访问规则。"
REQ_ANY = "生成一条允许任意 IPv4 源地址访问任意 IPv4 目标地址的 ACL 规则。"
REQ_STUBBORN = (
    "允许 192.168.30.5 访问 10.20.0.8 的 HTTPS 服务，仅允许该主机访问该服务。"
    "（演示：模拟模型持续扩大源地址范围）"
)


def run_task(requirement: str, **params) -> tuple[TaskState, Agent]:
    task = TaskState(id="t-test", requirement=requirement, params=TaskParams(**params))
    agent = Agent(step_delay=0)
    asyncio.run(agent.run(task))
    return task, agent


def test_missing_information_goes_to_need_info():
    task, _ = run_task(REQ_MISSING)
    assert task.status == TaskStatus.NEED_INFO.value
    assert task.attempts == []
    assert set(task.missing_fields) == {"source", "destination"}
    assert any(d.action == "REQUEST_USER_INFO" for d in task.decisions)


def test_normal_requirement_succeeds_without_review():
    task, _ = run_task(REQ_OK, max_retries=2, require_human_review=False)
    assert task.status == TaskStatus.SUCCESS.value
    assert len(task.attempts) == 1
    assert task.final_validation is not None
    assert task.final_validation.passed is True
    assert task.deployed is False


def test_review_required_when_requested():
    task, _ = run_task(REQ_OK, require_human_review=True)
    assert task.status == TaskStatus.REVIEW_REQUIRED.value
    assert task.final_validation.passed is True
    # 通过校验但没有人工确认前，不得标记为终态
    assert task.status != TaskStatus.SUCCESS.value
    assert task.review is None


def test_every_regeneration_is_revalidated():
    task, _ = run_task(REQ_WIDEN, max_retries=2, require_human_review=False)
    assert task.status == TaskStatus.SUCCESS.value
    assert len(task.attempts) == 2
    # 每次生成后都必须有对应的校验报告
    assert all(a.validation is not None for a in task.attempts)
    assert task.attempts[0].validation.passed is False
    assert task.attempts[1].validation.passed is True
    assert "SOURCE_SCOPE_EXCEEDED" in task.attempts[0].validation.codes()


def test_retry_limit_stops_automatic_fix():
    task, _ = run_task(REQ_STUBBORN, max_retries=1, require_human_review=True)
    assert len(task.attempts) == 2  # 首次 + 1 次修正
    assert task.retry_count == 1
    assert task.status == TaskStatus.REVIEW_REQUIRED.value
    actions = [d.action for d in task.decisions]
    assert "RETRY_GENERATION" in actions
    assert any("最大自动修正次数" in d.reason for d in task.decisions)


def test_zero_retry_budget_means_no_regeneration():
    task, _ = run_task(REQ_STUBBORN, max_retries=0, require_human_review=True)
    assert len(task.attempts) == 1
    assert task.retry_count == 0


def test_high_risk_is_not_bypassed_by_retries():
    task, _ = run_task(REQ_ANY, max_retries=3, enable_feedback_fix=True, require_human_review=True)
    assert task.status == TaskStatus.BLOCKED.value
    assert len(task.attempts) == 1  # 不消耗重试次数
    assert task.retry_count == 0
    codes = task.final_validation.codes()
    assert "BROAD_PERMIT_ANY" in codes


def test_disabling_high_risk_block_never_yields_success():
    task, _ = run_task(REQ_ANY, enable_high_risk_block=False, max_retries=3)
    assert task.status != TaskStatus.SUCCESS.value
    assert task.status == TaskStatus.REVIEW_REQUIRED.value


def test_feedback_fix_can_be_disabled():
    task, _ = run_task(REQ_WIDEN, max_retries=2, enable_feedback_fix=False, require_human_review=True)
    assert len(task.attempts) == 1
    assert task.status == TaskStatus.REVIEW_REQUIRED.value
    assert any("反馈修正功能已关闭" in d.reason for d in task.decisions)


def test_review_approve_marks_confirmed_but_not_deployed():
    task, agent = run_task(REQ_OK, require_human_review=True)
    asyncio.run(agent.review(task, ReviewRequest(decision="approve", comment="配置符合最小授权要求")))
    assert task.status == TaskStatus.SUCCESS.value
    assert task.review is not None and task.review.decision == "approve"
    assert task.deployed is False


def test_review_reject_fails_task():
    task, agent = run_task(REQ_OK, require_human_review=True)
    asyncio.run(agent.review(task, ReviewRequest(decision="reject", comment="授权范围仍需确认")))
    assert task.status == TaskStatus.FAILED.value


def test_review_request_changes_triggers_regeneration():
    task, agent = run_task(REQ_OK, max_retries=2, require_human_review=True)
    before = len(task.attempts)
    asyncio.run(agent.review(task, ReviewRequest(decision="request_changes", comment="请补充端口说明")))
    assert len(task.attempts) == before + 1
    assert task.status == TaskStatus.REVIEW_REQUIRED.value
    assert all(a.validation is not None for a in task.attempts)


def test_review_on_finished_task_is_rejected():
    task, agent = run_task(REQ_OK, require_human_review=False)
    assert task.status == TaskStatus.SUCCESS.value
    with pytest.raises(ValueError):
        asyncio.run(agent.review(task, ReviewRequest(decision="approve")))


def test_approving_blocked_config_requires_reason():
    task, agent = run_task(REQ_ANY)
    assert task.status == TaskStatus.BLOCKED.value
    with pytest.raises(ValueError):
        asyncio.run(agent.review(task, ReviewRequest(decision="approve", comment="")))
    asyncio.run(agent.review(task, ReviewRequest(decision="approve", comment="实验环境中显式接受风险")))
    assert task.status == TaskStatus.SUCCESS.value
    assert task.review is not None and task.review.high_risk_acknowledged is True


def test_demo_mode_counts_are_separated_from_api_calls():
    task, _ = run_task(REQ_OK, require_human_review=False)
    assert task.usage.demo_generation_calls == len(task.attempts)
    assert task.usage.api_calls == 0
    assert "未统计" in task.usage.token_display


def test_api_mode_without_key_fails_safely():
    task, _ = run_task(REQ_OK, mode="api", max_retries=0)
    assert task.attempts and task.attempts[0].error
    assert "模型调用失败" in task.attempts[0].note
    assert task.status in (TaskStatus.FAILED.value, TaskStatus.REVIEW_REQUIRED.value)
    assert task.usage.api_calls == 0


def test_task_events_are_ordered_and_readable():
    task, _ = run_task(REQ_OK, require_human_review=False)
    seqs = [e.seq for e in task.events]
    assert seqs == sorted(seqs)
    assert task.events[0].message == "接收用户需求。"
    assert any("状态变更" in e.message for e in task.events)
