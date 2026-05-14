"""
评测流水线核心实现

基于 LangGraph StateGraph 实现评测流程编排。
支持三阶段评估流水线（FR-007-02）：静态 → 动态 → 信任。
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, TypedDict

from pydantic import BaseModel, Field

from .._compat import StrEnum
from ..interface.base import FinancialAgentInterface
from ..interface.models import (
    AgentConfig,
    EvalDimension,
    EvalMode,
    EvalResponse,
    EvalStatus,
    EvalTask,
    TaskType,
)
from ..scoring.engine import EvaluationScore, ScoringConfig, ScoringEngine, TaskScore
from ..taskgen.generator import EvalTaskGenerator, TaskGeneratorConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 枚举定义
# ---------------------------------------------------------------------------


class PipelineStage(StrEnum):
    """流水线阶段"""

    INIT = "init"
    TASK_GENERATION = "task_generation"
    AGENT_EXECUTION = "agent_execution"
    SCORING = "scoring"
    AGGREGATION = "aggregation"
    REPORTING = "reporting"
    COMPLETED = "completed"
    FAILED = "failed"
    # 三阶段流水线新增
    STATIC_EVAL = "static_eval"
    DYNAMIC_EVAL = "dynamic_eval"
    TRUST_EVAL = "trust_eval"


class EvalPhase(StrEnum):
    """评测阶段（三阶段评估流水线）"""

    STATIC = "static"
    DYNAMIC = "dynamic"
    TRUST = "trust"


# ---------------------------------------------------------------------------
# 阶段 → 维度 / 任务类型映射
# ---------------------------------------------------------------------------

PHASE_DIMENSIONS: dict[EvalPhase, list[EvalDimension]] = {
    EvalPhase.STATIC: [
        EvalDimension.ACCURACY,
        EvalDimension.COMPLETENESS,
        EvalDimension.REASONING,
        EvalDimension.PROFESSIONALISM,
        EvalDimension.TOOL_USAGE,
    ],
    EvalPhase.DYNAMIC: [
        EvalDimension.ROBUSTNESS,
        EvalDimension.REASONING,
    ],
    EvalPhase.TRUST: [
        EvalDimension.COMPLIANCE,
        EvalDimension.SECURITY,
        EvalDimension.RISK_AWARENESS,
        EvalDimension.TRANSPARENCY,
        EvalDimension.CONSISTENCY,
    ],
}

PHASE_TASK_TYPES: dict[EvalPhase, list[TaskType]] = {
    EvalPhase.STATIC: [
        TaskType.KNOWLEDGE_QA,
        TaskType.ANALYSIS,
        TaskType.TOOL_USE,
    ],
    EvalPhase.DYNAMIC: [
        TaskType.TRADING,
        TaskType.ADVERSARIAL,
    ],
    EvalPhase.TRUST: [
        TaskType.TRUSTWORTHINESS,
    ],
}


# ---------------------------------------------------------------------------
# 流水线状态
# ---------------------------------------------------------------------------


class PipelineState(TypedDict):
    """流水线状态"""

    # 基本信息
    pipeline_id: str
    agent_id: str
    eval_mode: str
    status: str
    current_stage: str

    # 任务相关
    tasks: list[dict]
    current_task_index: int
    responses: list[dict]
    task_scores: list[dict]

    # 结果相关
    evaluation_score: dict | None
    report: dict | None

    # 错误处理
    errors: list[dict]
    retry_count: int

    # 元数据
    started_at: str | None
    completed_at: str | None
    metadata: dict

    # 三阶段流水线新增字段
    current_phase: str  # EvalPhase value
    phase_results: dict  # phase -> {tasks, responses, task_scores, evaluation_score}


# ---------------------------------------------------------------------------
# 流水线配置
# ---------------------------------------------------------------------------


class PipelineConfig(BaseModel):
    """流水线配置"""

    # 评测模式
    eval_mode: EvalMode = Field(default=EvalMode.FULL)

    # 并发配置
    max_concurrent_tasks: int = Field(default=5, description="最大并发任务数")
    task_timeout_seconds: int = Field(default=300, description="单个任务超时时间")

    # 重试配置
    max_retries: int = Field(default=3, description="最大重试次数")
    retry_delay_seconds: int = Field(default=5, description="重试延迟")

    # 检查点配置
    enable_checkpoint: bool = Field(default=True, description="是否启用检查点")
    checkpoint_interval: int = Field(default=10, description="检查点间隔（任务数）")

    # 报告配置
    generate_report: bool = Field(default=True, description="是否生成报告")
    report_format: str = Field(default="json", description="报告格式")

    # 快速评测配置
    quick_mode_tasks: int = Field(default=50, description="快速模式任务数")
    quick_mode_dimensions: list[EvalDimension] = Field(
        default_factory=lambda: [
            EvalDimension.ACCURACY,
            EvalDimension.COMPLETENESS,
            EvalDimension.REASONING,
            EvalDimension.TOOL_USAGE,
            EvalDimension.COMPLIANCE,
        ],
        description="快速模式评测维度",
    )

    # 三阶段流水线配置
    enable_three_stage: bool = Field(
        default=True, description="是否启用三阶段评估流水线（FULL 模式默认启用）"
    )


# ---------------------------------------------------------------------------
# 流水线执行结果
# ---------------------------------------------------------------------------


@dataclass
class PipelineResult:
    """流水线执行结果"""

    pipeline_id: str
    agent_id: str
    status: EvalStatus
    evaluation_score: EvaluationScore | None = None
    report: dict | None = None
    errors: list[dict] = field(default_factory=list)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @property
    def duration_seconds(self) -> float | None:
        """执行时长（秒）"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


# ---------------------------------------------------------------------------
# 阶段结果
# ---------------------------------------------------------------------------


@dataclass
class PhaseResult:
    """单个阶段的评估结果"""

    phase: EvalPhase
    tasks: list[EvalTask] = field(default_factory=list)
    responses: list[EvalResponse] = field(default_factory=list)
    task_scores: list[TaskScore] = field(default_factory=list)
    evaluation_score: EvaluationScore | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    errors: list[dict] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float | None:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "phase": self.phase.value,
            "task_count": len(self.tasks),
            "overall_score": self.evaluation_score.overall_score if self.evaluation_score else None,
            "overall_rating": self.evaluation_score.overall_rating.value
            if self.evaluation_score
            else None,
            "dimension_averages": {
                dim.value: score
                for dim, score in (
                    self.evaluation_score.dimension_averages.items()
                    if self.evaluation_score
                    else {}
                )
            },
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "errors": self.errors,
        }


# ---------------------------------------------------------------------------
# EvalPipeline（原始流水线，保持向后兼容）
# ---------------------------------------------------------------------------


class EvalPipeline:
    """评测流水线"""

    def __init__(
        self,
        agent: FinancialAgentInterface,
        config: PipelineConfig | None = None,
        task_generator_config: TaskGeneratorConfig | None = None,
        scoring_config: ScoringConfig | None = None,
    ):
        self.agent = agent
        self.config = config or PipelineConfig()
        self.task_generator = EvalTaskGenerator(task_generator_config or TaskGeneratorConfig())
        self.scoring_engine = ScoringEngine(scoring_config or ScoringConfig())

        self._state: PipelineState | None = None
        self._checkpointer = None

    def _init_state(self, agent_id: str) -> PipelineState:
        """初始化流水线状态"""
        return PipelineState(
            pipeline_id=str(uuid.uuid4()),
            agent_id=agent_id,
            eval_mode=self.config.eval_mode.value,
            status=EvalStatus.PENDING.value,
            current_stage=PipelineStage.INIT.value,
            tasks=[],
            current_task_index=0,
            responses=[],
            task_scores=[],
            evaluation_score=None,
            report=None,
            errors=[],
            retry_count=0,
            started_at=datetime.now().isoformat(),
            completed_at=None,
            metadata={},
            current_phase=EvalPhase.STATIC.value,
            phase_results={},
        )

    async def run(
        self,
        agent_config: AgentConfig | None = None,
        tasks: list[EvalTask] | None = None,
    ) -> PipelineResult:
        """
        运行评测流水线

        Args:
            agent_config: Agent配置
            tasks: 预定义的任务列表（可选，不提供则自动生成）

        Returns:
            流水线执行结果
        """

        # 获取Agent ID
        agent_id = agent_config.agent_name if agent_config else self.agent.get_config().agent_name

        # 初始化状态
        self._state = self._init_state(agent_id)
        result = PipelineResult(
            pipeline_id=self._state["pipeline_id"],
            agent_id=agent_id,
            status=EvalStatus.RUNNING,
            started_at=datetime.now(),
        )

        try:
            # 阶段1: 任务生成
            self._state["current_stage"] = PipelineStage.TASK_GENERATION.value
            if tasks is None:
                tasks = await self._generate_tasks()
            self._state["tasks"] = [self._task_to_dict(t) for t in tasks]

            # 阶段2: Agent执行
            self._state["current_stage"] = PipelineStage.AGENT_EXECUTION.value
            responses = await self._execute_tasks(tasks)
            self._state["responses"] = [self._response_to_dict(r) for r in responses]

            # 阶段3: 评分
            self._state["current_stage"] = PipelineStage.SCORING.value
            task_scores = await self._score_tasks(tasks, responses)
            self._state["task_scores"] = [self._task_score_to_dict(s) for s in task_scores]

            # 阶段4: 聚合
            self._state["current_stage"] = PipelineStage.AGGREGATION.value
            evaluation_score = await self._aggregate_scores(tasks, responses, task_scores)
            self._state["evaluation_score"] = self._eval_score_to_dict(evaluation_score)
            result.evaluation_score = evaluation_score

            # 阶段5: 报告生成
            if self.config.generate_report:
                self._state["current_stage"] = PipelineStage.REPORTING.value
                report = await self._generate_report(evaluation_score)
                self._state["report"] = report
                result.report = report

            # 完成
            self._state["status"] = EvalStatus.COMPLETED.value
            self._state["current_stage"] = PipelineStage.COMPLETED.value
            result.status = EvalStatus.COMPLETED

        except Exception as e:
            self._state["status"] = EvalStatus.FAILED.value
            self._state["current_stage"] = PipelineStage.FAILED.value
            self._state["errors"].append(
                {
                    "stage": self._state["current_stage"],
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }
            )
            result.status = EvalStatus.FAILED
            result.errors = self._state["errors"]

        finally:
            self._state["completed_at"] = datetime.now().isoformat()
            result.completed_at = datetime.now()

        return result

    async def run_quick_mode(
        self,
        agent_config: AgentConfig | None = None,
    ) -> PipelineResult:
        """运行快速评测模式"""

        # 生成快速模式任务
        tasks = self.task_generator.generate_quick_mode_tasks()

        # 临时修改配置
        original_mode = self.config.eval_mode
        self.config.eval_mode = EvalMode.QUICK

        try:
            result = await self.run(agent_config, tasks)
        finally:
            self.config.eval_mode = original_mode

        return result

    async def _generate_tasks(self) -> list[EvalTask]:
        """生成评测任务"""
        if self.config.eval_mode == EvalMode.QUICK:
            return self.task_generator.generate_quick_mode_tasks()
        else:
            return self.task_generator.generate_full_mode_tasks()

    async def _execute_tasks(self, tasks: list[EvalTask]) -> list[EvalResponse]:
        """执行评测任务"""
        responses = []

        # 并发执行
        semaphore = asyncio.Semaphore(self.config.max_concurrent_tasks)

        async def execute_with_semaphore(task: EvalTask) -> EvalResponse:
            async with semaphore:
                return await self._execute_single_task(task)

        # 创建执行任务
        coroutines = [execute_with_semaphore(task) for task in tasks]
        responses = await asyncio.gather(*coroutines, return_exceptions=True)

        # 处理异常
        final_responses = []
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                final_responses.append(
                    EvalResponse(
                        task_id=tasks[i].task_id,
                        output="",
                        error=str(response),
                    )
                )
            else:
                final_responses.append(response)

        return final_responses

    async def _execute_single_task(self, task: EvalTask) -> EvalResponse:
        """执行单个任务"""
        try:
            query = (
                task.input_data.get("query", "")
                if isinstance(task.input_data, dict)
                else str(task.input_data)
            )
            timeout = task.time_limit_seconds or self.config.task_timeout_seconds
            response = await asyncio.wait_for(
                self.agent.ainvoke(query, task.context),
                timeout=timeout,
            )
            return response
        except TimeoutError:
            return EvalResponse(
                task_id=task.task_id,
                output="",
                error=f"任务超时（{task.time_limit_seconds}秒）",
            )
        except Exception as e:
            return EvalResponse(
                task_id=task.task_id,
                output="",
                error=str(e),
            )

    async def _score_tasks(
        self,
        tasks: list[EvalTask],
        responses: list[EvalResponse],
    ) -> list[TaskScore]:
        """对任务进行评分"""
        scores = []

        for task, response in zip(tasks, responses, strict=False):
            reference = (
                task.input_data.get("reference_answer", "")
                if isinstance(task.input_data, dict)
                else None
            )
            score = self.scoring_engine.score_task(task, response, reference)
            scores.append(score)

        return scores

    async def _aggregate_scores(
        self,
        tasks: list[EvalTask],
        responses: list[EvalResponse],
        task_scores: list[TaskScore],
    ) -> EvaluationScore:
        """聚合评分"""

        task_response_pairs = [
            (
                task,
                response,
                task.input_data.get("reference_answer", "")
                if isinstance(task.input_data, dict)
                else None,
            )
            for task, response in zip(tasks, responses, strict=False)
        ]

        return self.scoring_engine.score_evaluation(
            task_response_pairs,
            self._state["agent_id"],
        )

    async def _generate_report(self, evaluation_score: EvaluationScore) -> dict:
        """生成评测报告"""

        report = {
            "pipeline_id": self._state["pipeline_id"],
            "agent_id": self._state["agent_id"],
            "eval_mode": self._state["eval_mode"],
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "overall_score": evaluation_score.overall_score,
                "overall_rating": evaluation_score.overall_rating.value,
                "total_tasks": evaluation_score.total_tasks,
                "passed_tasks": evaluation_score.passed_tasks,
                "pass_rate": evaluation_score.pass_rate,
                "veto_count": evaluation_score.veto_count,
            },
            "dimension_scores": {
                dim.value: score for dim, score in evaluation_score.dimension_averages.items()
            },
            "task_details": [
                {
                    "task_id": ts.task_id,
                    "overall_score": ts.overall_score,
                    "rating": ts.rating.value,
                    "veto_triggered": ts.veto_triggered,
                    "dimension_scores": {
                        ds.dimension.value: ds.score for ds in ts.dimension_scores
                    },
                }
                for ts in evaluation_score.task_scores
            ],
            "recommendations": self._generate_recommendations(evaluation_score),
        }

        return report

    def _generate_recommendations(self, score: EvaluationScore) -> list[str]:
        """生成改进建议"""
        recommendations = []

        # 基于各维度分数生成建议
        for dim, avg_score in score.dimension_averages.items():
            if avg_score < 60:
                recommendations.append(f"{dim.value}维度得分较低（{avg_score:.1f}），建议重点改进")
            elif avg_score < 80:
                recommendations.append(f"{dim.value}维度有提升空间（{avg_score:.1f}）")

        # 基于一票否决生成建议
        if score.veto_count > 0:
            recommendations.append(f"存在{score.veto_count}次一票否决，需重点关注合规性和安全性")

        if not recommendations:
            recommendations.append("整体表现良好，继续保持")

        return recommendations

    def get_state(self) -> PipelineState | None:
        """获取当前状态"""
        return self._state

    async def resume(
        self,
        state: PipelineState | None = None,
        checkpointer: Any = None,
        evaluation_id: str | None = None,
    ) -> PipelineResult:
        """
        从检查点恢复执行。

        支持两种恢复方式：
        1. 直接传入 PipelineState（向后兼容原有签名）
        2. 传入 checkpointer + evaluation_id，自动从数据库加载最新检查点

        恢复逻辑：
        - 根据 current_stage 判断上次执行到哪个阶段
        - 跳过已完成的阶段，从下一个阶段继续执行
        - 合并已有结果与新结果

        Args:
            state: 之前保存的流水线状态（向后兼容）
            checkpointer: ProductionCheckpointer 实例（可选）
            evaluation_id: 评测 ID，用于从 checkpointer 加载状态（可选）

        Returns:
            流水线执行结果
        """
        # 加载恢复状态
        self._state = await self._load_checkpoint(state, checkpointer, evaluation_id)
        self._validate_resume_state()

        current_stage = self._state.get("current_stage", PipelineStage.INIT.value)
        result = self._create_resume_result()

        try:
            # 阶段 1: 任务生成
            if current_stage in (
                PipelineStage.INIT.value,
                PipelineStage.TASK_GENERATION.value,
            ):
                await self._resume_task_generation(checkpointer, evaluation_id)

            # 阶段 2: Agent 执行
            if current_stage in (
                PipelineStage.INIT.value,
                PipelineStage.TASK_GENERATION.value,
                PipelineStage.AGENT_EXECUTION.value,
            ):
                await self._resume_agent_execution(checkpointer, evaluation_id)

            # 阶段 3: 评分
            if current_stage in (
                PipelineStage.INIT.value,
                PipelineStage.TASK_GENERATION.value,
                PipelineStage.AGENT_EXECUTION.value,
                PipelineStage.SCORING.value,
            ):
                await self._resume_scoring(checkpointer, evaluation_id)

            # 阶段 4: 聚合
            if current_stage in (
                PipelineStage.INIT.value,
                PipelineStage.TASK_GENERATION.value,
                PipelineStage.AGENT_EXECUTION.value,
                PipelineStage.SCORING.value,
                PipelineStage.AGGREGATION.value,
            ):
                await self._resume_aggregation(result, checkpointer, evaluation_id)

            # 阶段 5: 报告生成
            if current_stage in (
                PipelineStage.INIT.value,
                PipelineStage.TASK_GENERATION.value,
                PipelineStage.AGENT_EXECUTION.value,
                PipelineStage.SCORING.value,
                PipelineStage.AGGREGATION.value,
                PipelineStage.REPORTING.value,
            ):
                await self._resume_reporting(result)

            # 完成
            self._state["status"] = EvalStatus.COMPLETED.value
            self._state["current_stage"] = PipelineStage.COMPLETED.value
            result.status = EvalStatus.COMPLETED

        except Exception as e:
            self._handle_resume_error(result, e)
            await self._save_checkpoint_if_available(
                checkpointer, evaluation_id, stage=PipelineStage.FAILED.value
            )

        finally:
            self._state["completed_at"] = datetime.now().isoformat()
            result.completed_at = datetime.now()

        return result

    # ------------------------------------------------------------------
    # resume 辅助方法
    # ------------------------------------------------------------------

    async def _load_checkpoint(
        self,
        state: PipelineState | None,
        checkpointer: Any,
        evaluation_id: str | None,
    ) -> PipelineState:
        """从直接传入的 state 或 checkpointer 加载恢复状态。"""
        if state is not None:
            return state

        if checkpointer is not None and evaluation_id is not None:
            resume_info = await checkpointer.get_resume_info(evaluation_id)
            if resume_info is None:
                raise ValueError(f"未找到评测 {evaluation_id} 的检查点，无法恢复")
            saved_state = resume_info["state_data"]
            loaded = PipelineState(
                pipeline_id=saved_state.get("pipeline_id", str(uuid.uuid4())),
                agent_id=saved_state.get("agent_id", ""),
                eval_mode=saved_state.get("eval_mode", "full"),
                status=saved_state.get("status", "running"),
                current_stage=saved_state.get("current_stage", PipelineStage.INIT.value),
                tasks=saved_state.get("tasks", []),
                current_task_index=saved_state.get("current_task_index", 0),
                responses=saved_state.get("responses", []),
                task_scores=saved_state.get("task_scores", []),
                evaluation_score=saved_state.get("evaluation_score"),
                report=saved_state.get("report"),
                errors=saved_state.get("errors", []),
                retry_count=saved_state.get("retry_count", 0),
                started_at=saved_state.get("started_at"),
                completed_at=None,
                metadata=saved_state.get("metadata", {}),
                current_phase=saved_state.get("current_phase", EvalPhase.STATIC.value),
                phase_results=saved_state.get("phase_results", {}),
            )
            logger.info(
                "从检查点恢复: evaluation_id=%s, stage=%s, task_index=%d",
                evaluation_id,
                loaded["current_stage"],
                loaded["current_task_index"],
            )
            return loaded

        raise ValueError("resume() 需要提供 state 参数，或同时提供 checkpointer 和 evaluation_id")

    def _validate_resume_state(self) -> None:
        """验证恢复状态是否有效。"""
        if self._state is None:
            raise ValueError("无法恢复：状态为空")

    def _create_resume_result(self) -> PipelineResult:
        """基于当前状态创建 PipelineResult。"""
        return PipelineResult(
            pipeline_id=self._state["pipeline_id"],
            agent_id=self._state["agent_id"],
            status=EvalStatus.RUNNING,
            started_at=datetime.fromisoformat(self._state["started_at"])
            if self._state.get("started_at")
            else datetime.now(),
        )

    def _handle_resume_error(self, result: PipelineResult, error: Exception) -> None:
        """处理恢复过程中的错误。"""
        self._state["status"] = EvalStatus.FAILED.value
        self._state["current_stage"] = PipelineStage.FAILED.value
        self._state["errors"].append(
            {
                "stage": self._state["current_stage"],
                "error": str(error),
                "timestamp": datetime.now().isoformat(),
            }
        )
        result.status = EvalStatus.FAILED
        result.errors = self._state["errors"]
        logger.error("流水线恢复执行失败: %s", error, exc_info=True)

    async def _resume_task_generation(
        self,
        checkpointer: Any,
        evaluation_id: str | None,
    ) -> None:
        """恢复任务生成阶段。"""
        self._state["current_stage"] = PipelineStage.TASK_GENERATION.value
        if not self._state.get("tasks"):
            tasks = await self._generate_tasks()
            self._state["tasks"] = [self._task_to_dict(t) for t in tasks]
        await self._save_checkpoint_if_available(
            checkpointer, evaluation_id, stage=PipelineStage.TASK_GENERATION.value
        )

    async def _resume_agent_execution(
        self,
        checkpointer: Any,
        evaluation_id: str | None,
    ) -> None:
        """恢复 Agent 执行阶段。"""
        self._state["current_stage"] = PipelineStage.AGENT_EXECUTION.value

        all_tasks = self._dict_to_tasks(self._state["tasks"])
        existing_count = len(self._state.get("responses", []))

        if existing_count < len(all_tasks):
            remaining_tasks = all_tasks[existing_count:]
            remaining_responses = await self._execute_tasks(remaining_tasks)
            self._state["responses"].extend(
                [self._response_to_dict(r) for r in remaining_responses]
            )

        await self._save_checkpoint_if_available(
            checkpointer, evaluation_id, stage=PipelineStage.AGENT_EXECUTION.value
        )

    async def _resume_scoring(
        self,
        checkpointer: Any,
        evaluation_id: str | None,
    ) -> None:
        """恢复评分阶段。"""
        self._state["current_stage"] = PipelineStage.SCORING.value

        if not self._state.get("task_scores"):
            all_tasks = self._dict_to_tasks(self._state["tasks"])
            all_responses = self._dict_to_responses(self._state["responses"])
            task_scores = await self._score_tasks(all_tasks, all_responses)
            self._state["task_scores"] = [self._task_score_to_dict(s) for s in task_scores]

        await self._save_checkpoint_if_available(
            checkpointer, evaluation_id, stage=PipelineStage.SCORING.value
        )

    async def _resume_aggregation(
        self,
        result: PipelineResult,
        checkpointer: Any,
        evaluation_id: str | None,
    ) -> None:
        """恢复聚合阶段。"""
        self._state["current_stage"] = PipelineStage.AGGREGATION.value

        if self._state.get("evaluation_score") is None:
            all_tasks = self._dict_to_tasks(self._state["tasks"])
            all_responses = self._dict_to_responses(self._state["responses"])
            all_task_scores = self._dict_to_task_scores(self._state["task_scores"])
            evaluation_score = await self._aggregate_scores(
                all_tasks, all_responses, all_task_scores
            )
            self._state["evaluation_score"] = self._eval_score_to_dict(evaluation_score)
            result.evaluation_score = evaluation_score

        await self._save_checkpoint_if_available(
            checkpointer, evaluation_id, stage=PipelineStage.AGGREGATION.value
        )

    async def _resume_reporting(self, result: PipelineResult) -> None:
        """恢复报告生成阶段。"""
        if self.config.generate_report:
            self._state["current_stage"] = PipelineStage.REPORTING.value

            if self._state.get("report") is None and result.evaluation_score is not None:
                report = await self._generate_report(result.evaluation_score)
                self._state["report"] = report
                result.report = report

    async def _save_checkpoint_if_available(
        self,
        checkpointer: Any,
        evaluation_id: str | None,
        stage: str,
    ):
        """如果 checkpointer 可用，则保存当前状态作为检查点。"""
        if checkpointer is None or evaluation_id is None or self._state is None:
            return
        try:
            await checkpointer.save_checkpoint(
                evaluation_id=evaluation_id,
                task_index=self._state.get("current_task_index", 0),
                state_data=dict(self._state),
                metadata={"stage": stage},
            )
        except Exception as exc:
            logger.warning("保存检查点失败（不影响流水线执行）: %s", exc)

    # ------------------------------------------------------------------
    # 反序列化辅助方法（用于从检查点恢复数据）
    # ------------------------------------------------------------------

    def _dict_to_tasks(self, task_dicts: list[dict]) -> list[EvalTask]:
        """将字典列表还原为 EvalTask 对象列表。"""
        tasks = []
        for td in task_dicts:
            tasks.append(
                EvalTask(
                    task_id=td.get("task_id", str(uuid.uuid4())),
                    task_type=TaskType(td.get("task_type", "knowledge_qa")),
                    dimension=td.get("dimension", "accuracy"),
                    input_data=td.get("input_data", {"query": td.get("query", "")}),
                    context=td.get("context", {}),
                    time_limit_seconds=td.get("time_limit_seconds")
                    or td.get("timeout_seconds", 300),
                    metadata=td.get("metadata", {}),
                )
            )
        return tasks

    def _dict_to_responses(self, response_dicts: list[dict]) -> list[EvalResponse]:
        """将字典列表还原为 EvalResponse 对象列表。"""
        responses = []
        for rd in response_dicts:
            responses.append(
                EvalResponse(
                    task_id=rd.get("task_id", ""),
                    output=rd.get("output", ""),
                    tool_calls=rd.get("tool_calls", []),
                    error=rd.get("error"),
                )
            )
        return responses

    def _dict_to_task_scores(self, score_dicts: list[dict]) -> list[TaskScore]:
        """将字典列表还原为 TaskScore 对象列表。"""
        from ..scoring.engine import DimensionScore, RatingLevel

        scores = []
        for sd in score_dicts:
            dim_scores = []
            for ds in sd.get("dimension_scores", []):
                dim_scores.append(
                    DimensionScore(
                        dimension=EvalDimension(ds.get("dimension", "accuracy")),
                        score=ds.get("score", 0.0),
                        confidence=ds.get("confidence", 1.0),
                    )
                )
            scores.append(
                TaskScore(
                    task_id=sd.get("task_id", ""),
                    overall_score=sd.get("overall_score", 0.0),
                    rating=RatingLevel(sd.get("rating", "D")),
                    veto_triggered=sd.get("veto_triggered", False),
                    dimension_scores=dim_scores,
                )
            )
        return scores

    # 序列化辅助方法
    def _task_to_dict(self, task: EvalTask) -> dict:
        task_type = task.task_type
        if hasattr(task_type, "value"):
            task_type = task_type.value
        return {
            "task_id": task.task_id,
            "task_type": task_type,
            "query": task.input_data.get("query", "") if isinstance(task.input_data, dict) else "",
            "context": task.context,
            "dimensions": task.input_data.get("dimensions", [])
            if isinstance(task.input_data, dict)
            else [],
            "timeout_seconds": task.time_limit_seconds,
            "dimension": task.dimension,
            "input_data": task.input_data,
            "metadata": task.metadata,
        }

    def _response_to_dict(self, response: EvalResponse) -> dict:
        return {
            "task_id": response.task_id,
            "output": response.output,
            "tool_calls": response.tool_calls,
            "error": response.error,
        }

    def _task_score_to_dict(self, score: TaskScore) -> dict:
        rating = score.rating
        if hasattr(rating, "value"):
            rating = rating.value
        return {
            "task_id": score.task_id,
            "overall_score": score.overall_score,
            "rating": rating,
            "veto_triggered": score.veto_triggered,
            "dimension_scores": [
                {
                    "dimension": ds.dimension.value
                    if hasattr(ds.dimension, "value")
                    else ds.dimension,
                    "score": ds.score,
                    "confidence": ds.confidence,
                }
                for ds in score.dimension_scores
            ],
        }

    def _eval_score_to_dict(self, score: EvaluationScore) -> dict:
        overall_rating = score.overall_rating
        if hasattr(overall_rating, "value"):
            overall_rating = overall_rating.value
        return {
            "agent_id": score.agent_id,
            "overall_score": score.overall_score,
            "overall_rating": overall_rating,
            "total_tasks": score.total_tasks,
            "passed_tasks": score.passed_tasks,
            "veto_count": score.veto_count,
        }


# ---------------------------------------------------------------------------
# ThreeStagePipeline（三阶段评估流水线，FR-007-02）
# ---------------------------------------------------------------------------

# 阶段执行顺序
PHASE_ORDER: list[EvalPhase] = [EvalPhase.STATIC, EvalPhase.DYNAMIC, EvalPhase.TRUST]

# 阶段对应的 PipelineStage
PHASE_STAGE_MAP: dict[EvalPhase, PipelineStage] = {
    EvalPhase.STATIC: PipelineStage.STATIC_EVAL,
    EvalPhase.DYNAMIC: PipelineStage.DYNAMIC_EVAL,
    EvalPhase.TRUST: PipelineStage.TRUST_EVAL,
}


class ThreeStagePipeline:
    """
    三阶段评估流水线（FR-007-02）

    评估流程：
    - FULL 模式：STATIC → DYNAMIC → TRUST，三个阶段顺序执行
    - QUICK 模式：仅执行 STATIC 阶段（向后兼容）

    每个阶段独立生成任务、执行、评分，并支持阶段粒度的检查点/恢复。
    """

    def __init__(
        self,
        agent: FinancialAgentInterface,
        config: PipelineConfig | None = None,
        task_generator_config: TaskGeneratorConfig | None = None,
        scoring_config: ScoringConfig | None = None,
    ):
        self.agent = agent
        self.config = config or PipelineConfig()
        self.task_generator = EvalTaskGenerator(task_generator_config or TaskGeneratorConfig())
        self.scoring_engine = ScoringEngine(scoring_config or ScoringConfig())

        self._state: PipelineState | None = None
        self._phase_results: dict[EvalPhase, PhaseResult] = {}

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    async def run(
        self,
        agent_config: AgentConfig | None = None,
    ) -> PipelineResult:
        """
        运行三阶段评测流水线。

        FULL 模式：STATIC → DYNAMIC → TRUST
        QUICK 模式：仅 STATIC

        Args:
            agent_config: Agent 配置

        Returns:
            流水线执行结果
        """
        agent_id = agent_config.agent_name if agent_config else self.agent.get_config().agent_name

        self._state = self._init_state(agent_id)
        self._phase_results = {}

        result = PipelineResult(
            pipeline_id=self._state["pipeline_id"],
            agent_id=agent_id,
            status=EvalStatus.RUNNING,
            started_at=datetime.now(),
        )

        try:
            # 确定要执行的阶段
            phases_to_run = self._get_phases_to_run()

            for phase in phases_to_run:
                phase_result = await self._run_phase(phase, agent_id)
                self._phase_results[phase] = phase_result
                self._state["phase_results"][phase.value] = phase_result.to_dict()

                # 保存阶段检查点
                logger.info(
                    "阶段 %s 完成: score=%.1f, tasks=%d",
                    phase.value,
                    phase_result.evaluation_score.overall_score
                    if phase_result.evaluation_score
                    else 0.0,
                    len(phase_result.tasks),
                )

            # 聚合所有阶段结果
            evaluation_score = self._aggregate_phase_results()
            self._state["evaluation_score"] = self._eval_score_to_dict(evaluation_score)
            result.evaluation_score = evaluation_score

            # 生成报告
            if self.config.generate_report:
                self._state["current_stage"] = PipelineStage.REPORTING.value
                report = self._generate_three_stage_report(evaluation_score)
                self._state["report"] = report
                result.report = report

            self._state["status"] = EvalStatus.COMPLETED.value
            self._state["current_stage"] = PipelineStage.COMPLETED.value
            result.status = EvalStatus.COMPLETED

        except Exception as e:
            self._state["status"] = EvalStatus.FAILED.value
            self._state["current_stage"] = PipelineStage.FAILED.value
            self._state["errors"].append(
                {
                    "stage": self._state["current_stage"],
                    "phase": self._state.get("current_phase", ""),
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }
            )
            result.status = EvalStatus.FAILED
            result.errors = self._state["errors"]
            logger.error("三阶段流水线执行失败: %s", e, exc_info=True)

        finally:
            self._state["completed_at"] = datetime.now().isoformat()
            result.completed_at = datetime.now()

        return result

    async def resume(
        self,
        state: PipelineState | None = None,
        checkpointer: Any = None,
        evaluation_id: str | None = None,
    ) -> PipelineResult:
        """
        从检查点恢复三阶段流水线执行。

        支持阶段粒度的恢复：跳过已完成的阶段，从下一个未完成的阶段继续。

        Args:
            state: 之前保存的流水线状态
            checkpointer: ProductionCheckpointer 实例（可选）
            evaluation_id: 评测 ID（可选）

        Returns:
            流水线执行结果
        """
        # 加载恢复状态
        self._state = await self._load_checkpoint(state, checkpointer, evaluation_id)
        self._validate_resume_state()

        # 恢复已完成的阶段结果
        self._restore_phase_results()

        # 计算需要从哪个阶段开始恢复
        resume_from_index = self._compute_resume_index()
        phases_to_run = self._get_phases_to_run()

        result = self._create_resume_result()

        try:
            # 执行剩余阶段
            await self._resume_remaining_phases(
                phases_to_run, resume_from_index, checkpointer, evaluation_id
            )

            # 聚合所有阶段结果
            evaluation_score = self._aggregate_phase_results()
            self._state["evaluation_score"] = self._eval_score_to_dict(evaluation_score)
            result.evaluation_score = evaluation_score

            # 生成报告
            await self._resume_three_stage_reporting(result)

            self._state["status"] = EvalStatus.COMPLETED.value
            self._state["current_stage"] = PipelineStage.COMPLETED.value
            result.status = EvalStatus.COMPLETED

        except Exception as e:
            self._handle_resume_error(result, e)
            await self._save_checkpoint_if_available(
                checkpointer, evaluation_id, stage=PipelineStage.FAILED.value
            )

        finally:
            self._state["completed_at"] = datetime.now().isoformat()
            result.completed_at = datetime.now()

        return result

    # ------------------------------------------------------------------
    # resume 辅助方法
    # ------------------------------------------------------------------

    async def _load_checkpoint(
        self,
        state: PipelineState | None,
        checkpointer: Any,
        evaluation_id: str | None,
    ) -> PipelineState:
        """从直接传入的 state 或 checkpointer 加载恢复状态。"""
        if state is not None:
            return state

        if checkpointer is not None and evaluation_id is not None:
            resume_info = await checkpointer.get_resume_info(evaluation_id)
            if resume_info is None:
                raise ValueError(f"未找到评测 {evaluation_id} 的检查点，无法恢复")
            saved_state = resume_info["state_data"]
            loaded = PipelineState(
                pipeline_id=saved_state.get("pipeline_id", str(uuid.uuid4())),
                agent_id=saved_state.get("agent_id", ""),
                eval_mode=saved_state.get("eval_mode", "full"),
                status=saved_state.get("status", "running"),
                current_stage=saved_state.get("current_stage", PipelineStage.INIT.value),
                tasks=saved_state.get("tasks", []),
                current_task_index=saved_state.get("current_task_index", 0),
                responses=saved_state.get("responses", []),
                task_scores=saved_state.get("task_scores", []),
                evaluation_score=saved_state.get("evaluation_score"),
                report=saved_state.get("report"),
                errors=saved_state.get("errors", []),
                retry_count=saved_state.get("retry_count", 0),
                started_at=saved_state.get("started_at"),
                completed_at=None,
                metadata=saved_state.get("metadata", {}),
                current_phase=saved_state.get("current_phase", EvalPhase.STATIC.value),
                phase_results=saved_state.get("phase_results", {}),
            )
            logger.info(
                "三阶段流水线从检查点恢复: evaluation_id=%s, phase=%s, stage=%s",
                evaluation_id,
                loaded["current_phase"],
                loaded["current_stage"],
            )
            return loaded

        raise ValueError("resume() 需要提供 state 参数，或同时提供 checkpointer 和 evaluation_id")

    def _validate_resume_state(self) -> None:
        """验证恢复状态是否有效。"""
        if self._state is None:
            raise ValueError("无法恢复：状态为空")

    def _create_resume_result(self) -> PipelineResult:
        """基于当前状态创建 PipelineResult。"""
        return PipelineResult(
            pipeline_id=self._state["pipeline_id"],
            agent_id=self._state["agent_id"],
            status=EvalStatus.RUNNING,
            started_at=datetime.fromisoformat(self._state["started_at"])
            if self._state.get("started_at")
            else datetime.now(),
        )

    def _handle_resume_error(self, result: PipelineResult, error: Exception) -> None:
        """处理恢复过程中的错误。"""
        self._state["status"] = EvalStatus.FAILED.value
        self._state["current_stage"] = PipelineStage.FAILED.value
        self._state["errors"].append(
            {
                "stage": self._state["current_stage"],
                "phase": self._state.get("current_phase", ""),
                "error": str(error),
                "timestamp": datetime.now().isoformat(),
            }
        )
        result.status = EvalStatus.FAILED
        result.errors = self._state["errors"]
        logger.error("三阶段流水线恢复执行失败: %s", error, exc_info=True)

    def _restore_phase_results(self) -> None:
        """从状态中恢复已完成的阶段结果到 _phase_results。"""
        self._phase_results = {}
        for phase in PHASE_ORDER:
            phase_data = self._state.get("phase_results", {}).get(phase.value)
            if phase_data:
                self._phase_results[phase] = PhaseResult(
                    phase=phase,
                    started_at=datetime.fromisoformat(phase_data["started_at"])
                    if phase_data.get("started_at")
                    else None,
                    completed_at=datetime.fromisoformat(phase_data["completed_at"])
                    if phase_data.get("completed_at")
                    else None,
                )

    def _compute_resume_index(self) -> int:
        """计算需要从哪个阶段索引开始恢复。

        根据 current_phase 和该阶段是否已完成（有 overall_score）来判断。
        """
        completed_phase = self._state.get("current_phase", EvalPhase.STATIC.value)
        phases_to_run = self._get_phases_to_run()

        for i, phase in enumerate(phases_to_run):
            if phase.value == completed_phase:
                phase_data = self._state.get("phase_results", {}).get(phase.value, {})
                if phase_data.get("overall_score") is not None:
                    return i + 1  # 从下一个阶段开始
                else:
                    return i  # 从当前阶段重新开始

        return 0

    async def _resume_remaining_phases(
        self,
        phases_to_run: list[EvalPhase],
        resume_from_index: int,
        checkpointer: Any,
        evaluation_id: str | None,
    ) -> None:
        """执行剩余的评估阶段。"""
        for phase in phases_to_run[resume_from_index:]:
            phase_result = await self._run_phase(phase, self._state["agent_id"])
            self._phase_results[phase] = phase_result
            self._state["phase_results"][phase.value] = phase_result.to_dict()

            # 保存检查点
            await self._save_checkpoint_if_available(
                checkpointer, evaluation_id, stage=PHASE_STAGE_MAP[phase].value
            )

    async def _resume_three_stage_reporting(self, result: PipelineResult) -> None:
        """恢复三阶段流水线的报告生成。"""
        if self.config.generate_report:
            self._state["current_stage"] = PipelineStage.REPORTING.value
            if self._state.get("report") is None:
                report = self._generate_three_stage_report(result.evaluation_score)
                self._state["report"] = report
                result.report = report

    def get_state(self) -> PipelineState | None:
        """获取当前状态"""
        return self._state

    def get_phase_results(self) -> dict[EvalPhase, PhaseResult]:
        """获取各阶段结果"""
        return self._phase_results

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _init_state(self, agent_id: str) -> PipelineState:
        """初始化流水线状态"""
        return PipelineState(
            pipeline_id=str(uuid.uuid4()),
            agent_id=agent_id,
            eval_mode=self.config.eval_mode.value,
            status=EvalStatus.PENDING.value,
            current_stage=PipelineStage.INIT.value,
            tasks=[],
            current_task_index=0,
            responses=[],
            task_scores=[],
            evaluation_score=None,
            report=None,
            errors=[],
            retry_count=0,
            started_at=datetime.now().isoformat(),
            completed_at=None,
            metadata={},
            current_phase=EvalPhase.STATIC.value,
            phase_results={},
        )

    def _get_phases_to_run(self) -> list[EvalPhase]:
        """根据评测模式确定要执行的阶段"""
        if self.config.eval_mode == EvalMode.QUICK:
            return [EvalPhase.STATIC]
        return list(PHASE_ORDER)

    async def _run_phase(self, phase: EvalPhase, agent_id: str) -> PhaseResult:
        """
        执行单个评估阶段。

        每个阶段独立完成：任务生成 → Agent执行 → 评分 → 聚合。
        """
        phase_result = PhaseResult(phase=phase, started_at=datetime.now())

        stage = PHASE_STAGE_MAP[phase]
        self._state["current_stage"] = stage.value
        self._state["current_phase"] = phase.value

        logger.info("开始执行阶段: %s", phase.value)

        try:
            # 1. 生成阶段任务
            tasks = self.task_generator.generate_phase_tasks(phase)
            phase_result.tasks = tasks

            if not tasks:
                logger.warning("阶段 %s 没有生成任何任务，跳过", phase.value)
                phase_result.completed_at = datetime.now()
                return phase_result

            # 2. 执行任务
            responses = await self._execute_tasks(tasks)
            phase_result.responses = responses

            # 3. 评分
            task_scores = await self._score_tasks(tasks, responses)
            phase_result.task_scores = task_scores

            # 4. 聚合阶段评分
            evaluation_score = self._aggregate_phase_score(tasks, responses, task_scores, agent_id)
            phase_result.evaluation_score = evaluation_score

            # 合并到全局状态
            self._state["tasks"].extend([self._task_to_dict(t) for t in tasks])
            self._state["responses"].extend([self._response_to_dict(r) for r in responses])
            self._state["task_scores"].extend([self._task_score_to_dict(s) for s in task_scores])

        except Exception as e:
            phase_result.errors.append(
                {
                    "phase": phase.value,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }
            )
            logger.error("阶段 %s 执行失败: %s", phase.value, e, exc_info=True)
            raise

        finally:
            phase_result.completed_at = datetime.now()

        return phase_result

    async def _execute_tasks(self, tasks: list[EvalTask]) -> list[EvalResponse]:
        """执行评测任务（并发控制）"""
        semaphore = asyncio.Semaphore(self.config.max_concurrent_tasks)

        async def execute_with_semaphore(task: EvalTask) -> EvalResponse:
            async with semaphore:
                return await self._execute_single_task(task)

        coroutines = [execute_with_semaphore(task) for task in tasks]
        responses = await asyncio.gather(*coroutines, return_exceptions=True)

        final_responses = []
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                final_responses.append(
                    EvalResponse(
                        task_id=tasks[i].task_id,
                        output="",
                        error=str(response),
                    )
                )
            else:
                final_responses.append(response)

        return final_responses

    async def _execute_single_task(self, task: EvalTask) -> EvalResponse:
        """执行单个任务"""
        try:
            query = (
                task.input_data.get("query", "")
                if isinstance(task.input_data, dict)
                else str(task.input_data)
            )
            timeout = task.time_limit_seconds or self.config.task_timeout_seconds
            response = await asyncio.wait_for(
                self.agent.ainvoke(query, task.context),
                timeout=timeout,
            )
            return response
        except TimeoutError:
            return EvalResponse(
                task_id=task.task_id,
                output="",
                error=f"任务超时（{task.time_limit_seconds}秒）",
            )
        except Exception as e:
            return EvalResponse(
                task_id=task.task_id,
                output="",
                error=str(e),
            )

    async def _score_tasks(
        self,
        tasks: list[EvalTask],
        responses: list[EvalResponse],
    ) -> list[TaskScore]:
        """对任务进行评分"""
        scores = []
        for task, response in zip(tasks, responses, strict=False):
            reference = (
                task.input_data.get("reference_answer", "")
                if isinstance(task.input_data, dict)
                else None
            )
            score = self.scoring_engine.score_task(task, response, reference)
            scores.append(score)
        return scores

    def _aggregate_phase_score(
        self,
        tasks: list[EvalTask],
        responses: list[EvalResponse],
        task_scores: list[TaskScore],
        agent_id: str,
    ) -> EvaluationScore:
        """聚合单个阶段的评分"""
        task_response_pairs = [
            (
                task,
                response,
                task.input_data.get("reference_answer", "")
                if isinstance(task.input_data, dict)
                else None,
            )
            for task, response in zip(tasks, responses, strict=False)
        ]
        return self.scoring_engine.score_evaluation(task_response_pairs, agent_id)

    def _aggregate_phase_results(self) -> EvaluationScore:
        """
        聚合所有阶段的评分结果为最终 EvaluationScore。

        合并所有阶段的 task_scores，重新计算维度平均和总分。
        """
        all_task_scores: list[TaskScore] = []
        for phase in PHASE_ORDER:
            phase_result = self._phase_results.get(phase)
            if phase_result and phase_result.task_scores:
                all_task_scores.extend(phase_result.task_scores)

        if not all_task_scores:
            # 无任务时返回零分
            return EvaluationScore(
                agent_id=self._state["agent_id"],
                task_scores=[],
                dimension_averages={},
                overall_score=0.0,
                overall_rating=self.scoring_engine.rater.rate(0.0),
                total_tasks=0,
                passed_tasks=0,
                veto_count=0,
            )

        # 收集维度分数
        import statistics

        dimension_scores_map: dict[EvalDimension, list[float]] = {dim: [] for dim in EvalDimension}
        for ts in all_task_scores:
            for ds in ts.dimension_scores:
                dimension_scores_map[ds.dimension].append(ds.score)

        dimension_averages = {}
        for dim, scores in dimension_scores_map.items():
            if scores:
                dimension_averages[dim] = statistics.mean(scores)

        overall_scores = [ts.overall_score for ts in all_task_scores]
        overall_score = statistics.mean(overall_scores) if overall_scores else 0.0
        overall_rating = self.scoring_engine.rater.rate(overall_score)

        total_tasks = len(all_task_scores)
        passed_tasks = sum(
            1
            for ts in all_task_scores
            if ts.overall_score >= self.scoring_engine.config.pass_threshold
            and not ts.veto_triggered
        )
        veto_count = sum(1 for ts in all_task_scores if ts.veto_triggered)

        return EvaluationScore(
            agent_id=self._state["agent_id"],
            task_scores=all_task_scores,
            dimension_averages=dimension_averages,
            overall_score=overall_score,
            overall_rating=overall_rating,
            total_tasks=total_tasks,
            passed_tasks=passed_tasks,
            veto_count=veto_count,
        )

    def _generate_three_stage_report(self, evaluation_score: EvaluationScore) -> dict:
        """生成三阶段评测报告，包含各阶段的独立分析"""
        report = {
            "pipeline_id": self._state["pipeline_id"],
            "agent_id": self._state["agent_id"],
            "eval_mode": self._state["eval_mode"],
            "pipeline_type": "three_stage",
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "overall_score": evaluation_score.overall_score,
                "overall_rating": evaluation_score.overall_rating.value,
                "total_tasks": evaluation_score.total_tasks,
                "passed_tasks": evaluation_score.passed_tasks,
                "pass_rate": evaluation_score.pass_rate,
                "veto_count": evaluation_score.veto_count,
            },
            "dimension_scores": {
                dim.value: score for dim, score in evaluation_score.dimension_averages.items()
            },
            # 三阶段独立报告
            "phases": {},
        }

        # 各阶段详情
        for phase in PHASE_ORDER:
            phase_result = self._phase_results.get(phase)
            if phase_result:
                phase_section: dict[str, Any] = {
                    "phase": phase.value,
                    "task_count": len(phase_result.tasks),
                    "duration_seconds": phase_result.duration_seconds,
                }
                if phase_result.evaluation_score:
                    es = phase_result.evaluation_score
                    phase_section["score"] = {
                        "overall_score": es.overall_score,
                        "overall_rating": es.overall_rating.value,
                        "passed_tasks": es.passed_tasks,
                        "veto_count": es.veto_count,
                        "dimension_averages": {
                            dim.value: score for dim, score in es.dimension_averages.items()
                        },
                    }
                    phase_section["recommendations"] = self._generate_phase_recommendations(
                        phase, es
                    )
                if phase_result.errors:
                    phase_section["errors"] = phase_result.errors
                report["phases"][phase.value] = phase_section

        # 总体建议
        report["recommendations"] = self._generate_recommendations(evaluation_score)

        return report

    def _generate_phase_recommendations(
        self, phase: EvalPhase, score: EvaluationScore
    ) -> list[str]:
        """为单个阶段生成改进建议"""
        recommendations = []
        phase_dimensions = PHASE_DIMENSIONS.get(phase, [])

        for dim, avg_score in score.dimension_averages.items():
            if dim not in phase_dimensions:
                continue
            if avg_score < 60:
                recommendations.append(
                    f"{phase.value}阶段 {dim.value} 维度得分较低（{avg_score:.1f}），建议重点改进"
                )
            elif avg_score < 80:
                recommendations.append(
                    f"{phase.value}阶段 {dim.value} 维度有提升空间（{avg_score:.1f}）"
                )

        if score.veto_count > 0:
            phase_label = {
                EvalPhase.STATIC: "静态",
                EvalPhase.DYNAMIC: "动态",
                EvalPhase.TRUST: "信任",
            }.get(phase, phase.value)
            recommendations.append(f"{phase_label}阶段存在{score.veto_count}次一票否决，需重点关注")

        if not recommendations:
            recommendations.append(f"{phase.value}阶段表现良好")

        return recommendations

    def _generate_recommendations(self, score: EvaluationScore) -> list[str]:
        """生成总体改进建议"""
        recommendations = []

        for dim, avg_score in score.dimension_averages.items():
            if avg_score < 60:
                recommendations.append(f"{dim.value}维度得分较低（{avg_score:.1f}），建议重点改进")
            elif avg_score < 80:
                recommendations.append(f"{dim.value}维度有提升空间（{avg_score:.1f}）")

        if score.veto_count > 0:
            recommendations.append(f"存在{score.veto_count}次一票否决，需重点关注合规性和安全性")

        if not recommendations:
            recommendations.append("整体表现良好，继续保持")

        return recommendations

    async def _save_checkpoint_if_available(
        self,
        checkpointer: Any,
        evaluation_id: str | None,
        stage: str,
    ):
        """如果 checkpointer 可用，则保存当前状态作为检查点。"""
        if checkpointer is None or evaluation_id is None or self._state is None:
            return
        try:
            await checkpointer.save_checkpoint(
                evaluation_id=evaluation_id,
                task_index=self._state.get("current_task_index", 0),
                state_data=dict(self._state),
                metadata={"stage": stage, "pipeline_type": "three_stage"},
            )
        except Exception as exc:
            logger.warning("保存检查点失败（不影响流水线执行）: %s", exc)

    # ------------------------------------------------------------------
    # 序列化 / 反序列化辅助方法（与 EvalPipeline 一致）
    # ------------------------------------------------------------------

    def _task_to_dict(self, task: EvalTask) -> dict:
        task_type = task.task_type
        if hasattr(task_type, "value"):
            task_type = task_type.value
        return {
            "task_id": task.task_id,
            "task_type": task_type,
            "query": task.input_data.get("query", "") if isinstance(task.input_data, dict) else "",
            "context": task.context,
            "dimensions": task.input_data.get("dimensions", [])
            if isinstance(task.input_data, dict)
            else [],
            "timeout_seconds": task.time_limit_seconds,
            "dimension": task.dimension,
            "input_data": task.input_data,
            "metadata": task.metadata,
        }

    def _response_to_dict(self, response: EvalResponse) -> dict:
        return {
            "task_id": response.task_id,
            "output": response.output,
            "tool_calls": response.tool_calls,
            "error": response.error,
        }

    def _task_score_to_dict(self, score: TaskScore) -> dict:
        rating = score.rating
        if hasattr(rating, "value"):
            rating = rating.value
        return {
            "task_id": score.task_id,
            "overall_score": score.overall_score,
            "rating": rating,
            "veto_triggered": score.veto_triggered,
            "dimension_scores": [
                {
                    "dimension": ds.dimension.value
                    if hasattr(ds.dimension, "value")
                    else ds.dimension,
                    "score": ds.score,
                    "confidence": ds.confidence,
                }
                for ds in score.dimension_scores
            ],
        }

    def _eval_score_to_dict(self, score: EvaluationScore) -> dict:
        overall_rating = score.overall_rating
        if hasattr(overall_rating, "value"):
            overall_rating = overall_rating.value
        return {
            "agent_id": score.agent_id,
            "overall_score": score.overall_score,
            "overall_rating": overall_rating,
            "total_tasks": score.total_tasks,
            "passed_tasks": score.passed_tasks,
            "veto_count": score.veto_count,
        }
