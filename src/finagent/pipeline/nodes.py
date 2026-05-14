"""
流水线节点模块

实现评测流水线的各个处理节点。
"""

import asyncio
from abc import ABC, abstractmethod

from ..interface.base import FinancialAgentInterface
from ..interface.models import EvalResponse, EvalTask
from ..scoring.engine import ScoringEngine
from ..taskgen.generator import EvalTaskGenerator
from .pipeline import PipelineStage, PipelineState


class BaseNode(ABC):
    """节点基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """节点名称"""
        pass

    @abstractmethod
    async def execute(self, state: PipelineState) -> PipelineState:
        """执行节点逻辑"""
        pass

    def update_stage(self, state: PipelineState, stage: PipelineStage) -> PipelineState:
        """更新流水线阶段"""
        state["current_stage"] = stage.value
        return state


class TaskGeneratorNode(BaseNode):
    """任务生成节点"""

    def __init__(self, task_generator: EvalTaskGenerator):
        self.task_generator = task_generator

    @property
    def name(self) -> str:
        return "task_generator"

    async def execute(self, state: PipelineState) -> PipelineState:
        """生成评测任务"""
        state = self.update_stage(state, PipelineStage.TASK_GENERATION)

        # 根据评测模式生成任务
        from ..interface.models import EvalMode

        eval_mode = EvalMode(state.get("eval_mode", "full"))

        if eval_mode == EvalMode.QUICK:
            tasks = self.task_generator.generate_quick_mode_tasks()
        else:
            tasks = self.task_generator.generate_full_mode_tasks()

        # 序列化任务
        state["tasks"] = [
            {
                "task_id": t.task_id,
                "task_type": t.task_type.value,
                "query": t.query,
                "context": t.context,
                "dimensions": [d.value for d in t.dimensions],
                "timeout_seconds": t.timeout_seconds,
                "reference_answer": t.reference_answer,
            }
            for t in tasks
        ]

        return state


class AgentExecutorNode(BaseNode):
    """Agent执行节点"""

    def __init__(
        self,
        agent: FinancialAgentInterface,
        max_concurrent: int = 5,
        timeout_seconds: int = 300,
    ):
        self.agent = agent
        self.max_concurrent = max_concurrent
        self.timeout_seconds = timeout_seconds

    @property
    def name(self) -> str:
        return "agent_executor"

    async def execute(self, state: PipelineState) -> PipelineState:
        """执行Agent任务"""
        state = self.update_stage(state, PipelineStage.AGENT_EXECUTION)

        tasks_data = state.get("tasks", [])
        responses = []

        # 并发执行控制
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def execute_task(task_data: dict) -> dict:
            async with semaphore:
                try:
                    timeout = task_data.get("timeout_seconds", self.timeout_seconds)
                    response = await asyncio.wait_for(
                        self.agent.ainvoke(
                            task_data["query"],
                            task_data.get("context", {}),
                        ),
                        timeout=timeout,
                    )
                    return {
                        "task_id": task_data["task_id"],
                        "output": response.output,
                        "tool_calls": response.tool_calls,
                        "error": response.error,
                    }
                except TimeoutError:
                    return {
                        "task_id": task_data["task_id"],
                        "output": "",
                        "error": f"任务超时（{timeout}秒）",
                    }
                except Exception as e:
                    return {
                        "task_id": task_data["task_id"],
                        "output": "",
                        "error": str(e),
                    }

        # 并发执行所有任务
        coroutines = [execute_task(task) for task in tasks_data]
        responses = await asyncio.gather(*coroutines)

        state["responses"] = list(responses)
        return state


class ScorerNode(BaseNode):
    """评分节点"""

    def __init__(self, scoring_engine: ScoringEngine):
        self.scoring_engine = scoring_engine

    @property
    def name(self) -> str:
        return "scorer"

    async def execute(self, state: PipelineState) -> PipelineState:
        """对任务进行评分"""
        state = self.update_stage(state, PipelineStage.SCORING)

        tasks_data = state.get("tasks", [])
        responses_data = state.get("responses", [])

        task_scores = []

        for task_data, response_data in zip(tasks_data, responses_data, strict=False):
            # 重建任务对象
            from ..interface.models import EvalDimension, TaskType

            task = EvalTask(
                task_id=task_data["task_id"],
                task_type=TaskType(task_data["task_type"]),
                query=task_data["query"],
                context=task_data.get("context", {}),
                dimensions=[EvalDimension(d) for d in task_data.get("dimensions", [])],
                timeout_seconds=task_data.get("timeout_seconds", 120),
                reference_answer=task_data.get("reference_answer", ""),
            )

            # 重建响应对象
            response = EvalResponse(
                task_id=response_data["task_id"],
                output=response_data.get("output", ""),
                tool_calls=response_data.get("tool_calls"),
                error=response_data.get("error"),
            )

            # 评分
            score = self.scoring_engine.score_task(task, response, task.reference_answer)

            # 序列化评分
            task_scores.append(
                {
                    "task_id": score.task_id,
                    "overall_score": score.overall_score,
                    "rating": score.rating.value,
                    "veto_triggered": score.veto_triggered,
                    "veto_reason": score.veto_reason,
                    "dimension_scores": [
                        {
                            "dimension": ds.dimension.value,
                            "score": ds.score,
                            "confidence": ds.confidence,
                            "evidence": ds.evidence,
                            "reasoning": ds.reasoning,
                        }
                        for ds in score.dimension_scores
                    ],
                }
            )

        state["task_scores"] = task_scores
        return state


class AggregatorNode(BaseNode):
    """聚合节点"""

    def __init__(self, scoring_engine: ScoringEngine):
        self.scoring_engine = scoring_engine

    @property
    def name(self) -> str:
        return "aggregator"

    async def execute(self, state: PipelineState) -> PipelineState:
        """聚合评分结果"""
        state = self.update_stage(state, PipelineStage.AGGREGATION)

        task_scores_data = state.get("task_scores", [])
        agent_id = state.get("agent_id", "unknown")

        # 计算各维度平均分
        import statistics

        from ..scoring.engine import RatingLevel

        dimension_scores: dict[str, list[float]] = {}
        overall_scores = []
        passed_count = 0
        veto_count = 0

        for ts in task_scores_data:
            overall_scores.append(ts["overall_score"])

            if ts["overall_score"] >= 60 and not ts["veto_triggered"]:
                passed_count += 1

            if ts["veto_triggered"]:
                veto_count += 1

            for ds in ts["dimension_scores"]:
                dim = ds["dimension"]
                if dim not in dimension_scores:
                    dimension_scores[dim] = []
                dimension_scores[dim].append(ds["score"])

        # 计算平均值
        dimension_averages = {
            dim: statistics.mean(scores) if scores else 0.0
            for dim, scores in dimension_scores.items()
        }

        overall_score = statistics.mean(overall_scores) if overall_scores else 0.0

        # 确定评级
        if overall_score >= 95:
            rating = RatingLevel.S.value
        elif overall_score >= 85:
            rating = RatingLevel.A.value
        elif overall_score >= 70:
            rating = RatingLevel.B.value
        elif overall_score >= 60:
            rating = RatingLevel.C.value
        else:
            rating = RatingLevel.D.value

        state["evaluation_score"] = {
            "agent_id": agent_id,
            "overall_score": overall_score,
            "overall_rating": rating,
            "dimension_averages": dimension_averages,
            "total_tasks": len(task_scores_data),
            "passed_tasks": passed_count,
            "veto_count": veto_count,
        }

        return state


class ReporterNode(BaseNode):
    """报告生成节点"""

    @property
    def name(self) -> str:
        return "reporter"

    async def execute(self, state: PipelineState) -> PipelineState:
        """生成评测报告"""
        state = self.update_stage(state, PipelineStage.REPORTING)

        evaluation_score = state.get("evaluation_score", {})
        task_scores = state.get("task_scores", [])

        # 生成建议
        recommendations = []
        for dim, score in evaluation_score.get("dimension_averages", {}).items():
            if score < 60:
                recommendations.append(f"{dim}维度得分较低（{score:.1f}），建议重点改进")
            elif score < 80:
                recommendations.append(f"{dim}维度有提升空间（{score:.1f}）")

        if evaluation_score.get("veto_count", 0) > 0:
            recommendations.append(
                f"存在{evaluation_score['veto_count']}次一票否决，需重点关注合规性和安全性"
            )

        if not recommendations:
            recommendations.append("整体表现良好，继续保持")

        # 构建报告
        report = {
            "pipeline_id": state["pipeline_id"],
            "agent_id": state["agent_id"],
            "eval_mode": state["eval_mode"],
            "generated_at": state.get("completed_at"),
            "summary": {
                "overall_score": evaluation_score.get("overall_score", 0),
                "overall_rating": evaluation_score.get("overall_rating", "D"),
                "total_tasks": evaluation_score.get("total_tasks", 0),
                "passed_tasks": evaluation_score.get("passed_tasks", 0),
                "pass_rate": (
                    evaluation_score.get("passed_tasks", 0)
                    / max(evaluation_score.get("total_tasks", 1), 1)
                ),
                "veto_count": evaluation_score.get("veto_count", 0),
            },
            "dimension_scores": evaluation_score.get("dimension_averages", {}),
            "task_details": [
                {
                    "task_id": ts["task_id"],
                    "overall_score": ts["overall_score"],
                    "rating": ts["rating"],
                    "veto_triggered": ts["veto_triggered"],
                    "dimension_scores": {
                        ds["dimension"]: ds["score"] for ds in ts["dimension_scores"]
                    },
                }
                for ts in task_scores
            ],
            "recommendations": recommendations,
        }

        state["report"] = report
        return state
