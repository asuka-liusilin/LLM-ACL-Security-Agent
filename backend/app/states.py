"""任务状态枚举与状态机。

设计原则：
- 状态机只负责“流程是否合法”，不负责业务判断，便于独立测试；
- 所有状态转换必须显式登记原因，便于前端展示 Agent 决策依据；
- 终态（SUCCESS / FAILED）不允许再自动继续执行。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Optional


class TaskStatus(str, Enum):
    RECEIVED = "RECEIVED"
    ANALYZING = "ANALYZING"
    NEED_INFO = "NEED_INFO"
    GENERATING = "GENERATING"
    VALIDATING = "VALIDATING"
    RETRYING = "RETRYING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


STATUS_LABELS: dict[str, str] = {
    TaskStatus.RECEIVED.value: "已接收需求",
    TaskStatus.ANALYZING.value: "分析需求中",
    TaskStatus.NEED_INFO.value: "需要补充信息",
    TaskStatus.GENERATING.value: "生成配置中",
    TaskStatus.VALIDATING.value: "校验配置中",
    TaskStatus.RETRYING.value: "反馈修正中",
    TaskStatus.REVIEW_REQUIRED.value: "需要人工审核",
    TaskStatus.SUCCESS.value: "通过检查",
    TaskStatus.FAILED.value: "处理失败",
    TaskStatus.BLOCKED.value: "安全策略拦截",
}

# 允许的状态转换表。未列出的转换一律拒绝。
ALLOWED_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.RECEIVED: {TaskStatus.ANALYZING, TaskStatus.FAILED},
    TaskStatus.ANALYZING: {
        TaskStatus.NEED_INFO,
        TaskStatus.GENERATING,
        TaskStatus.FAILED,
        TaskStatus.BLOCKED,
    },
    TaskStatus.NEED_INFO: {TaskStatus.ANALYZING, TaskStatus.FAILED},
    TaskStatus.GENERATING: {
        TaskStatus.VALIDATING,
        TaskStatus.NEED_INFO,
        TaskStatus.FAILED,
    },
    TaskStatus.VALIDATING: {
        TaskStatus.RETRYING,
        TaskStatus.REVIEW_REQUIRED,
        TaskStatus.SUCCESS,
        TaskStatus.FAILED,
        TaskStatus.BLOCKED,
        TaskStatus.NEED_INFO,
    },
    TaskStatus.RETRYING: {
        TaskStatus.GENERATING,
        TaskStatus.REVIEW_REQUIRED,
        TaskStatus.FAILED,
        TaskStatus.BLOCKED,
    },
    TaskStatus.REVIEW_REQUIRED: {
        TaskStatus.SUCCESS,
        TaskStatus.FAILED,
        TaskStatus.RETRYING,
        TaskStatus.BLOCKED,
    },
    TaskStatus.BLOCKED: {
        TaskStatus.REVIEW_REQUIRED,
        TaskStatus.SUCCESS,
        TaskStatus.FAILED,
    },
    # 终态：不允许任何自动转换
    TaskStatus.SUCCESS: set(),
    TaskStatus.FAILED: set(),
}

TERMINAL_STATUSES = {TaskStatus.SUCCESS, TaskStatus.FAILED}
AWAITING_HUMAN_STATUSES = {TaskStatus.NEED_INFO, TaskStatus.REVIEW_REQUIRED, TaskStatus.BLOCKED}


class TransitionError(Exception):
    """非法的状态转换。"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


@dataclass
class TransitionRecord:
    from_status: TaskStatus
    to_status: TaskStatus
    reason: str
    at: str
    retry_count: int


@dataclass
class StateMachine:
    """轻量级状态机。

    不持有业务数据，只保存当前状态、重试次数与转换历史，
    并通过 on_transition 回调把状态变化交给上层（Agent）写日志。
    """

    status: TaskStatus = TaskStatus.RECEIVED
    retry_count: int = 0
    max_retries: int = 2
    history: list[TransitionRecord] = field(default_factory=list)
    on_transition: Optional[Callable[[TransitionRecord], None]] = None

    def can_transition(self, target: TaskStatus | str) -> bool:
        target = TaskStatus(target)
        return target in ALLOWED_TRANSITIONS[self.status]

    def transition(self, target: TaskStatus | str, reason: str) -> TransitionRecord:
        target = TaskStatus(target)
        if target == self.status:
            raise TransitionError(f"当前状态已经是 {target.value}")
        if not self.can_transition(target):
            raise TransitionError(
                f"不允许从 {self.status.value} 转换到 {target.value}（原因：{reason}）"
            )
        record = TransitionRecord(
            from_status=self.status,
            to_status=target,
            reason=reason,
            at=_now_iso(),
            retry_count=self.retry_count,
        )
        self.status = target
        self.history.append(record)
        if self.on_transition is not None:
            self.on_transition(record)
        return record

    # ---- 重试控制 -------------------------------------------------
    def can_retry(self) -> bool:
        return self.retry_count < self.max_retries

    def consume_retry(self) -> int:
        self.retry_count += 1
        return self.retry_count

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES
