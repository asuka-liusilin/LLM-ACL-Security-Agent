"""Pydantic 数据模型：ACL 中间数据模型、校验结果、任务与事件。"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from .states import STATUS_LABELS, TaskStatus


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# ACL 统一中间数据模型（不等同于任何厂商设备可直接使用的语法）
# ---------------------------------------------------------------------------


class ACLRule(BaseModel):
    model_config = {"extra": "forbid"}

    action: Literal["permit", "deny"]
    protocol: Literal["tcp", "udp", "icmp", "ip"]
    source: str
    destination: str
    destination_port: Optional[int] = None
    description: Optional[str] = None


class ACLConfig(BaseModel):
    model_config = {"extra": "forbid"}

    rules: list[ACLRule]
    default_action: Literal["permit", "deny"]


# ---------------------------------------------------------------------------
# 需求理解结果
# ---------------------------------------------------------------------------


class Intent(BaseModel):
    text: str = ""
    parse_mode: str = "demo-rule"  # demo-rule | llm
    action: Optional[str] = None
    protocol: Optional[str] = None
    destination_port: Optional[int] = None
    sources: list[str] = Field(default_factory=list)
    destinations: list[str] = Field(default_factory=list)
    default_action: Optional[str] = None
    missing: list[str] = Field(default_factory=list)
    invalid_values: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    # 用户原文中显式要求“覆盖某个更大网段”之类的扩大指令（会被记录，但校验仍按授权范围判断）
    widen_source_hint: Optional[str] = None
    widen_destination_hint: Optional[str] = None
    any_any: bool = False
    stubborn_widen: bool = False
    service_label: Optional[str] = None

    @property
    def is_complete(self) -> bool:
        return not self.missing and not self.invalid_values


# ---------------------------------------------------------------------------
# 校验结果
# ---------------------------------------------------------------------------


class CheckStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    UNDETERMINED = "UNDETERMINED"


CHECK_STATUS_LABELS = {
    CheckStatus.PASS.value: "通过",
    CheckStatus.FAIL.value: "未通过",
    CheckStatus.NEEDS_REVIEW.value: "需要人工确认",
    CheckStatus.UNDETERMINED.value: "无法判断",
}

SEVERITY_LABELS = {
    "INFO": "提示",
    "LOW": "低风险",
    "MEDIUM": "中风险",
    "HIGH": "高风险",
    "CRITICAL": "严重风险",
}

SEVERITY_ORDER = {"INFO": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


class Finding(BaseModel):
    code: str
    severity: Literal["INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
    dimension: Literal["structure", "value", "intent", "risk"]
    message: str
    evidence: str = ""
    recommendation: str = ""
    # 该问题是否可以通过“重新生成配置”消除；False 表示不允许用普通重试绕过
    retryable: bool = False
    # 命中即触发安全拦截（BLOCKED），需要人工显式处理
    blocking: bool = False
    # 问题关联的规则下标（0 起），用于前端按规则展示风险状态
    rule_index: Optional[int] = None


class CheckResult(BaseModel):
    key: str
    name: str
    status: str  # CheckStatus
    status_label: str = ""
    severity: Optional[str] = None
    summary: str = ""
    findings: list[Finding] = Field(default_factory=list)

    def finalize(self) -> "CheckResult":
        self.status_label = CHECK_STATUS_LABELS.get(self.status, self.status)
        if self.findings:
            self.severity = max(
                (f.severity for f in self.findings), key=lambda s: SEVERITY_ORDER[s]
            )
        return self


class ValidationReport(BaseModel):
    passed: bool = False
    status_suggestion: str = TaskStatus.FAILED.value
    findings: list[Finding] = Field(default_factory=list)
    checks: list[CheckResult] = Field(default_factory=list)
    summary: dict[str, int] = Field(default_factory=dict)
    rules_evaluated: int = 0
    config_parsed: bool = False

    def highest_severity(self) -> Optional[str]:
        if not self.findings:
            return None
        return max((f.severity for f in self.findings), key=lambda s: SEVERITY_ORDER[s])

    def has_blocking(self) -> bool:
        return any(f.blocking for f in self.findings)

    def codes(self) -> list[str]:
        return [f.code for f in self.findings]


# ---------------------------------------------------------------------------
# 任务参数 / 生成结果
# ---------------------------------------------------------------------------


class TaskParams(BaseModel):
    mode: Literal["demo", "api"] = "demo"
    max_retries: int = Field(default=2, ge=0, le=3)
    enable_feedback_fix: bool = True
    enable_high_risk_block: bool = True
    require_human_review: bool = True


class GenerationResult(BaseModel):
    raw: str
    config: Optional[dict[str, Any]] = None
    note: str = ""
    source: Literal["demo", "llm", "fixed"] = "demo"
    model: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    latency_ms: Optional[int] = None
    error: Optional[str] = None


class Attempt(BaseModel):
    index: int
    kind: Literal["initial", "correction"] = "initial"
    note: str = ""
    raw: str = ""
    config: Optional[dict[str, Any]] = None
    validation: Optional[ValidationReport] = None
    created_at: str = Field(default_factory=now_iso)
    generation_source: str = "demo"
    error: Optional[str] = None


class TaskEvent(BaseModel):
    seq: int
    at: str = Field(default_factory=now_iso)
    level: Literal["info", "success", "warning", "error"] = "info"
    status: Optional[str] = None
    message: str
    detail: Optional[str] = None


class Decision(BaseModel):
    step: int
    status: str
    error_codes: list[str] = Field(default_factory=list)
    action: str
    reason: str
    requires_human_review: bool = False
    retry_count: int = 0
    attempt: int = 0


class ReviewRecord(BaseModel):
    decision: Literal["approve", "reject", "request_changes", "escalate"]
    comment: str = ""
    reviewer: str = "人工审核员"
    at: str = Field(default_factory=now_iso)
    high_risk_acknowledged: bool = False


class UsageStats(BaseModel):
    """模型调用统计。演示模式与真实 API 调用严格分开。"""

    demo_generation_calls: int = 0
    api_calls: int = 0
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None

    @property
    def token_display(self) -> str:
        if self.api_calls == 0:
            return "未统计（演示模式）"
        if self.prompt_tokens is None:
            return "未提供"
        return str(self.prompt_tokens + (self.completion_tokens or 0))


# ---------------------------------------------------------------------------
# 任务
# ---------------------------------------------------------------------------


class TaskState(BaseModel):
    id: str
    requirement: str
    params: TaskParams = Field(default_factory=TaskParams)
    status: str = TaskStatus.RECEIVED.value
    status_label: str = STATUS_LABELS[TaskStatus.RECEIVED.value]
    created_at: str = Field(default_factory=now_iso)
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration_ms: Optional[int] = None
    intent: Optional[Intent] = None
    attempts: list[Attempt] = Field(default_factory=list)
    events: list[TaskEvent] = Field(default_factory=list)
    decisions: list[Decision] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    review: Optional[ReviewRecord] = None
    usage: UsageStats = Field(default_factory=UsageStats)
    retry_count: int = 0
    origin: Literal["manual", "test-case"] = "manual"
    test_case_id: Optional[str] = None
    # 明确标记：本原型不下发配置
    deployed: bool = False

    @field_validator("status")
    @classmethod
    def _known_status(cls, v: str) -> str:
        TaskStatus(v)
        return v

    # ---- 便捷访问 ----
    @property
    def latest_attempt(self) -> Optional[Attempt]:
        return self.attempts[-1] if self.attempts else None

    @property
    def final_validation(self) -> Optional[ValidationReport]:
        attempt = self.latest_attempt
        return attempt.validation if attempt else None

    @property
    def final_config(self) -> Optional[dict[str, Any]]:
        attempt = self.latest_attempt
        return attempt.config if attempt else None

    def event(self, message: str, level: str = "info", detail: Optional[str] = None,
              status: Optional[str] = None) -> TaskEvent:
        evt = TaskEvent(
            seq=len(self.events) + 1,
            level=level,  # type: ignore[arg-type]
            status=status or self.status,
            message=message,
            detail=detail,
        )
        self.events.append(evt)
        return evt

    def set_status(self, status: TaskStatus | str, reason: str = "") -> None:
        status = TaskStatus(status)
        self.status = status.value
        self.status_label = STATUS_LABELS[status.value]
        if reason:
            self.event(reason, level="info", status=status.value)

    def decision(self, action: str, reason: str, error_codes: list[str] | None = None,
                 requires_human_review: bool = False, attempt: int | None = None) -> Decision:
        d = Decision(
            step=len(self.decisions) + 1,
            status=self.status,
            error_codes=error_codes or [],
            action=action,
            reason=reason,
            requires_human_review=requires_human_review,
            retry_count=self.retry_count,
            attempt=len(self.attempts) if attempt is None else attempt,
        )
        self.decisions.append(d)
        return d


# ---------------------------------------------------------------------------
# API 请求 / 响应
# ---------------------------------------------------------------------------


class TaskCreateRequest(BaseModel):
    requirement: str = Field(min_length=1)
    params: TaskParams = Field(default_factory=TaskParams)

    @field_validator("requirement")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("需求描述不能为空")
        return v.strip()


class TaskSummary(BaseModel):
    id: str
    requirement: str
    status: str
    status_label: str
    created_at: str
    duration_ms: Optional[int] = None
    mode: str = "demo"
    attempt_count: int = 0
    risk_codes: list[str] = Field(default_factory=list)


class FeedbackRequest(BaseModel):
    message: str = Field(min_length=1)

    @field_validator("message")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("补充信息不能为空")
        return v.strip()


class ReviewRequest(BaseModel):
    decision: Literal["approve", "reject", "request_changes"]
    comment: str = ""
    reviewer: str = "人工审核员"


class TestCaseDefinition(BaseModel):
    id: str
    name: str
    category: str
    requirement: str
    target: str = ""
    config_payload: Optional[dict[str, Any]] = None
    params: TaskParams = Field(default_factory=lambda: TaskParams(max_retries=0, require_human_review=False))
    expected_status: str
    expected_codes: list[str] = Field(default_factory=list)
    ground_truth_has_risk: bool = False
    ground_truth_compliant: bool = True
    notes: str = ""


class CaseRunResult(BaseModel):
    case_id: str
    case_name: str
    group: str
    group_label: str
    actual_status: str = ""
    actual_status_label: str = ""
    expected_status: str = ""
    codes: list[str] = Field(default_factory=list)
    missing_codes: list[str] = Field(default_factory=list)
    unexpected_codes: list[str] = Field(default_factory=list)
    matched_expected: bool = False
    structure_valid: Optional[bool] = None
    compliant: Optional[bool] = None
    risk_detected: Optional[bool] = None
    ground_truth_has_risk: bool = False
    ground_truth_compliant: bool = True
    attempts: int = 0
    duration_ms: float = 0.0
    generation_calls: int = 0
    tokens: Optional[int] = None
    detail: str = ""
    task_id: Optional[str] = None


class TestRunRequest(BaseModel):
    case_ids: Optional[list[str]] = None
    group: Literal["basic", "validate", "agent"] = "agent"


class TestRunResponse(BaseModel):
    group: str
    group_label: str
    mode: str
    started_at: str
    finished_at: str
    results: list[CaseRunResult]
    passed: int
    total: int
    notice: str


class MetricValue(BaseModel):
    key: str
    label: str
    display: str
    value: Optional[float] = None
    numerator: Optional[int] = None
    denominator: Optional[int] = None
    note: str = ""


class GroupMetrics(BaseModel):
    group: str
    label: str
    description: str
    metrics: list[MetricValue]


class MetricsResponse(BaseModel):
    status: Literal["NOT_RUN", "COMPLETED"]
    mode: Optional[str] = None
    generated_at: Optional[str] = None
    case_count: int = 0
    groups: list[GroupMetrics] = Field(default_factory=list)
    notices: list[str] = Field(default_factory=list)


class ReviewResponse(BaseModel):
    task_id: str
    status: str
    status_label: str
    message: str


class HealthResponse(BaseModel):
    status: str
    mode: str
    api_mode_available: bool
    model: Optional[str] = None
    version: str = "0.1.0"
    notices: list[str] = Field(default_factory=list)
