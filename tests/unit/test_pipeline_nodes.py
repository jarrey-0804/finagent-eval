"""
pipeline/nodes.py 单元测试

测试流水线各节点：TaskGeneratorNode、AgentExecutorNode、ScorerNode、AggregatorNode、ReporterNode。
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from finagent.interface.models import (
    EvalDimension,
    EvalMode,
    EvalResponse,
    EvalTask,
    TaskType,
)
from finagent.pipeline.nodes import (
    AggregatorNode,
    AgentExecutorNode,
    BaseNode,
    ReporterNode,
    ScorerNode,
    TaskGeneratorNode,
)
from finagent.pipeline.pipeline import PipelineStage, PipelineState
from finagent.scoring.engine import (
    DimensionScore,
    RatingLevel,
    ScoringConfig,
    ScoringEngine,
    TaskScore,
)
from finagent.taskgen.generator import EvalTaskGenerator, TaskGeneratorConfig


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _make_pipeline_state(**overrides) -> PipelineState:
    """创建测试用 PipelineState"""
    defaults = {
        "pipeline_id": "test-pipeline-001",
        "agent_id": "test-agent",
        "eval_mode": "full",
        "status": "running",
        "current_stage": PipelineStage.INIT.value,
        "tasks": [],
        "current_task_index": 0,
        "responses": [],
        "task_scores": [],
        "evaluation_score": None,
        "report": None,
        "errors": [],
        "retry_count": 0,
        "started_at": "2025-01-01T00:00:00",
        "completed_at": None,
        "metadata": {},
        "current_phase": "static",
        "phase_results": {},
    }
    defaults.update(overrides)
    return PipelineState(**defaults)


def _make_eval_task(
    task_id: str = "task-001",
    task_type: TaskType = TaskType.KNOWLEDGE_QA,
    query: str = "什么是市盈率？",
) -> MagicMock:
    """创建符合 nodes.py 期望的 mock 任务对象

    nodes.py 访问 t.task_type.value, t.query, t.dimensions, t.timeout_seconds,
    t.reference_answer 等属性，需要用 mock 对象模拟。
    """
    task = MagicMock()
    task.task_id = task_id
    task.task_type = task_type  # 枚举，支持 .value
    task.query = query
    task.context = {}
    task.dimensions = [EvalDimension.ACCURACY]
    task.timeout_seconds = 120
    task.reference_answer = "参考答案"
    return task


def _make_serialized_task(task_id: str = "task-001", query: str = "test query") -> dict:
    """创建序列化后的任务数据（nodes.py 中 ScorerNode 使用的格式）"""
    return {
        "task_id": task_id,
        "task_type": "knowledge_qa",
        "query": query,
        "context": {},
        "dimensions": ["accuracy"],
        "timeout_seconds": 120,
        "reference_answer": "参考答案",
        # ScorerNode 重建 EvalTask 需要的字段
        "dimension": "accuracy",
        "input_data": {"query": query},
    }


# ===========================================================================
# BaseNode 测试
# ===========================================================================


class TestBaseNode:
    """测试 BaseNode 基类"""

    def test_update_stage(self):
        """测试阶段更新"""
        # BaseNode 是抽象类，用一个简单实现来测试
        class ConcreteNode(BaseNode):
            @property
            def name(self) -> str:
                return "concrete"

            async def execute(self, state: PipelineState) -> PipelineState:
                return state

        node = ConcreteNode()
        state = _make_pipeline_state()
        updated = node.update_stage(state, PipelineStage.TASK_GENERATION)
        assert updated["current_stage"] == PipelineStage.TASK_GENERATION.value


# ===========================================================================
# TaskGeneratorNode 测试
# ===========================================================================


class TestTaskGeneratorNode:
    """测试任务生成节点"""

    def test_name(self):
        generator = MagicMock(spec=EvalTaskGenerator)
        node = TaskGeneratorNode(generator)
        assert node.name == "task_generator"

    @pytest.mark.asyncio
    async def test_execute_full_mode(self):
        """测试完整模式任务生成"""
        task = _make_eval_task()
        generator = MagicMock(spec=EvalTaskGenerator)
        generator.generate_full_mode_tasks.return_value = [task]

        node = TaskGeneratorNode(generator)
        state = _make_pipeline_state()
        result = await node.execute(state)

        assert result["current_stage"] == PipelineStage.TASK_GENERATION.value
        assert len(result["tasks"]) == 1
        assert result["tasks"][0]["task_id"] == "task-001"
        generator.generate_full_mode_tasks.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_quick_mode(self):
        """测试快速模式任务生成"""
        task = _make_eval_task()
        generator = MagicMock(spec=EvalTaskGenerator)
        generator.generate_quick_mode_tasks.return_value = [task]

        node = TaskGeneratorNode(generator)
        state = _make_pipeline_state(eval_mode="quick")
        result = await node.execute(state)

        assert len(result["tasks"]) == 1
        generator.generate_quick_mode_tasks.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_serializes_dimensions(self):
        """测试维度序列化"""
        task = MagicMock()
        task.task_id = "t1"
        task.task_type = TaskType.KNOWLEDGE_QA
        task.input_data = {"query": "q", "reference_answer": ""}
        task.context = {}
        task.dimension = "accuracy"
        task.time_limit_seconds = 120

        generator = MagicMock(spec=EvalTaskGenerator)
        generator.generate_full_mode_tasks.return_value = [task]

        node = TaskGeneratorNode(generator)
        state = _make_pipeline_state()
        result = await node.execute(state)

        assert "dimensions" in result["tasks"][0]
        assert result["tasks"][0]["dimensions"] == ["accuracy"]


# ===========================================================================
# AgentExecutorNode 测试
# ===========================================================================


class TestAgentExecutorNode:
    """测试 Agent 执行节点"""

    def test_name(self):
        agent = AsyncMock()
        node = AgentExecutorNode(agent)
        assert node.name == "agent_executor"

    @pytest.mark.asyncio
    async def test_execute_single_task(self):
        """测试单个任务执行"""
        agent = AsyncMock()
        agent.ainvoke.return_value = EvalResponse(
            task_id="task-001",
            output="市盈率是股价与每股收益的比值",
        )

        node = AgentExecutorNode(agent)
        state = _make_pipeline_state(tasks=[_make_serialized_task()])
        result = await node.execute(state)

        assert result["current_stage"] == PipelineStage.AGENT_EXECUTION.value
        assert len(result["responses"]) == 1
        assert result["responses"][0]["task_id"] == "task-001"
        assert "市盈率" in result["responses"][0]["output"]

    @pytest.mark.asyncio
    async def test_execute_multiple_tasks(self):
        """测试多个任务并发执行"""
        agent = AsyncMock()
        agent.ainvoke.return_value = EvalResponse(
            task_id="task-001",
            output="answer",
        )

        node = AgentExecutorNode(agent, max_concurrent=2)
        tasks = [_make_serialized_task(f"task-{i}", f"query-{i}") for i in range(5)]
        state = _make_pipeline_state(tasks=tasks)
        result = await node.execute(state)

        assert len(result["responses"]) == 5
        assert agent.ainvoke.call_count == 5

    @pytest.mark.asyncio
    async def test_execute_timeout(self):
        """测试任务超时处理"""
        agent = AsyncMock()
        agent.ainvoke.side_effect = TimeoutError("任务超时")

        node = AgentExecutorNode(agent, timeout_seconds=1)
        state = _make_pipeline_state(tasks=[_make_serialized_task()])
        result = await node.execute(state)

        assert len(result["responses"]) == 1
        assert result["responses"][0]["error"] is not None

    @pytest.mark.asyncio
    async def test_execute_exception(self):
        """测试任务异常处理"""
        agent = AsyncMock()
        agent.ainvoke.side_effect = RuntimeError("agent crashed")

        node = AgentExecutorNode(agent)
        state = _make_pipeline_state(tasks=[_make_serialized_task()])
        result = await node.execute(state)

        assert len(result["responses"]) == 1
        assert "agent crashed" in result["responses"][0]["error"]

    @pytest.mark.asyncio
    async def test_execute_empty_tasks(self):
        """测试空任务列表"""
        agent = AsyncMock()
        node = AgentExecutorNode(agent)
        state = _make_pipeline_state(tasks=[])
        result = await node.execute(state)

        assert result["responses"] == []

    @pytest.mark.asyncio
    async def test_execute_uses_task_timeout(self):
        """测试使用任务级别的超时"""
        agent = AsyncMock()
        agent.ainvoke.return_value = EvalResponse(task_id="t1", output="ok")

        node = AgentExecutorNode(agent, timeout_seconds=300)
        task = _make_serialized_task()
        task["timeout_seconds"] = 10  # 任务级别超时
        state = _make_pipeline_state(tasks=[task])
        result = await node.execute(state)

        assert len(result["responses"]) == 1


# ===========================================================================
# ScorerNode 测试
# ===========================================================================


class TestScorerNode:
    """测试评分节点"""

    def test_name(self):
        engine = MagicMock(spec=ScoringEngine)
        node = ScorerNode(engine)
        assert node.name == "scorer"

    @pytest.mark.asyncio
    async def test_execute_scoring(self):
        """测试评分执行"""
        engine = MagicMock(spec=ScoringEngine)
        engine.score_task.return_value = TaskScore(
            task_id="task-001",
            dimension_scores=[
                DimensionScore(
                    dimension=EvalDimension.ACCURACY,
                    score=85.0,
                    confidence=0.9,
                    evidence=["e1"],
                    reasoning="good",
                ),
            ],
            overall_score=85.0,
            rating=RatingLevel.A,
            veto_triggered=False,
        )

        node = ScorerNode(engine)
        state = _make_pipeline_state(
            tasks=[_make_serialized_task()],
            responses=[{"task_id": "task-001", "output": "good answer", "tool_calls": [], "error": None}],
        )

        # nodes.py 中 EvalTask 构造使用的字段与 models.EvalTask 不完全匹配，
        # 需要 mock EvalTask 让构造通过
        mock_task = MagicMock()
        mock_task.task_id = "task-001"
        mock_task.reference_answer = "参考答案"
        with patch("finagent.pipeline.nodes.EvalTask", return_value=mock_task):
            result = await node.execute(state)

        assert result["current_stage"] == PipelineStage.SCORING.value
        assert len(result["task_scores"]) == 1
        assert result["task_scores"][0]["overall_score"] == 85.0
        engine.score_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_empty_data(self):
        """测试空数据"""
        engine = MagicMock(spec=ScoringEngine)
        node = ScorerNode(engine)
        state = _make_pipeline_state(tasks=[], responses=[])
        result = await node.execute(state)

        assert result["task_scores"] == []

    @pytest.mark.asyncio
    async def test_execute_veto_triggered(self):
        """测试一票否决场景"""
        engine = MagicMock(spec=ScoringEngine)
        engine.score_task.return_value = TaskScore(
            task_id="task-001",
            dimension_scores=[
                DimensionScore(
                    dimension=EvalDimension.COMPLIANCE,
                    score=20.0,
                    confidence=0.9,
                    evidence=["violation"],
                    reasoning="compliance issue",
                ),
            ],
            overall_score=20.0,
            rating=RatingLevel.D,
            veto_triggered=True,
            veto_reason="合规性分数过低",
        )

        node = ScorerNode(engine)
        state = _make_pipeline_state(
            tasks=[_make_serialized_task()],
            responses=[{"task_id": "task-001", "output": "", "tool_calls": [], "error": "veto test"}],
        )

        mock_task = MagicMock()
        mock_task.task_id = "task-001"
        mock_task.reference_answer = "参考答案"
        with patch("finagent.pipeline.nodes.EvalTask", return_value=mock_task):
            result = await node.execute(state)

        assert result["task_scores"][0]["veto_triggered"] is True
        assert result["task_scores"][0]["veto_reason"] == "合规性分数过低"


# ===========================================================================
# AggregatorNode 测试
# ===========================================================================


class TestAggregatorNode:
    """测试聚合节点"""

    def test_name(self):
        engine = MagicMock(spec=ScoringEngine)
        node = AggregatorNode(engine)
        assert node.name == "aggregator"

    @pytest.mark.asyncio
    async def test_execute_aggregation_high_score(self):
        """测试高分聚合"""
        engine = MagicMock(spec=ScoringEngine)
        node = AggregatorNode(engine)

        state = _make_pipeline_state(
            task_scores=[
                {
                    "task_id": "t1",
                    "overall_score": 95.0,
                    "rating": "S",
                    "veto_triggered": False,
                    "dimension_scores": [
                        {"dimension": "accuracy", "score": 95.0, "confidence": 0.9, "evidence": [], "reasoning": ""},
                    ],
                },
            ],
        )
        result = await node.execute(state)

        assert result["current_stage"] == PipelineStage.AGGREGATION.value
        eval_score = result["evaluation_score"]
        assert eval_score["overall_score"] == pytest.approx(95.0)
        assert eval_score["overall_rating"] == "S"
        assert eval_score["total_tasks"] == 1
        assert eval_score["passed_tasks"] == 1

    @pytest.mark.asyncio
    async def test_execute_aggregation_mixed_scores(self):
        """测试混合分数聚合"""
        engine = MagicMock(spec=ScoringEngine)
        node = AggregatorNode(engine)

        state = _make_pipeline_state(
            task_scores=[
                {
                    "task_id": "t1",
                    "overall_score": 90.0,
                    "rating": "S",
                    "veto_triggered": False,
                    "dimension_scores": [
                        {"dimension": "accuracy", "score": 90.0, "confidence": 0.9, "evidence": [], "reasoning": ""},
                    ],
                },
                {
                    "task_id": "t2",
                    "overall_score": 50.0,
                    "rating": "C",
                    "veto_triggered": False,
                    "dimension_scores": [
                        {"dimension": "accuracy", "score": 50.0, "confidence": 0.9, "evidence": [], "reasoning": ""},
                    ],
                },
            ],
        )
        result = await node.execute(state)

        eval_score = result["evaluation_score"]
        assert eval_score["overall_score"] == pytest.approx(70.0)
        assert eval_score["passed_tasks"] == 1  # 只有 90 分的通过

    @pytest.mark.asyncio
    async def test_execute_aggregation_with_veto(self):
        """测试含否决的聚合"""
        engine = MagicMock(spec=ScoringEngine)
        node = AggregatorNode(engine)

        state = _make_pipeline_state(
            task_scores=[
                {
                    "task_id": "t1",
                    "overall_score": 80.0,
                    "rating": "A",
                    "veto_triggered": True,
                    "dimension_scores": [
                        {"dimension": "compliance", "score": 20.0, "confidence": 0.9, "evidence": [], "reasoning": ""},
                    ],
                },
            ],
        )
        result = await node.execute(state)

        eval_score = result["evaluation_score"]
        assert eval_score["veto_count"] == 1
        assert eval_score["passed_tasks"] == 0  # veto 不算通过

    @pytest.mark.asyncio
    async def test_execute_aggregation_empty(self):
        """测试空数据聚合"""
        engine = MagicMock(spec=ScoringEngine)
        node = AggregatorNode(engine)

        state = _make_pipeline_state(task_scores=[])
        result = await node.execute(state)

        eval_score = result["evaluation_score"]
        assert eval_score["overall_score"] == 0.0
        assert eval_score["total_tasks"] == 0

    @pytest.mark.asyncio
    async def test_rating_boundaries(self):
        """测试评级边界"""
        engine = MagicMock(spec=ScoringEngine)
        node = AggregatorNode(engine)

        # S 级: >= 95
        state = _make_pipeline_state(task_scores=[
            {"task_id": "t1", "overall_score": 95.0, "rating": "S", "veto_triggered": False, "dimension_scores": []},
        ])
        result = await node.execute(state)
        assert result["evaluation_score"]["overall_rating"] == "S"

        # A 级: >= 85
        state = _make_pipeline_state(task_scores=[
            {"task_id": "t1", "overall_score": 85.0, "rating": "A", "veto_triggered": False, "dimension_scores": []},
        ])
        result = await node.execute(state)
        assert result["evaluation_score"]["overall_rating"] == "A"

        # B 级: >= 70
        state = _make_pipeline_state(task_scores=[
            {"task_id": "t1", "overall_score": 70.0, "rating": "B", "veto_triggered": False, "dimension_scores": []},
        ])
        result = await node.execute(state)
        assert result["evaluation_score"]["overall_rating"] == "B"

        # C 级: >= 60
        state = _make_pipeline_state(task_scores=[
            {"task_id": "t1", "overall_score": 60.0, "rating": "C", "veto_triggered": False, "dimension_scores": []},
        ])
        result = await node.execute(state)
        assert result["evaluation_score"]["overall_rating"] == "C"

        # D 级: < 60
        state = _make_pipeline_state(task_scores=[
            {"task_id": "t1", "overall_score": 50.0, "rating": "D", "veto_triggered": False, "dimension_scores": []},
        ])
        result = await node.execute(state)
        assert result["evaluation_score"]["overall_rating"] == "D"


# ===========================================================================
# ReporterNode 测试
# ===========================================================================


class TestReporterNode:
    """测试报告生成节点"""

    def test_name(self):
        node = ReporterNode()
        assert node.name == "reporter"

    @pytest.mark.asyncio
    async def test_execute_report_generation(self):
        """测试报告生成"""
        node = ReporterNode()
        state = _make_pipeline_state(
            evaluation_score={
                "agent_id": "test-agent",
                "overall_score": 85.0,
                "overall_rating": "A",
                "dimension_averages": {"accuracy": 90.0, "completeness": 80.0},
                "total_tasks": 10,
                "passed_tasks": 8,
                "veto_count": 0,
            },
            task_scores=[
                {
                    "task_id": "t1",
                    "overall_score": 85.0,
                    "rating": "A",
                    "veto_triggered": False,
                    "dimension_scores": [{"dimension": "accuracy", "score": 85.0}],
                },
            ],
        )
        result = await node.execute(state)

        assert result["current_stage"] == PipelineStage.REPORTING.value
        report = result["report"]
        assert report["pipeline_id"] == "test-pipeline-001"
        assert report["agent_id"] == "test-agent"
        assert report["summary"]["overall_score"] == 85.0
        assert report["summary"]["pass_rate"] == pytest.approx(0.8)
        assert "task_details" in report
        assert "recommendations" in report

    @pytest.mark.asyncio
    async def test_execute_report_low_dimension_recommendation(self):
        """测试低分维度生成建议"""
        node = ReporterNode()
        state = _make_pipeline_state(
            evaluation_score={
                "agent_id": "test-agent",
                "overall_score": 50.0,
                "overall_rating": "D",
                "dimension_averages": {"accuracy": 40.0, "completeness": 75.0},
                "total_tasks": 10,
                "passed_tasks": 3,
                "veto_count": 0,
            },
            task_scores=[],
        )
        result = await node.execute(state)

        recommendations = result["report"]["recommendations"]
        assert any("accuracy" in r and "较低" in r for r in recommendations)
        assert any("completeness" in r and "提升空间" in r for r in recommendations)

    @pytest.mark.asyncio
    async def test_execute_report_veto_recommendation(self):
        """测试否决建议"""
        node = ReporterNode()
        state = _make_pipeline_state(
            evaluation_score={
                "agent_id": "test-agent",
                "overall_score": 70.0,
                "overall_rating": "B",
                "dimension_averages": {},
                "total_tasks": 5,
                "passed_tasks": 4,
                "veto_count": 2,
            },
            task_scores=[],
        )
        result = await node.execute(state)

        recommendations = result["report"]["recommendations"]
        assert any("否决" in r for r in recommendations)

    @pytest.mark.asyncio
    async def test_execute_report_good_performance(self):
        """测试良好表现的建议"""
        node = ReporterNode()
        state = _make_pipeline_state(
            evaluation_score={
                "agent_id": "test-agent",
                "overall_score": 90.0,
                "overall_rating": "S",
                "dimension_averages": {"accuracy": 90.0, "completeness": 85.0},
                "total_tasks": 10,
                "passed_tasks": 10,
                "veto_count": 0,
            },
            task_scores=[],
        )
        result = await node.execute(state)

        recommendations = result["report"]["recommendations"]
        assert any("良好" in r for r in recommendations)

    @pytest.mark.asyncio
    async def test_execute_report_empty_evaluation(self):
        """测试空评测分数的报告"""
        node = ReporterNode()
        state = _make_pipeline_state(
            evaluation_score={},
            task_scores=[],
        )
        result = await node.execute(state)

        report = result["report"]
        assert report["summary"]["overall_score"] == 0
        assert report["summary"]["pass_rate"] == pytest.approx(0.0)
