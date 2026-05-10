"""
评测引擎模块

提供快速评测和完整评测模式的引擎实现。
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime

from ..interface.base import FinancialAgentInterface
from ..interface.models import EvalDimension, EvalMode, EvalResponse, EvalTask
from ..scoring.engine import ScoringConfig, ScoringEngine
from ..scoring.veto import VetoChecker
from ..taskgen.generator import EvalTaskGenerator, TaskGeneratorConfig


@dataclass
class EngineConfig:
    """引擎配置"""
    eval_mode: EvalMode = EvalMode.FULL
    max_concurrent_tasks: int = 5
    task_timeout_seconds: int = 300
    max_retries: int = 2
    retry_delay_seconds: int = 5
    enable_checkpoint: bool = True
    checkpoint_interval: int = 10


@dataclass
class EngineResult:
    """引擎执行结果"""
    success: bool
    eval_mode: str
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    overall_score: float | None = None
    overall_rating: str | None = None
    veto_triggered: bool = False
    veto_reason: str | None = None
    dimension_scores: dict = field(default_factory=dict)
    duration_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)
    started_at: datetime | None = None
    completed_at: datetime | None = None


class EvaluationEngine:
    """
    评测引擎

    统一管理快速评测和完整评测模式的执行。
    """

    def __init__(
        self,
        agent: FinancialAgentInterface,
        config: EngineConfig | None = None,
        scoring_config: ScoringConfig | None = None,
    ):
        self.agent = agent
        self.config = config or EngineConfig()
        self.scoring_engine = ScoringEngine(scoring_config or ScoringConfig())
        self.veto_checker = VetoChecker()
        self.task_generator = EvalTaskGenerator(TaskGeneratorConfig())

    async def run_quick_eval(
        self,
        agent_config: dict | None = None,
    ) -> EngineResult:
        """运行快速评测（5维度, ~4小时）"""
        self.config.eval_mode = EvalMode.QUICK

        quick_dimensions = [
            EvalDimension.ACCURACY,
            EvalDimension.COMPLETENESS,
            EvalDimension.REASONING,
            EvalDimension.TOOL_USAGE,
            EvalDimension.COMPLIANCE,
        ]

        tasks = self.task_generator.generate_tasks(
            n_tasks=20,
            dimensions=quick_dimensions,
        )

        return await self._execute_evaluation(tasks)

    async def run_full_eval(
        self,
        agent_config: dict | None = None,
    ) -> EngineResult:
        """运行完整评测（11维度, ~12小时）"""
        self.config.eval_mode = EvalMode.FULL

        tasks = self.task_generator.generate_full_mode_tasks()

        return await self._execute_evaluation(tasks)

    async def run_custom_eval(
        self,
        tasks: list[EvalTask],
    ) -> EngineResult:
        """运行自定义评测"""
        return await self._execute_evaluation(tasks)

    async def _execute_evaluation(
        self,
        tasks: list[EvalTask],
    ) -> EngineResult:
        """执行评测流程"""
        started_at = datetime.now()
        result = EngineResult(
            success=False,
            eval_mode=self.config.eval_mode.value,
            total_tasks=len(tasks),
            completed_tasks=0,
            failed_tasks=0,
            started_at=started_at,
        )

        try:
            # 阶段1: 执行Agent任务
            responses = await self._execute_agent_tasks(tasks)

            # 阶段2: 评分
            task_response_pairs = []
            for task, response in zip(tasks, responses, strict=False):
                task_response_pairs.append((task, response, task.reference_answer))

            agent_id = self.agent.get_config().agent_id if hasattr(self.agent, 'get_config') else "unknown"
            eval_score = self.scoring_engine.score_evaluation(
                task_response_pairs, agent_id
            )

            # 阶段3: 否决检查
            for ts in eval_score.task_scores:
                if ts.veto_triggered:
                    result.veto_triggered = True
                    result.veto_reason = ts.veto_reason
                    break

            # 填充结果
            result.completed_tasks = eval_score.passed_tasks + eval_score.veto_count
            result.failed_tasks = eval_score.total_tasks - result.completed_tasks
            result.overall_score = eval_score.overall_score
            result.overall_rating = eval_score.overall_rating.value
            result.dimension_scores = {
                dim.value: score
                for dim, score in eval_score.dimension_averages.items()
            }
            result.success = True

        except Exception as e:
            result.errors.append(str(e))

        finally:
            result.completed_at = datetime.now()
            result.duration_seconds = (result.completed_at - started_at).total_seconds()

        return result

    async def _execute_agent_tasks(
        self,
        tasks: list[EvalTask],
    ) -> list[EvalResponse]:
        """并发执行Agent任务"""
        semaphore = asyncio.Semaphore(self.config.max_concurrent_tasks)
        responses = []

        async def execute_one(task: EvalTask) -> EvalResponse:
            async with semaphore:
                for attempt in range(self.config.max_retries + 1):
                    try:
                        response = await asyncio.wait_for(
                            self.agent.ainvoke(task.query, task.context or {}),
                            timeout=task.timeout_seconds or self.config.task_timeout_seconds,
                        )
                        return response
                    except TimeoutError:
                        if attempt == self.config.max_retries:
                            return EvalResponse(
                                task_id=task.task_id,
                                output="",
                                error=f"任务超时（重试{attempt + 1}次后）",
                            )
                        await asyncio.sleep(self.config.retry_delay_seconds)
                    except Exception as e:
                        if attempt == self.config.max_retries:
                            return EvalResponse(
                                task_id=task.task_id,
                                output="",
                                error=f"执行失败: {str(e)}",
                            )
                        await asyncio.sleep(self.config.retry_delay_seconds)

                return EvalResponse(task_id=task.task_id, output="", error="未知错误")

        coroutines = [execute_one(task) for task in tasks]
        responses = await asyncio.gather(*coroutines, return_exceptions=True)

        final = []
        for i, resp in enumerate(responses):
            if isinstance(resp, Exception):
                final.append(EvalResponse(
                    task_id=tasks[i].task_id,
                    output="",
                    error=str(resp),
                ))
            else:
                final.append(resp)

        return final
