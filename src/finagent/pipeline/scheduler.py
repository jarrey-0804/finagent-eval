"""
评测任务调度器

管理评测任务的排队、调度和并发执行。
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .._compat import StrEnum
from .quota import QuotaConfig, ResourceQuota


class TaskPriority(StrEnum):
    """任务优先级"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class ScheduledTaskStatus(StrEnum):
    """调度任务状态"""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ScheduledTask:
    """调度任务"""
    task_id: str
    evaluation_id: str
    agent_id: str
    priority: TaskPriority
    status: ScheduledTaskStatus = ScheduledTaskStatus.QUEUED
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: dict | None = None
    error: str | None = None
    retry_count: int = 0


class SchedulerConfig(BaseModel):
    """调度器配置"""
    max_concurrent_evaluations: int = Field(default=3, description="最大并发评测数")
    max_queue_size: int = Field(default=50, description="最大队列大小")
    task_timeout: int = Field(default=43200, description="任务超时(秒)，默认12小时")
    retry_limit: int = Field(default=2, description="最大重试次数")
    retry_delay: int = Field(default=30, description="重试延迟(秒)")

    # 资源配额
    quota_config: QuotaConfig = Field(default_factory=QuotaConfig)


class EvaluationScheduler:
    """
    评测任务调度器

    功能：
    - 任务排队和优先级调度
    - 并发控制（max=3）
    - 资源配额管理
    - 任务超时和重试
    - 断点续跑支持
    """

    def __init__(self, config: SchedulerConfig | None = None):
        self.config = config or SchedulerConfig()
        self._queue: list[ScheduledTask] = []
        self._running: dict[str, ScheduledTask] = {}
        self._completed: list[ScheduledTask] = []
        self._quota = ResourceQuota(self.config.quota_config)
        self._lock = asyncio.Lock()
        self._scheduler_task: asyncio.Task | None = None

    async def submit(
        self,
        evaluation_id: str,
        agent_id: str,
        priority: TaskPriority = TaskPriority.NORMAL,
        task_func: Any | None = None,
    ) -> str:
        """
        提交评测任务

        Returns:
            任务ID
        """
        async with self._lock:
            if len(self._queue) >= self.config.max_queue_size:
                raise RuntimeError(f"任务队列已满 ({self.config.max_queue_size})")

            task_id = str(uuid.uuid4())
            task = ScheduledTask(
                task_id=task_id,
                evaluation_id=evaluation_id,
                agent_id=agent_id,
                priority=priority,
            )

            # 按优先级插入队列
            inserted = False
            for i, existing in enumerate(self._queue):
                priority_order = {
                    TaskPriority.URGENT: 0,
                    TaskPriority.HIGH: 1,
                    TaskPriority.NORMAL: 2,
                    TaskPriority.LOW: 3,
                }
                if priority_order[priority] < priority_order.get(existing.priority, 2):
                    self._queue.insert(i, task)
                    inserted = True
                    break

            if not inserted:
                self._queue.append(task)

            return task_id

    async def start(self):
        """启动调度器"""
        self._scheduler_task = asyncio.create_task(self._schedule_loop())

    async def stop(self):
        """停止调度器"""
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass

    async def _schedule_loop(self):
        """调度循环"""
        while True:
            async with self._lock:
                # 检查是否有空闲槽位
                while (
                    len(self._running) < self.config.max_concurrent_evaluations
                    and self._queue
                ):
                    # 检查资源配额
                    if not self._quota.can_allocate():
                        break

                    task = self._queue.pop(0)
                    task.status = ScheduledTaskStatus.RUNNING
                    task.started_at = datetime.now()
                    self._running[task.task_id] = task

                    # 分配资源
                    self._quota.allocate(task.evaluation_id)

                    # 启动任务（异步）
                    asyncio.create_task(
                        self._execute_task(task)
                    )

            await asyncio.sleep(1)

    async def _execute_task(self, task: ScheduledTask):
        """执行任务"""
        try:
            # 这里应该调用实际的评测流水线
            # 简化实现：模拟执行
            await asyncio.sleep(1)

            task.status = ScheduledTaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.result = {"status": "completed"}

        except Exception as e:
            if task.retry_count < self.config.retry_limit:
                task.retry_count += 1
                task.status = ScheduledTaskStatus.QUEUED
                await asyncio.sleep(self.config.retry_delay)
                self._queue.append(task)
            else:
                task.status = ScheduledTaskStatus.FAILED
                task.error = str(e)

        finally:
            # 释放资源
            self._quota.release(task.evaluation_id)
            async with self._lock:
                self._running.pop(task.task_id, None)
                self._completed.append(task)

    def get_task_status(self, task_id: str) -> dict | None:
        """获取任务状态"""
        for task in self._queue + list(self._running.values()) + self._completed:
            if task.task_id == task_id:
                return {
                    "task_id": task.task_id,
                    "evaluation_id": task.evaluation_id,
                    "status": task.status.value,
                    "priority": task.priority.value,
                    "created_at": task.created_at.isoformat(),
                    "started_at": task.started_at.isoformat() if task.started_at else None,
                    "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                    "retry_count": task.retry_count,
                }
        return None

    def get_queue_status(self) -> dict:
        """获取队列状态"""
        return {
            "queue_size": len(self._queue),
            "running_count": len(self._running),
            "completed_count": len(self._completed),
            "max_concurrent": self.config.max_concurrent_evaluations,
            "quota_usage": self._quota.get_usage(),
        }

    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        async with self._lock:
            for i, task in enumerate(self._queue):
                if task.task_id == task_id:
                    task.status = ScheduledTaskStatus.CANCELLED
                    self._queue.pop(i)
                    return True

            if task_id in self._running:
                self._running[task_id].status = ScheduledTaskStatus.CANCELLED
                return True

        return False
