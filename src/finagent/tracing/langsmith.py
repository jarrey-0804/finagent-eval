"""
LangSmith 追踪集成模块

提供 LangSmith 追踪功能，用于评测过程的可视化与调试。
当 langsmith 包未安装时，所有方法自动降级为 no-op，不影响系统正常运行。
"""

from __future__ import annotations

import asyncio
import functools
import os
import uuid
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from ..utils.logging import get_logger

logger = get_logger(__name__)

__all__ = [
    "LangSmithTracer",
    "TraceContext",
    "TraceEvaluation",
]

# ---------------------------------------------------------------------------
# 尝试导入 langsmith，不可用时设为 None
# ---------------------------------------------------------------------------
try:
    from langsmith import Client as LangSmithClient
    from langsmith.run_trees import RunTree

    _LANGSMITH_AVAILABLE = True
except ImportError:
    LangSmithClient = None  # type: ignore[assignment, misc]
    RunTree = None  # type: ignore[assignment, misc]
    _LANGSMITH_AVAILABLE = False


# ---------------------------------------------------------------------------
# TraceContext - 追踪上下文数据类
# ---------------------------------------------------------------------------


@dataclass
class TraceContext:
    """当前追踪状态，保存 run 层级关系。"""

    run_id: str | None = None
    parent_run_id: str | None = None
    evaluation_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# LangSmithTracer - LangSmith 追踪封装
# ---------------------------------------------------------------------------


class LangSmithTracer:
    """
    LangSmith 追踪封装类。

    在 langsmith 包可用时提供完整的追踪功能；
    不可用时所有公开方法均为 no-op，通过 ``is_enabled`` 属性查询状态。
    """

    def __init__(
        self,
        project_name: str | None = None,
        api_key: str | None = None,
        api_url: str | None = None,
    ) -> None:
        """
        Args:
            project_name: LangSmith 项目名称，默认读取 LANGSMITH_PROJECT 环境变量。
            api_key: LangSmith API Key，默认读取 LANGSMITH_API_KEY 环境变量。
            api_url: LangSmith API URL，默认读取 LANGSMITH_ENDPOINT 环境变量。
        """
        self._project_name: str | None = project_name or os.getenv(
            "LANGSMITH_PROJECT", "finagent-eval"
        )
        self._api_key: str | None = api_key or os.getenv("LANGSMITH_API_KEY")
        self._api_url: str | None = api_url or os.getenv("LANGSMITH_ENDPOINT")

        self._client: Any = None
        self._enabled: bool = False
        self._runs: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # 公开属性
    # ------------------------------------------------------------------

    @property
    def is_enabled(self) -> bool:
        """LangSmith 是否可用且已配置。"""
        return self._enabled

    # ------------------------------------------------------------------
    # 初始化
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """
        初始化 LangSmith 客户端并创建项目。

        若 langsmith 未安装或 API Key 未配置，将记录警告并禁用追踪。
        """
        if not _LANGSMITH_AVAILABLE:
            logger.warning(
                "langsmith 包未安装，追踪功能已禁用。可通过 'pip install langsmith' 安装。"
            )
            self._enabled = False
            return

        if not self._api_key:
            logger.warning(
                "LANGSMITH_API_KEY 未配置，LangSmith 追踪已禁用。"
                "请设置环境变量 LANGSMITH_API_KEY 或在构造时传入 api_key。"
            )
            self._enabled = False
            return

        try:
            self._client = LangSmithClient(
                api_key=self._api_key,
                api_url=self._api_url,
            )
            self._enabled = True
            logger.info(
                "LangSmith 追踪已启用，项目: %s",
                self._project_name,
            )
        except Exception as exc:
            logger.warning("LangSmith 客户端初始化失败: %s", exc)
            self._enabled = False

    # ------------------------------------------------------------------
    # Run 生命周期
    # ------------------------------------------------------------------

    def start_evaluation_run(
        self,
        evaluation_id: str,
        agent_id: str,
        mode: str,
    ) -> str | None:
        """
        启动一个评测级别的 LangSmith run。

        Args:
            evaluation_id: 评测 ID。
            agent_id: Agent ID。
            mode: 评测模式（如 "full", "quick"）。

        Returns:
            run_id 字符串；若追踪未启用则返回 None。
        """
        if not self._enabled or self._client is None:
            return None

        try:
            run_id = str(uuid.uuid4())
            run = self._client.create_run(
                name=f"evaluation-{evaluation_id}",
                run_id=run_id,
                run_type="chain",
                inputs={
                    "evaluation_id": evaluation_id,
                    "agent_id": agent_id,
                    "mode": mode,
                },
                project_name=self._project_name,
                tags=["evaluation", mode, agent_id],
            )
            self._runs[run_id] = run
            logger.debug("LangSmith 评测 run 已启动: %s", run_id)
            return run_id
        except Exception as exc:
            logger.warning("启动 LangSmith 评测 run 失败: %s", exc)
            return None

    def start_task_run(
        self,
        parent_run_id: str | None,
        task_id: str,
        dimension: str,
    ) -> str | None:
        """
        启动一个任务级别的子 run。

        Args:
            parent_run_id: 父 run ID（评测 run）。
            task_id: 任务 ID。
            dimension: 评测维度。

        Returns:
            run_id 字符串；若追踪未启用则返回 None。
        """
        if not self._enabled or self._client is None:
            return None

        try:
            run_id = str(uuid.uuid4())
            run = self._client.create_run(
                name=f"task-{task_id}",
                run_id=run_id,
                run_type="chain",
                inputs={
                    "task_id": task_id,
                    "dimension": dimension,
                },
                project_name=self._project_name,
                tags=["task", dimension],
                parent_run_id=parent_run_id,
            )
            self._runs[run_id] = run
            logger.debug("LangSmith 任务 run 已启动: %s (parent=%s)", run_id, parent_run_id)
            return run_id
        except Exception as exc:
            logger.warning("启动 LangSmith 任务 run 失败: %s", exc)
            return None

    def end_run(
        self,
        run_id: str | None,
        outputs: dict | None = None,
        error: str | None = None,
    ) -> None:
        """
        结束一个 run，并记录输出或错误。

        Args:
            run_id: 要结束的 run ID。
            outputs: run 输出数据。
            error: 错误信息（若有）。
        """
        if not self._enabled or self._client is None or run_id is None:
            return

        try:
            end_data: dict[str, Any] = {}
            if outputs is not None:
                end_data["outputs"] = outputs
            if error is not None:
                end_data["error"] = error

            self._client.update_run(
                run_id,
                **end_data,
            )
            self._runs.pop(run_id, None)
            logger.debug("LangSmith run 已结束: %s", run_id)
        except Exception as exc:
            logger.warning("结束 LangSmith run 失败: %s", exc)

    # ------------------------------------------------------------------
    # 评分记录
    # ------------------------------------------------------------------

    def log_evaluation_score(
        self,
        run_id: str | None,
        metric_name: str,
        score: float,
        details: dict | None = None,
    ) -> None:
        """
        向指定 run 记录一个评分。

        Args:
            run_id: 目标 run ID。
            metric_name: 指标名称（如 "accuracy", "overall_score"）。
            score: 分数值。
            details: 额外详情。
        """
        if not self._enabled or self._client is None or run_id is None:
            return

        try:
            self._client.create_feedback(
                run_id,
                key=metric_name,
                score=score,
                comment=details,  # type: ignore[arg-type]
            )
            logger.debug(
                "LangSmith 评分已记录: run=%s, metric=%s, score=%.2f",
                run_id,
                metric_name,
                score,
            )
        except Exception as exc:
            logger.warning("记录 LangSmith 评分失败: %s", exc)

    # ------------------------------------------------------------------
    # URL 生成
    # ------------------------------------------------------------------

    def get_run_url(self, run_id: str | None) -> str | None:
        """
        获取 LangSmith 中查看指定 run 的 URL。

        Args:
            run_id: 目标 run ID。

        Returns:
            可访问的 URL 字符串；若追踪未启用则返回 None。
        """
        if not self._enabled or run_id is None:
            return None

        base_url = self._api_url or "https://smith.langchain.com"
        # 移除尾部路径（如 /api），替换为 app 前缀
        base_url = base_url.rstrip("/")
        if base_url.endswith("/api"):
            base_url = base_url[:-4]

        return f"{base_url}/o/default/projects/p/{self._project_name}?run={run_id}"


# ---------------------------------------------------------------------------
# TraceEvaluation - 装饰器 / 上下文管理器
# ---------------------------------------------------------------------------


class TraceEvaluation:
    """
    将评测函数包裹在 LangSmith 追踪中的装饰器 / 上下文管理器。

    用法示例（装饰器）::

        tracer = LangSmithTracer()
        tracer.initialize()

        @TraceEvaluation(tracer, evaluation_id="eval-001", agent_id="agent-1", mode="full")
        def run_evaluation():
            ...

    用法示例（上下文管理器）::

        with TraceEvaluation(tracer, evaluation_id="eval-001", agent_id="agent-1", mode="full"):
            run_evaluation()
    """

    def __init__(
        self,
        tracer: LangSmithTracer,
        evaluation_id: str,
        agent_id: str,
        mode: str = "full",
    ) -> None:
        self._tracer = tracer
        self._evaluation_id = evaluation_id
        self._agent_id = agent_id
        self._mode = mode
        self._run_id: str | None = None
        self._context = TraceContext(
            evaluation_id=evaluation_id,
        )

    @property
    def context(self) -> TraceContext:
        """获取当前追踪上下文。"""
        return self._context

    # ------------------------------------------------------------------
    # 上下文管理器协议
    # ------------------------------------------------------------------

    def __enter__(self) -> TraceEvaluation:
        self._run_id = self._tracer.start_evaluation_run(
            evaluation_id=self._evaluation_id,
            agent_id=self._agent_id,
            mode=self._mode,
        )
        self._context.run_id = self._run_id
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        error = None
        if exc_type is not None:
            error = f"{exc_type.__name__}: {exc_val}"
            logger.error("评测追踪捕获异常: %s", error)

        self._tracer.end_run(
            run_id=self._run_id,
            outputs={"status": "error"} if error else {"status": "completed"},
            error=error,
        )

        # 不吞掉异常，让上层处理
        return False  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # 装饰器协议
    # ------------------------------------------------------------------

    def __call__(self, func: Callable) -> Callable:
        """作为装饰器使用。"""

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            with self:
                return func(*args, **kwargs)

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            with self:
                return await func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    # ------------------------------------------------------------------
    # 便捷方法：在上下文内启动子任务 run
    # ------------------------------------------------------------------

    @contextmanager
    def task_run(self, task_id: str, dimension: str) -> Generator[TraceContext, None, None]:
        """
        在评测 run 下启动一个子任务 run 的上下文管理器。

        Args:
            task_id: 任务 ID。
            dimension: 评测维度。

        Yields:
            包含子任务 run 信息的 TraceContext。
        """
        child_run_id = self._tracer.start_task_run(
            parent_run_id=self._run_id,
            task_id=task_id,
            dimension=dimension,
        )
        child_context = TraceContext(
            run_id=child_run_id,
            parent_run_id=self._run_id,
            evaluation_id=self._evaluation_id,
            metadata={"task_id": task_id, "dimension": dimension},
        )
        try:
            yield child_context
        except Exception as exc:
            self._tracer.end_run(
                run_id=child_run_id,
                error=f"{type(exc).__name__}: {exc}",
            )
            raise
        else:
            self._tracer.end_run(run_id=child_run_id)

    def log_score(
        self,
        metric_name: str,
        score: float,
        details: dict | None = None,
        run_id: str | None = None,
    ) -> None:
        """
        在当前追踪上下文中记录评分。

        Args:
            metric_name: 指标名称。
            score: 分数值。
            details: 额外详情。
            run_id: 指定 run ID；默认使用当前评测 run。
        """
        self._tracer.log_evaluation_score(
            run_id=run_id or self._run_id,
            metric_name=metric_name,
            score=score,
            details=details,
        )
