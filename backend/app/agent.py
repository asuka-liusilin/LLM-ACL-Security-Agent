"""轻量级 Agent：任务规划、工具调用与受约束的流程决策。

它不是“把函数改名为 Agent”：
- 每一步都读取任务状态与工具（生成器 / 校验器）的返回结果；
- 用明确规则提出下一步行动，再由 Python 状态机校验该行动是否合法；
- 重试次数、危险配置、人工审核等边界由状态机与校验结果共同约束；
- 所有行动都记录原因（Decision），供前端展示；
- 决策不使用、也不展示任何模型的隐藏推理过程。

在 API 模式下，模型只负责“生成配置”这一工具调用，决策仍由确定性规则给出，
避免模型自行宣布危险配置“已经安全”。
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from enum import Enum
from typing import Optional

from .config import settings
from .generator import DemoGenerator, FixedConfigGenerator, LLMGenerator
from .intent_parser import parse_intent
from .schemas import (
    Attempt,
    Decision,
    GenerationResult,
    Intent,
    ReviewRecord,
    ReviewRequest,
    TaskState,
    ValidationReport,
    now_iso,
)
from .states import StateMachine, TaskStatus, TransitionRecord
from .validator import validate_config


class AgentAction(str, Enum):
    GENERATE_CONFIG = "GENERATE_CONFIG"
    VALIDATE_CONFIG = "VALIDATE_CONFIG"
    RETRY_GENERATION = "RETRY_GENERATION"
    REQUEST_USER_INFO = "REQUEST_USER_INFO"
    REQUEST_HUMAN_REVIEW = "REQUEST_HUMAN_REVIEW"
    COMPLETE_TASK = "COMPLETE_TASK"
    ABORT_TASK = "ABORT_TASK"


STRUCTURAL_FATAL = {
    "JSON_PARSE_ERROR",
    "MISSING_RULES",
    "RULES_NOT_LIST",
    "ROOT_NOT_OBJECT",
    "EMPTY_RULES",
    "MISSING_DEFAULT_ACTION",
}


def _intent_summary(intent: Intent) -> str:
    src = ", ".join(intent.sources) or "未识别"
    dst = ", ".join(intent.destinations) or "未识别"
    proto = intent.protocol or "未识别"
    port = f"/{intent.destination_port}" if intent.destination_port else ""
    action = intent.action or "未识别"
    return f"{action} {proto}{port}：{src} → {dst}"


class Agent:
    def __init__(self, step_delay: Optional[float] = None, generator=None) -> None:
        self.step_delay = settings.step_delay if step_delay is None else step_delay
        self._forced_generator = generator

    # ------------------------------------------------------------------
    # 工具选择
    # ------------------------------------------------------------------
    def _generator(self, task: TaskState):
        if self._forced_generator is not None:
            return self._forced_generator
        if task.params.mode == "api":
            return LLMGenerator()
        return DemoGenerator()

    async def _sleep(self) -> None:
        if self.step_delay > 0:
            await asyncio.sleep(self.step_delay)

    # ------------------------------------------------------------------
    # 状态机回调 → 任务状态与事件同步
    # ------------------------------------------------------------------
    def _make_sm(self, task: TaskState) -> StateMachine:
        def on_transition(record: TransitionRecord) -> None:
            level = "info"
            if record.to_status in (TaskStatus.FAILED, TaskStatus.BLOCKED):
                level = "error"
            elif record.to_status in (TaskStatus.NEED_INFO, TaskStatus.REVIEW_REQUIRED):
                level = "warning"
            elif record.to_status == TaskStatus.SUCCESS:
                level = "success"
            elif record.to_status == TaskStatus.RETRYING:
                level = "warning"
            task.set_status(record.to_status.value)
            task.event(
                f"状态变更：{record.from_status.value} → {record.to_status.value}。{record.reason}",
                level=level,
                detail=f"重试次数 {record.retry_count}/{task.params.max_retries}",
            )

        return StateMachine(
            status=TaskStatus(task.status),
            retry_count=task.retry_count,
            max_retries=task.params.max_retries,
            on_transition=on_transition,
        )

    # ------------------------------------------------------------------
    # 主流程
    # ------------------------------------------------------------------
    async def run(self, task: TaskState, resume: bool = False) -> TaskState:
        sm = self._make_sm(task)
        task.started_at = task.started_at or now_iso()
        started = datetime.fromisoformat(task.started_at)

        try:
            if sm.status == TaskStatus.NEED_INFO:
                sm.transition(TaskStatus.ANALYZING, "收到用户补充信息，重新解析需求。")
            elif sm.status == TaskStatus.RECEIVED:
                task.event("接收用户需求。", level="info")
                sm.transition(
                    TaskStatus.ANALYZING,
                    "开始分析需求：提取源地址、目标地址、协议、端口与访问动作。",
                )
            else:
                raise RuntimeError(f"任务 {task.id} 当前状态为 {sm.status.value}，不能继续自动执行。")

            await self._sleep()
            intent = parse_intent(task.requirement)
            task.intent = intent
            detail = "；".join(intent.notes) or None
            task.event(
                f"需求解析完成：{_intent_summary(intent)}",
                level="info",
                detail=detail,
            )
            if intent.assumptions:
                task.event(
                    "解析假设：" + "；".join(intent.assumptions),
                    level="warning",
                )

            if not intent.is_complete:
                task.missing_fields = list(intent.missing)
                reason = (
                    "需求缺少必要信息（"
                    + "、".join(intent.missing)
                    + "）。Agent 选择请求用户补充，而不是猜测网络地址。"
                )
                task.decision(
                    AgentAction.REQUEST_USER_INFO.value,
                    reason,
                    error_codes=[f"MISSING_{m.upper()}" for m in intent.missing],
                    requires_human_review=True,
                )
                sm.transition(TaskStatus.NEED_INFO, reason)
                self._finalize(task, started, waiting=True)
                return task

            task.missing_fields = []
            await self._generate_validate_loop(task, sm, intent)
        except Exception as exc:  # 安全失败：异常不应让任务停留在中间态
            task.event(f"执行异常，任务终止：{type(exc).__name__}: {exc}", level="error")
            if not sm.is_terminal and sm.can_transition(TaskStatus.FAILED):
                sm.transition(TaskStatus.FAILED, f"执行异常，按安全失败策略终止：{exc}")

        self._finalize(task, started)
        return task

    def _finalize(self, task: TaskState, started: datetime, waiting: bool = False) -> None:
        if waiting:
            task.finished_at = None
        else:
            task.finished_at = now_iso()
        try:
            end = datetime.fromisoformat(task.finished_at) if task.finished_at else datetime.fromisoformat(
                now_iso()
            )
            task.duration_ms = max(0, int((end - started).total_seconds() * 1000))
        except ValueError:  # pragma: no cover
            task.duration_ms = None

    async def _generate_validate_loop(
        self, task: TaskState, sm: StateMachine, intent: Intent
    ) -> None:
        generator = self._generator(task)

        while True:
            attempt_index = len(task.attempts)
            reason = (
                "调用配置生成模块，生成候选 ACL 配置。"
                if attempt_index == 0
                else f"第 {attempt_index} 次修正：根据校验反馈重新生成配置。"
            )
            task.decision(AgentAction.GENERATE_CONFIG.value, reason, attempt=attempt_index)
            sm.transition(TaskStatus.GENERATING, reason)
            await self._sleep()

            feedback_codes: list[str] = []
            feedback_detail: list[str] = []
            if task.attempts:
                prev = task.attempts[-1].validation
                if prev is not None:
                    feedback_codes = [f.code for f in prev.findings if f.retryable]
                    feedback_detail = [
                        f"[{f.code}] {f.message} 依据：{f.evidence}" for f in prev.findings if f.retryable
                    ]

            result = await self._generate(generator, intent, attempt_index, task, feedback_codes, feedback_detail)

            note = result.note or ""
            level = "info"
            if result.error:
                level = "warning"
            task.event(
                f"配置生成完成（attempt {attempt_index + 1}）。{note}",
                level=level,
                detail=(f"错误：{result.error}" if result.error else None),
            )

            if result.source == "demo":
                task.usage.demo_generation_calls += 1
            elif result.source == "llm" and result.error is None:
                # 只统计真正成功返回的模型调用；失败请求不虚增调用次数
                task.usage.api_calls += 1
                if result.prompt_tokens is not None:
                    task.usage.prompt_tokens = (task.usage.prompt_tokens or 0) + result.prompt_tokens
                if result.completion_tokens is not None:
                    task.usage.completion_tokens = (
                        task.usage.completion_tokens or 0
                    ) + result.completion_tokens

            attempt = Attempt(
                index=attempt_index + 1,
                kind="initial" if attempt_index == 0 else "correction",
                note=note,
                raw=result.raw,
                config=result.config,
                generation_source=result.source,
                error=result.error,
            )
            task.attempts.append(attempt)

            # 模型明确表示信息不足 → 请求补充
            if result.error == "NEED_INFO":
                reason = "模型返回信息不足：" + note
                task.missing_fields = ["source", "destination"]
                task.decision(
                    AgentAction.REQUEST_USER_INFO.value,
                    reason,
                    error_codes=["MODEL_NEED_INFO"],
                    requires_human_review=True,
                )
                sm.transition(TaskStatus.NEED_INFO, reason)
                return

            task.decision(AgentAction.VALIDATE_CONFIG.value, "调用 Python 校验工具检查候选配置。")
            sm.transition(TaskStatus.VALIDATING, "对候选配置执行结构、字段值、授权范围与风险规则检查。")
            await self._sleep()

            report = validate_config(result.raw if result.raw else result.config, intent, task.params)
            attempt.validation = report
            codes = sorted(set(report.codes()))
            task.event(
                f"Python 校验完成：共 {len(report.findings)} 条检查项，"
                f"{'通过' if report.passed else '未通过'}"
                + (f"（{', '.join(codes)}）" if codes else "。"),
                level="success" if report.passed else "warning",
            )

            action, target, reason, needs_review = self._decide(task, sm, report)
            task.decision(
                action.value,
                reason,
                error_codes=codes,
                requires_human_review=needs_review,
            )

            if action == AgentAction.RETRY_GENERATION:
                sm.consume_retry()
                task.retry_count = sm.retry_count
                sm.transition(TaskStatus.RETRYING, reason)
                await self._sleep()
                continue

            sm.transition(target, reason)
            return

    async def _generate(
        self,
        generator,
        intent: Intent,
        attempt_index: int,
        task: TaskState,
        feedback_codes: list[str],
        feedback_detail: list[str],
    ) -> GenerationResult:
        if isinstance(generator, LLMGenerator):
            return await generator.generate(
                intent,
                attempt_index=attempt_index,
                feedback_codes=feedback_codes,
                params=task.params,
                feedback_detail=feedback_detail,
            )
        return generator.generate(
            intent,
            attempt_index=attempt_index,
            feedback_codes=feedback_codes,
            params=task.params,
        )

    # ------------------------------------------------------------------
    # 决策规则（确定性，可解释）
    # ------------------------------------------------------------------
    def _decide(
        self, task: TaskState, sm: StateMachine, report: ValidationReport
    ) -> tuple[AgentAction, TaskStatus, str, bool]:
        findings = report.findings
        codes = ", ".join(sorted(set(report.codes()))) or "无"
        blocking = [f for f in findings if f.blocking]
        high = [f for f in findings if f.severity in ("HIGH", "CRITICAL")]
        significant = [f for f in findings if f.severity in ("MEDIUM", "HIGH", "CRITICAL")]

        # 1) 命中不可自动消除的严重风险 → 安全拦截
        if blocking:
            reason = (
                f"校验命中严重风险规则（{codes}），该类风险不能通过重新生成配置自动消除。"
                "按安全边界要求停止自动处理并进入安全拦截，需人工审核后另行决定。"
            )
            if not task.params.enable_high_risk_block:
                reason += "（高风险自动拦截开关已关闭，但安全边界仍禁止此类配置自动通过，因此转人工审核。）"
                return AgentAction.REQUEST_HUMAN_REVIEW, TaskStatus.REVIEW_REQUIRED, reason, True
            return AgentAction.REQUEST_HUMAN_REVIEW, TaskStatus.BLOCKED, reason, True

        # 2) 校验未通过
        if significant:
            fixable = all(f.retryable for f in findings if f.severity in ("MEDIUM", "HIGH", "CRITICAL"))
            can_retry = (
                task.params.enable_feedback_fix
                and fixable
                and sm.can_retry()
                and not any(f.code in STRUCTURAL_FATAL and not f.retryable for f in findings)
            )
            if can_retry:
                next_round = sm.retry_count + 1
                reason = (
                    f"校验未通过（{codes}），问题属于可通过重新生成修正的类型。"
                    f"Agent 选择请求重新生成；本次为第 {next_round} 次修正，"
                    f"自动修正上限 {task.params.max_retries} 次。"
                )
                return AgentAction.RETRY_GENERATION, TaskStatus.RETRYING, reason, False

            if not task.params.enable_feedback_fix:
                stop_reason = "反馈修正功能已关闭"
            elif not fixable:
                stop_reason = "存在无法通过重新生成消除的问题"
            else:
                stop_reason = (
                    f"已达到最大自动修正次数（{task.params.max_retries} 次），"
                    "按约束停止自动重试"
                )
            reason = f"校验未通过（{codes}），{stop_reason}。Agent 停止自动处理并转交人工审核。"
            if high or task.params.require_human_review:
                return AgentAction.REQUEST_HUMAN_REVIEW, TaskStatus.REVIEW_REQUIRED, reason, True
            reason = f"校验未通过（{codes}），{stop_reason}，且未启用人工审核，任务判定为失败。"
            return AgentAction.ABORT_TASK, TaskStatus.FAILED, reason, False

        # 3) 通过检查
        if report.passed:
            if task.params.require_human_review:
                reason = (
                    "Python 校验未发现中高风险问题，但按任务参数仍需人工审核。"
                    "审核通过仅代表确认候选配置，不代表已下发到设备。"
                )
                return AgentAction.REQUEST_HUMAN_REVIEW, TaskStatus.REVIEW_REQUIRED, reason, True
            reason = (
                "Python 校验未发现中高风险问题，且未要求人工审核，任务在通过检查后结束。"
                "注意：通过预定义检查不代表配置绝对安全，也没有向任何真实设备下发配置。"
            )
            return AgentAction.COMPLETE_TASK, TaskStatus.SUCCESS, reason, False

        # 4) 只有提示级别问题
        reason = "校验仅产生提示级信息，未发现需要阻断的问题。"
        if task.params.require_human_review:
            return AgentAction.REQUEST_HUMAN_REVIEW, TaskStatus.REVIEW_REQUIRED, reason, True
        return AgentAction.COMPLETE_TASK, TaskStatus.SUCCESS, reason, False

    # ------------------------------------------------------------------
    # 人工审核
    # ------------------------------------------------------------------
    async def review(self, task: TaskState, req: ReviewRequest) -> TaskState:
        sm = self._make_sm(task)
        if sm.status not in (TaskStatus.REVIEW_REQUIRED, TaskStatus.BLOCKED):
            raise ValueError(f"当前状态 {sm.status.value} 不允许人工审核操作。")

        record = ReviewRecord(decision=req.decision, comment=req.comment, reviewer=req.reviewer)
        if req.decision == "approve" and sm.status == TaskStatus.BLOCKED:
            if not req.comment.strip():
                raise ValueError("该配置命中严重风险，批准时必须填写审核理由。")
            record.high_risk_acknowledged = True
        task.review = record

        started = datetime.fromisoformat(task.started_at or now_iso())

        if req.decision == "approve":
            task.event(
                f"人工审核通过（审核人：{req.reviewer}）。审核意见：{req.comment or '无'}",
                level="warning" if record.high_risk_acknowledged else "success",
                detail="审核通过仅代表确认候选配置，未向任何真实设备下发。",
            )
            sm.transition(
                TaskStatus.SUCCESS,
                "人工审核通过，候选配置被确认（未下发设备）。"
                + ("注意：该配置命中过严重风险，风险由审核人显式接受。" if record.high_risk_acknowledged else ""),
            )
        elif req.decision == "reject":
            task.event(
                f"人工审核拒绝（审核人：{req.reviewer}）。审核意见：{req.comment or '无'}",
                level="error",
            )
            sm.transition(TaskStatus.FAILED, "人工审核拒绝，配置不予采用。")
        else:  # request_changes
            task.event(
                f"人工审核要求修改（审核人：{req.reviewer}）。审核意见：{req.comment or '无'}",
                level="warning",
            )
            if sm.can_retry():
                sm.consume_retry()
                task.retry_count = sm.retry_count
                reason = (
                    "审核人要求重新生成配置，且自动修正次数未达上限，进入反馈修正流程。"
                )
                sm.transition(TaskStatus.RETRYING, reason)
                intent = task.intent or parse_intent(task.requirement)
                await self._generate_validate_loop(task, sm, intent)
                self._finalize(task, started)
                return task

            reason = (
                f"审核人要求重新生成配置，但已达到最大自动修正次数（{task.params.max_retries} 次），"
                "保持待审核状态，需人工进一步处理。"
            )
            task.event(reason, level="warning")
            task.decision(AgentAction.REQUEST_HUMAN_REVIEW.value, reason, requires_human_review=True)

        task.finished_at = now_iso()
        self._finalize(task, started)
        return task
