"""内存任务存储。

第一阶段不引入数据库：任务只保存在后端进程内存中，
- 重启后端后任务历史会清空；
- 前端另有一份本次会话的历史（localStorage），仅用于列表展示。
这一范围已在 README 中说明。
"""

from __future__ import annotations

from typing import Optional

from .schemas import TaskState, TaskSummary, ValidationReport


class TaskStore:
    def __init__(self) -> None:
        self._tasks: dict[str, TaskState] = {}
        self._order: list[str] = []

    def add(self, task: TaskState) -> TaskState:
        self._tasks[task.id] = task
        self._order.append(task.id)
        return task

    def get(self, task_id: str) -> Optional[TaskState]:
        return self._tasks.get(task_id)

    def all(self) -> list[TaskState]:
        return [self._tasks[tid] for tid in reversed(self._order) if tid in self._tasks]

    def summaries(self, limit: int = 50) -> list[TaskSummary]:
        items: list[TaskSummary] = []
        for task in self.all()[:limit]:
            report: Optional[ValidationReport] = task.final_validation
            items.append(
                TaskSummary(
                    id=task.id,
                    requirement=task.requirement,
                    status=task.status,
                    status_label=task.status_label,
                    created_at=task.created_at,
                    duration_ms=task.duration_ms,
                    mode=task.params.mode,
                    attempt_count=len(task.attempts),
                    risk_codes=sorted(
                        {f.code for f in (report.findings if report else []) if f.severity in ("HIGH", "CRITICAL")}
                    ),
                )
            )
        return items

    def clear(self) -> None:
        self._tasks.clear()
        self._order.clear()


task_store = TaskStore()
