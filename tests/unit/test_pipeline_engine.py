"""
pipeline/engine.py 单元测试

测试评测引擎的核心功能：快速评测、完整评测、自定义评测、
任务执行（含重试和超时）、评分流程、否决检查等。
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from finagent.interface.models import (
    AgentConfig,
    AgentType,
    EvalDimension,
    EvalMode,
    EvalResponse,
    EvalTask,
    TaskType,
)
from finagent.pipeline.engine import EngineConfig, EngineResult, EvaluationEngine
from finagent.scoring.engine import (
    DimensionScore,
    EvaluationScore,
    RatingLevel,
    TaskScore,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_agent():
    """创建 mock Agent"""
    agent = MagicMock()
    config = MagicMock()
    config.agent_id = "test-agent"
    config.agent_name = "test-agent"
    config.agent_type = AgentType.FINANCIAL_ANALYSIS
    config.version = "1.0"
    config.framework = "langgraph"
    config.llm_backend = "gpt-4o"
    agent.get_config.return_value = config
    agent.ainvoke = AsyncMock(return_value=EvalResponse(
        task_id="task-001",
        output="这是测试回答",
    ))
    return agent


def _make_task(task_id="task-001", query="测试问题", dimension="accuracy"):
    """创建 mock EvalTask"""
    task = MagicMock()
    task.task_id = task_id
    task.input_data = {"query": query, "reference_answer": "参考答案"}
    task.reference_answer = "参考答案"
    task.timeout_seconds = 300
    task.time_limit_seconds = 300
    task.context = {}
    task.dimension = dimension
    return task


def _make_eval_score(
    overall_score=75.0,
    passed_tasks=3,
    veto_count=0,
    total_tasks=3,
    veto_triggered=False,
):
    """创建 mock EvaluationScore"""
    return EvaluationScore(
        agent_id="test-agent",
        task_scores=[
            TaskScore(
                task_id="task-001",
                dimension_scores=[],
                overall_score=overall_score,
                rating=RatingLevel.B,
                veto_triggered=veto_triggered,
            )
        ],
        dimension_averages={EvalDimension.ACCURACY: overall_score},
        overall_score=overall_score,
        overall_rating=RatingLevel.B,
        total_tasks=total_tasks,
        passed_tasks=passed_tasks,
        veto_count=veto_count,
    )


# ---------------------------------------------------------------------------
# EngineConfig 测试
# ---------------------------------------------------------------------------

class TestEngineConfig:
    """EngineConfig 数据类测试"""

    def test_default_config_values(self):
        """验证默认配置值"""
        config = EngineConfig()
        assert config.eval_mode == EvalMode.FULL
        assert config.max_concurrent_tasks == 5
        assert config.task_timeout_seconds == 300
        assert config.max_retries == 2
        assert config.retry_delay_seconds == 5
        assert config.enable_checkpoint is True
        assert config.checkpoint_interval == 10

    def test_custom_config_values(self):
        """验证自定义配置值"""
        config = EngineConfig(
            eval_mode=EvalMode.QUICK,
            max_concurrent_tasks=10,
            task_timeout_seconds=600,
        )
        assert config.eval_mode == EvalMode.QUICK
        assert config.max_concurrent_tasks == 10
        assert config.task_timeout_seconds == 600


# ---------------------------------------------------------------------------
# EngineResult 测试
# ---------------------------------------------------------------------------

class TestEngineResult:
    """EngineResult 数据类测试"""

    def test_default_result_values(self):
        """验证默认结果值"""
        result = EngineResult(
            success=False,
            eval_mode="full",
            total_tasks=5,
            completed_tasks=0,
            failed_tasks=0,
        )
        assert result.success is False
        assert result.overall_score is None
        assert result.overall_rating is None
        assert result.veto_triggered is False
        assert result.veto_reason is None
        assert result.dimension_scores == {}
        assert result.duration_seconds == 0.0
        assert result.errors == []
        assert result.started_at is None
        assert result.completed_at is None

    def test_result_with_values(self):
        """验证带值的结果"""
        result = EngineResult(
            success=True,
            eval_mode="quick",
            total_tasks=3,
            completed_tasks=3,
            failed_tasks=0,
            overall_score=85.0,
            overall_rating="S",
            dimension_scores={"accuracy": 90.0},
            errors=[],
        )
        assert result.success is True
        assert result.overall_score == 85.0
        assert result.overall_rating == "S"
        assert result.dimension_scores == {"accuracy": 90.0}


# ---------------------------------------------------------------------------
# EvaluationEngine 测试
# ---------------------------------------------------------------------------

class TestEvaluationEngine:

    def test_init_default_config(self):
        """初始化时使用默认配置"""
        agent = _make_agent()
        engine = EvaluationEngine(agent)
        assert engine.agent is agent
        assert engine.config.eval_mode == EvalMode.FULL

    def test_init_custom_config(self):
        """初始化时使用自定义配置"""
        agent = _make_agent()
        config = EngineConfig(eval_mode=EvalMode.QUICK, max_concurrent_tasks=3)
        engine = EvaluationEngine(agent, config=config)
        assert engine.config.max_concurrent_tasks == 3

    @pytest.mark.asyncio
    async def test_run_quick_eval_sets_mode(self):
        """快速评测应设置 eval_mode 为 QUICK"""
        agent = _make_agent()
        engine = EvaluationEngine(agent)

        with patch.object(engine, "_execute_evaluation") as mock_exec:
            mock_exec.return_value = EngineResult(
                success=True, eval_mode="quick", total_tasks=0,
                completed_tasks=0, failed_tasks=0,
            )
            result = await engine.run_quick_eval()
            assert engine.config.eval_mode == EvalMode.QUICK
            mock_exec.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_full_eval_sets_mode(self):
        """完整评测应设置 eval_mode 为 FULL"""
        agent = _make_agent()
        engine = EvaluationEngine(agent)

        with patch.object(engine, "_execute_evaluation") as mock_exec:
            mock_exec.return_value = EngineResult(
                success=True, eval_mode="full", total_tasks=0,
                completed_tasks=0, failed_tasks=0,
            )
            result = await engine.run_full_eval()
            assert engine.config.eval_mode == EvalMode.FULL
            mock_exec.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_custom_eval(self):
        """自定义评测应直接执行传入的任务"""
        agent = _make_agent()
        engine = EvaluationEngine(agent)
        tasks = [_make_task("task-001")]

        with patch.object(engine, "_execute_evaluation") as mock_exec:
            mock_exec.return_value = EngineResult(
                success=True, eval_mode="full", total_tasks=1,
                completed_tasks=1, failed_tasks=0,
            )
            result = await engine.run_custom_eval(tasks)
            mock_exec.assert_called_once_with(tasks)

    @pytest.mark.asyncio
    async def test_execute_evaluation_success(self):
        """评测成功时应填充所有结果字段"""
        agent = _make_agent()
        engine = EvaluationEngine(agent)
        tasks = [_make_task("task-001")]

        mock_score = _make_eval_score(overall_score=80.0, passed_tasks=1, total_tasks=1)

        with patch.object(engine, "_execute_agent_tasks", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = [EvalResponse(task_id="task-001", output="回答")]
            with patch.object(engine.scoring_engine, "score_evaluation", return_value=mock_score):
                result = await engine._execute_evaluation(tasks)

        assert result.success is True
        assert result.total_tasks == 1
        assert result.overall_score == 80.0
        assert result.completed_at is not None
        assert result.duration_seconds >= 0

    @pytest.mark.asyncio
    async def test_execute_evaluation_veto_triggered(self):
        """评测中触发否决时应标记 veto"""
        agent = _make_agent()
        engine = EvaluationEngine(agent)
        tasks = [_make_task("task-001")]

        mock_score = _make_eval_score(
            overall_score=20.0, passed_tasks=0, total_tasks=1, veto_count=1,
        )
        # 给 task_score 设置 veto_triggered
        mock_score.task_scores[0].veto_triggered = True
        mock_score.task_scores[0].veto_reason = "合规性否决"

        with patch.object(engine, "_execute_agent_tasks", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = [EvalResponse(task_id="task-001", output="回答")]
            with patch.object(engine.scoring_engine, "score_evaluation", return_value=mock_score):
                result = await engine._execute_evaluation(tasks)

        assert result.veto_triggered is True
        assert result.veto_reason == "合规性否决"

    @pytest.mark.asyncio
    async def test_execute_evaluation_exception(self):
        """评测异常时应记录错误"""
        agent = _make_agent()
        engine = EvaluationEngine(agent)
        tasks = [_make_task("task-001")]

        with patch.object(engine, "_execute_agent_tasks", new_callable=AsyncMock) as mock_exec:
            mock_exec.side_effect = RuntimeError("测试异常")
            result = await engine._execute_evaluation(tasks)

        assert result.success is False
        assert len(result.errors) > 0
        assert "测试异常" in result.errors[0]

    @pytest.mark.asyncio
    async def test_execute_agent_tasks_success(self):
        """任务执行成功应返回响应列表"""
        agent = _make_agent()
        engine = EvaluationEngine(agent)
        tasks = [_make_task("task-001")]

        responses = await engine._execute_agent_tasks(tasks)
        assert len(responses) == 1
        assert responses[0].task_id == "task-001"
        assert responses[0].output == "这是测试回答"

    @pytest.mark.asyncio
    async def test_execute_agent_tasks_timeout(self):
        """任务超时后重试耗尽应返回超时错误响应"""
        agent = _make_agent()
        agent.ainvoke.side_effect = TimeoutError("任务超时")
        engine = EvaluationEngine(agent, config=EngineConfig(max_retries=1, retry_delay_seconds=0))
        tasks = [_make_task("task-001")]

        responses = await engine._execute_agent_tasks(tasks)
        assert len(responses) == 1
        assert "超时" in responses[0].error

    @pytest.mark.asyncio
    async def test_execute_agent_tasks_generic_exception(self):
        """任务执行异常后重试耗尽应返回错误响应"""
        agent = _make_agent()
        agent.ainvoke.side_effect = RuntimeError("执行失败")
        engine = EvaluationEngine(agent, config=EngineConfig(max_retries=1, retry_delay_seconds=0))
        tasks = [_make_task("task-001")]

        responses = await engine._execute_agent_tasks(tasks)
        assert len(responses) == 1
        assert "执行失败" in responses[0].error

    @pytest.mark.asyncio
    async def test_execute_agent_tasks_concurrency_limit(self):
        """并发任务数应受 max_concurrent_tasks 限制"""
        agent = _make_agent()
        engine = EvaluationEngine(agent, config=EngineConfig(max_concurrent_tasks=1, max_retries=0))
        tasks = [_make_task(f"task-{i}") for i in range(5)]

        call_count = 0
        max_concurrent = 0
        current_concurrent = 0

        original_ainvoke = agent.ainvoke

        async def tracking_ainvoke(task):
            nonlocal call_count, max_concurrent, current_concurrent
            call_count += 1
            current_concurrent += 1
            if current_concurrent > max_concurrent:
                max_concurrent = current_concurrent
            await asyncio.sleep(0.01)
            current_concurrent -= 1
            return EvalResponse(task_id=f"task-{call_count}", output="ok")

        agent.ainvoke = tracking_ainvoke
        responses = await engine._execute_agent_tasks(tasks)
        assert len(responses) == 5
        assert max_concurrent <= 1
