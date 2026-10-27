"""状态机单元测试：允许/拒绝的状态转换、重试上限、终态保护。"""

from __future__ import annotations

import pytest

from app.states import StateMachine, TaskStatus, TransitionError


def test_allowed_transition_path():
    sm = StateMachine()
    sm.transition(TaskStatus.ANALYZING, "分析需求")
    sm.transition(TaskStatus.GENERATING, "生成配置")
    sm.transition(TaskStatus.VALIDATING, "校验配置")
    sm.transition(TaskStatus.SUCCESS, "通过检查")
    assert sm.status == TaskStatus.SUCCESS
    assert len(sm.history) == 4
    assert sm.is_terminal is True


def test_illegal_transition_is_rejected():
    sm = StateMachine()
    with pytest.raises(TransitionError):
        sm.transition(TaskStatus.SUCCESS, "跳过中间步骤直接成功")


def test_cannot_jump_from_terminal_state():
    sm = StateMachine(status=TaskStatus.SUCCESS)
    with pytest.raises(TransitionError):
        sm.transition(TaskStatus.GENERATING, "完成后又继续执行")


def test_need_info_returns_to_analyzing():
    sm = StateMachine()
    sm.transition(TaskStatus.ANALYZING, "分析")
    sm.transition(TaskStatus.NEED_INFO, "缺信息")
    sm.transition(TaskStatus.ANALYZING, "收到补充信息")
    assert sm.status == TaskStatus.ANALYZING


def test_retry_counter_respects_limit():
    sm = StateMachine(max_retries=2)
    assert sm.can_retry() is True
    assert sm.consume_retry() == 1
    assert sm.consume_retry() == 2
    assert sm.can_retry() is False


def test_transition_records_reason_and_retry_count():
    sm = StateMachine(max_retries=2)
    sm.transition(TaskStatus.ANALYZING, "开始分析")
    sm.consume_retry()
    record = sm.transition(TaskStatus.GENERATING, "重试生成")
    assert record.reason == "重试生成"
    assert record.retry_count == 1
    assert record.at  # 时间戳存在


def test_on_transition_callback_receives_record():
    captured = []
    sm = StateMachine(on_transition=captured.append)
    sm.transition(TaskStatus.ANALYZING, "分析")
    assert len(captured) == 1
    assert captured[0].to_status == TaskStatus.ANALYZING


def test_validation_can_go_to_retrying_and_back():
    sm = StateMachine()
    sm.transition(TaskStatus.ANALYZING, "分析")
    sm.transition(TaskStatus.GENERATING, "生成")
    sm.transition(TaskStatus.VALIDATING, "校验")
    sm.transition(TaskStatus.RETRYING, "发现问题")
    sm.transition(TaskStatus.GENERATING, "重新生成")
    assert sm.status == TaskStatus.GENERATING


def test_review_required_can_be_approved_or_rejected():
    sm = StateMachine(status=TaskStatus.REVIEW_REQUIRED)
    assert sm.can_transition(TaskStatus.SUCCESS) is True
    assert sm.can_transition(TaskStatus.FAILED) is True
    assert sm.can_transition(TaskStatus.GENERATING) is False
