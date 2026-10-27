"""FastAPI 入口：任务接口、测试用例接口与指标接口。

运行：
    uvicorn app.main:app --reload --port 8000
接口文档：
    http://127.0.0.1:8000/docs
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .agent import Agent
from .config import settings
from .metrics import compute_metrics, run_store
from .schemas import (
    CaseRunResult,
    FeedbackRequest,
    HealthResponse,
    ReviewRequest,
    TaskCreateRequest,
    TaskState,
    TestCaseDefinition,
    TestRunRequest,
    TestRunResponse,
    now_iso,
)
from .states import TaskStatus
from .store import task_store
from .test_runner import GROUP_META, run_cases
from .testcases import TEST_CASES, get_case

logger = logging.getLogger("acl_agent")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(
    title="ACL 智能运维与安全校验 Agent 原型",
    description="自然语言 → 结构化 ACL → Python 独立校验 → Agent 受约束决策（仅生成与检查，不下发设备）",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()] or ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# 异常处理：给前端可读的中文错误，而不是堆栈
# ---------------------------------------------------------------------------


@app.exception_handler(RequestValidationError)
async def _validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err.get("loc", []) if x not in ("body",))
        details.append(f"{loc or '参数'}：{err.get('msg', '格式不正确')}")
    return JSONResponse(status_code=422, content={"detail": "请求参数不合法：" + "；".join(details)})


@app.exception_handler(Exception)
async def _unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("未处理异常：%s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": f"服务器内部错误：{type(exc).__name__}。请查看后端日志，或改用演示模式重试。"},
    )


# ---------------------------------------------------------------------------
# 健康检查
# ---------------------------------------------------------------------------


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    notices = ["本原型只生成与检查配置，不连接、不下发任何真实网络设备。"]
    if not settings.api_mode_available:
        notices.append("未检测到 LLM_API_KEY，API 模式不可用；演示模式可正常使用。")
    return HealthResponse(
        status="ok",
        mode="api" if settings.api_mode_available else "demo",
        api_mode_available=settings.api_mode_available,
        model=settings.llm_model if settings.api_mode_available else None,
        notices=notices,
    )


# ---------------------------------------------------------------------------
# 任务
# ---------------------------------------------------------------------------


def _task_payload(task: TaskState) -> dict:
    payload = task.model_dump()
    report = task.final_validation
    payload["final_config"] = task.final_config
    payload["final_validation"] = report.model_dump() if report is not None else None
    payload["token_display"] = task.usage.token_display
    payload["mode_label"] = "演示模式" if task.params.mode == "demo" else "API 模式"
    payload["is_terminal"] = task.status in (TaskStatus.SUCCESS.value, TaskStatus.FAILED.value)
    payload["awaiting_user"] = task.status == TaskStatus.NEED_INFO.value
    payload["awaiting_review"] = task.status == TaskStatus.REVIEW_REQUIRED.value
    payload["deployed"] = False
    return payload


async def _run_agent(task: TaskState, resume: bool = False) -> None:
    try:
        await Agent().run(task, resume=resume)
    except Exception as exc:  # 安全失败：任务不应停留在中间状态
        logger.exception("任务执行异常 %s", task.id)
        task.event(f"任务执行异常，已终止：{type(exc).__name__}: {exc}", level="error")
        if task.status not in (TaskStatus.SUCCESS.value, TaskStatus.FAILED.value):
            try:
                task.set_status(TaskStatus.FAILED.value, "执行异常，按安全失败策略终止。")
            except Exception:  # pragma: no cover
                task.status = TaskStatus.FAILED.value
        task.finished_at = now_iso()


@app.post("/api/tasks", status_code=201)
async def create_task(req: TaskCreateRequest) -> dict:
    if req.params.mode == "api" and not settings.api_mode_available:
        raise HTTPException(
            status_code=400,
            detail="API 模式不可用：后端未配置 LLM_API_KEY。请改用演示模式，或先在 .env 中配置模型服务。",
        )
    task = TaskState(
        id=f"task-{uuid.uuid4().hex[:10]}",
        requirement=req.requirement,
        params=req.params,
    )
    task_store.add(task)
    asyncio.create_task(_run_agent(task))
    return _task_payload(task)


@app.get("/api/tasks")
async def list_tasks() -> dict:
    return {"items": [s.model_dump() for s in task_store.summaries()]}


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str) -> dict:
    task = task_store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在（后端重启后内存任务会清空）。")
    return _task_payload(task)


@app.get("/api/tasks/{task_id}/events")
async def get_task_events(task_id: str) -> dict:
    task = task_store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在。")
    return {
        "task_id": task.id,
        "status": task.status,
        "status_label": task.status_label,
        "retry_count": task.retry_count,
        "max_retries": task.params.max_retries,
        "events": [e.model_dump() for e in task.events],
        "decisions": [d.model_dump() for d in task.decisions],
    }


@app.post("/api/tasks/{task_id}/feedback")
async def submit_feedback(task_id: str, req: FeedbackRequest) -> dict:
    task = task_store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在。")
    if task.status != TaskStatus.NEED_INFO.value:
        raise HTTPException(
            status_code=409,
            detail=f"任务当前状态为 {task.status_label}，只有“需要补充信息”的任务可以提交补充信息。",
        )
    task.requirement = f"{task.requirement}\n补充信息：{req.message}"
    task.event(f"收到用户补充信息：{req.message}", level="info")
    task.missing_fields = []
    asyncio.create_task(_run_agent(task, resume=True))
    return _task_payload(task)


@app.post("/api/tasks/{task_id}/review")
async def submit_review(task_id: str, req: ReviewRequest) -> dict:
    task = task_store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在。")
    if task.status not in (TaskStatus.REVIEW_REQUIRED.value, TaskStatus.BLOCKED.value):
        raise HTTPException(
            status_code=409,
            detail=f"任务当前状态为 {task.status_label}，只有待人工审核或安全拦截的任务可以提交审核意见。",
        )
    try:
        await Agent().review(task, req)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _task_payload(task)


# ---------------------------------------------------------------------------
# 测试用例
# ---------------------------------------------------------------------------


def _case_payload(case: TestCaseDefinition) -> dict:
    payload = case.model_dump()
    last = run_store.latest_for_case(case.id)
    payload["last_results"] = {g: r.model_dump() for g, r in last.items()}
    return payload


@app.get("/api/test-cases")
async def list_test_cases() -> dict:
    return {
        "items": [_case_payload(c) for c in TEST_CASES],
        "total": len(TEST_CASES),
        "notice": (
            "这些用例由作者手工设计并标注预期结果；演示模式下的执行结果只反映原型行为，"
            "不是真实大模型的实验结果。"
        ),
    }


@app.post("/api/test-cases/run", response_model=TestRunResponse)
async def run_test_cases(req: TestRunRequest) -> TestRunResponse:
    if req.case_ids:
        cases = []
        for cid in req.case_ids:
            case = get_case(cid)
            if case is None:
                raise HTTPException(status_code=404, detail=f"测试用例 {cid} 不存在。")
            cases.append(case)
    else:
        cases = list(TEST_CASES)

    if req.group == "agent" and any(c.params.mode == "api" for c in cases):
        if not settings.api_mode_available:
            raise HTTPException(status_code=400, detail="用例要求 API 模式，但后端未配置 LLM_API_KEY。")

    started = now_iso()
    results: list[CaseRunResult] = await run_cases(cases, req.group, step_delay=0.0)
    run_store.record(results, mode="demo" if all(c.params.mode == "demo" for c in cases) else "api")
    finished = now_iso()
    passed = len([r for r in results if r.matched_expected])
    group_note = {
        "basic": "A 组只生成配置、不做校验，因此“应被校验发现问题”的用例不会符合最终预期，这正是对照组的意义。",
        "validate": "B 组只做一次校验、不执行修正，因此“需要修正后才能通过”的用例不会全部符合预期。",
        "agent": "C 组执行完整 Agent 闭环（修正 / 请求补充 / 人工审核）。",
    }[req.group]
    notice = (
        f"当前为{'演示模式' if all(c.params.mode == 'demo' for c in cases) else 'API 模式'}测试，"
        "结果来自本机真实执行。" + group_note + " 这些结果不能作为真实大模型能力结论。"
    )
    return TestRunResponse(
        group=req.group,
        group_label=GROUP_META[req.group]["label"],
        mode="demo" if all(c.params.mode == "demo" for c in cases) else "api",
        started_at=started,
        finished_at=finished,
        results=results,
        passed=passed,
        total=len(results),
        notice=notice,
    )


# ---------------------------------------------------------------------------
# 指标与实验
# ---------------------------------------------------------------------------


@app.get("/api/metrics")
async def get_metrics() -> dict:
    return compute_metrics().model_dump()


@app.post("/api/experiments/run")
async def run_experiment() -> dict:
    """运行三组对比实验（A 基础生成 / B 生成+校验 / C Agent 闭环）。"""
    all_results: list[CaseRunResult] = []
    for group in ("basic", "validate", "agent"):
        all_results.extend(await run_cases(list(TEST_CASES), group, step_delay=0.0))
    run_store.record(all_results, mode="demo")
    return compute_metrics().model_dump()


@app.post("/api/experiments/reset")
async def reset_experiment() -> dict:
    run_store.clear()
    return {"status": "cleared", "detail": "已清除本进程内的测试与实验统计记录。"}


# ---------------------------------------------------------------------------
# 可选：直接托管前端构建产物（npm run build 之后）
# ---------------------------------------------------------------------------

DIST_DIR = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if DIST_DIR.exists():
    app.mount("/", StaticFiles(directory=str(DIST_DIR), html=True), name="frontend")
else:

    @app.get("/")
    async def root() -> dict:
        return {
            "detail": "后端已启动。前端请运行 npm run dev 后访问 http://127.0.0.1:5173；"
            "接口文档见 /docs。",
        }
