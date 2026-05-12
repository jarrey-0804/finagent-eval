"""
三阶段评估流水线单元测试 (FR-007-02)

测试内容：
- EvalPhase / PipelineStage 新枚举值
- PipelineState 新字段
- PipelineConfig enable_three_stage 配置
- PhaseResult 数据类
- generate_phase_tasks() 方法
- ThreeStagePipeline 基本流程
- 三阶段流水线阶段粒度恢复
- 向后兼容性（EvalPipeline 不受影响）
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from finagent.pipeline.pipeline import (
    PipelineStage,
    EvalPhase,
    PipelineState,
    PipelineConfig,
    PipelineResult,
    PhaseResult,
    EvalPipeline,
    ThreeStagePipeline,
    PHASE_DIMENSIONS,
    PHASE_TASK_TYPES,
    PHASE_ORDER,
    PHASE_STAGE_MAP,
)
from finagent.taskgen.generator import EvalTaskGenerator, TaskGeneratorConfig
from finagent.interface.models import (
    EvalTask,
    EvalResponse,
    EvalMode,
    EvalStatus,
    EvalDimension,
    AgentConfig,
    AgentType,
    TaskType,
)
from finagent.scoring.engine import EvaluationScore, TaskScore, RatingLevel, DimensionScore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class MockAgent:
    """模拟 Agent，实现 FinancialAgentInterface 的 ainvoke 调用约定"""

    def __init__(self):
        self.config = AgentConfig(
            agent_name="test_agent",
            agent_type=AgentType.FINANCIAL_ANALYSIS,
            version="1.0.0",
            framework="custom",
            llm_backend="test-llm",
        )

    def get_config(self):
        return self.config

    async def ainvoke(self, query, context=None):
        return EvalResponse(
            task_id="mock_task",
            output=f"Mock response for: {query}",
            tool_calls=[],
        )


@pytest.fixture
def mock_agent():
    return MockAgent()


@pytest.fixture
def pipeline_config_full():
    return PipelineConfig(eval_mode=EvalMode.FULL, generate_report=False)


@pytest.fixture
def pipeline_config_quick():
    return PipelineConfig(eval_mode=EvalMode.QUICK, generate_report=False)


@pytest.fixture
def task_generator():
    config = TaskGeneratorConfig(
        tasks_per_source=2,
        max_total_tasks=10,
    )
    return EvalTaskGenerator(config)


# ---------------------------------------------------------------------------
# 枚举和常量测试
# ---------------------------------------------------------------------------

class TestEvalPhase:
    """EvalPhase 枚举测试"""

    def test_phase_values(self):
        assert EvalPhase.STATIC.value == "static"
        assert EvalPhase.DYNAMIC.value == "dynamic"
        assert EvalPhase.TRUST.value == "trust"

    def test_phase_from_string(self):
        assert EvalPhase("static") == EvalPhase.STATIC
        assert EvalPhase("dynamic") == EvalPhase.DYNAMIC
        assert EvalPhase("trust") == EvalPhase.TRUST


class TestPipelineStage:
    """PipelineStage 新增阶段测试"""

    def test_original_stages_exist(self):
        """确保原有阶段值不受影响"""
        assert PipelineStage.INIT.value == "init"
        assert PipelineStage.TASK_GENERATION.value == "task_generation"
        assert PipelineStage.AGENT_EXECUTION.value == "agent_execution"
        assert PipelineStage.SCORING.value == "scoring"
        assert PipelineStage.AGGREGATION.value == "aggregation"
        assert PipelineStage.REPORTING.value == "reporting"
        assert PipelineStage.COMPLETED.value == "completed"
        assert PipelineStage.FAILED.value == "failed"

    def test_new_stages_exist(self):
        """三阶段新增的阶段值"""
        assert PipelineStage.STATIC_EVAL.value == "static_eval"
        assert PipelineStage.DYNAMIC_EVAL.value == "dynamic_eval"
        assert PipelineStage.TRUST_EVAL.value == "trust_eval"


class TestPhaseMappings:
    """阶段映射常量测试"""

    def test_phase_dimensions(self):
        """验证各阶段的维度映射"""
        assert EvalPhase.STATIC in PHASE_DIMENSIONS
        assert EvalPhase.DYNAMIC in PHASE_DIMENSIONS
        assert EvalPhase.TRUST in PHASE_DIMENSIONS

        # Static 阶段应包含能力维度
        static_dims = PHASE_DIMENSIONS[EvalPhase.STATIC]
        assert EvalDimension.ACCURACY in static_dims
        assert EvalDimension.COMPLETENESS in static_dims
        assert EvalDimension.REASONING in static_dims
        assert EvalDimension.PROFESSIONALISM in static_dims
        assert EvalDimension.TOOL_USAGE in static_dims

        # Dynamic 阶段应包含鲁棒性
        dynamic_dims = PHASE_DIMENSIONS[EvalPhase.DYNAMIC]
        assert EvalDimension.ROBUSTNESS in dynamic_dims

        # Trust 阶段应包含可信度维度
        trust_dims = PHASE_DIMENSIONS[EvalPhase.TRUST]
        assert EvalDimension.COMPLIANCE in trust_dims
        assert EvalDimension.SECURITY in trust_dims
        assert EvalDimension.RISK_AWARENESS in trust_dims
        assert EvalDimension.TRANSPARENCY in trust_dims
        assert EvalDimension.CONSISTENCY in trust_dims

    def test_phase_task_types(self):
        """验证各阶段的任务类型映射"""
        assert TaskType.KNOWLEDGE_QA in PHASE_TASK_TYPES[EvalPhase.STATIC]
        assert TaskType.ANALYSIS in PHASE_TASK_TYPES[EvalPhase.STATIC]
        assert TaskType.TOOL_USE in PHASE_TASK_TYPES[EvalPhase.STATIC]

        assert TaskType.TRADING in PHASE_TASK_TYPES[EvalPhase.DYNAMIC]
        assert TaskType.ADVERSARIAL in PHASE_TASK_TYPES[EvalPhase.DYNAMIC]

        assert TaskType.TRUSTWORTHINESS in PHASE_TASK_TYPES[EvalPhase.TRUST]

    def test_phase_order(self):
        """验证阶段执行顺序"""
        assert PHASE_ORDER == [EvalPhase.STATIC, EvalPhase.DYNAMIC, EvalPhase.TRUST]

    def test_phase_stage_map(self):
        """验证阶段到 PipelineStage 的映射"""
        assert PHASE_STAGE_MAP[EvalPhase.STATIC] == PipelineStage.STATIC_EVAL
        assert PHASE_STAGE_MAP[EvalPhase.DYNAMIC] == PipelineStage.DYNAMIC_EVAL
        assert PHASE_STAGE_MAP[EvalPhase.TRUST] == PipelineStage.TRUST_EVAL


# ---------------------------------------------------------------------------
# PipelineState 新字段测试
# ---------------------------------------------------------------------------

class TestPipelineState:
    """PipelineState 新字段测试"""

    def test_state_includes_phase_fields(self):
        """PipelineState 应包含 current_phase 和 phase_results"""
        state = PipelineState(
            pipeline_id="test-001",
            agent_id="agent-001",
            eval_mode="full",
            status="pending",
            current_stage="init",
            tasks=[],
            current_task_index=0,
            responses=[],
            task_scores=[],
            evaluation_score=None,
            report=None,
            errors=[],
            retry_count=0,
            started_at=None,
            completed_at=None,
            metadata={},
            current_phase="static",
            phase_results={},
        )
        assert state["current_phase"] == "static"
        assert state["phase_results"] == {}


# ---------------------------------------------------------------------------
# PipelineConfig 测试
# ---------------------------------------------------------------------------

class TestPipelineConfig:
    """PipelineConfig 测试"""

    def test_default_config_has_enable_three_stage(self):
        """默认配置应包含 enable_three_stage"""
        config = PipelineConfig()
        assert hasattr(config, "enable_three_stage")
        assert config.enable_three_stage is True

    def test_enable_three_stage_can_be_disabled(self):
        """可以禁用三阶段流水线"""
        config = PipelineConfig(enable_three_stage=False)
        assert config.enable_three_stage is False

    def test_backward_compatible_config(self):
        """原有配置字段不受影响"""
        config = PipelineConfig(
            eval_mode=EvalMode.QUICK,
            max_concurrent_tasks=3,
            task_timeout_seconds=60,
            generate_report=False,
        )
        assert config.eval_mode == EvalMode.QUICK
        assert config.max_concurrent_tasks == 3
        assert config.task_timeout_seconds == 60
        assert config.generate_report is False


# ---------------------------------------------------------------------------
# PhaseResult 测试
# ---------------------------------------------------------------------------

class TestPhaseResult:
    """PhaseResult 数据类测试"""

    def test_default_phase_result(self):
        pr = PhaseResult(phase=EvalPhase.STATIC)
        assert pr.phase == EvalPhase.STATIC
        assert pr.tasks == []
        assert pr.responses == []
        assert pr.task_scores == []
        assert pr.evaluation_score is None
        assert pr.errors == []

    def test_phase_result_to_dict(self):
        pr = PhaseResult(phase=EvalPhase.STATIC)
        d = pr.to_dict()
        assert d["phase"] == "static"
        assert d["task_count"] == 0
        assert d["overall_score"] is None
        assert d["overall_rating"] is None

    def test_phase_result_to_dict_with_score(self):
        score = EvaluationScore(
            agent_id="test",
            task_scores=[],
            dimension_averages={EvalDimension.ACCURACY: 85.0},
            overall_score=85.0,
            overall_rating=RatingLevel.S,
            total_tasks=10,
            passed_tasks=8,
            veto_count=0,
        )
        pr = PhaseResult(phase=EvalPhase.STATIC, evaluation_score=score)
        d = pr.to_dict()
        assert d["overall_score"] == 85.0
        assert d["overall_rating"] == "S"
        assert d["task_count"] == 0
        assert "accuracy" in d["dimension_averages"]

    def test_phase_result_duration(self):
        start = datetime(2024, 1, 1, 12, 0, 0)
        end = datetime(2024, 1, 1, 12, 5, 30)
        pr = PhaseResult(phase=EvalPhase.STATIC, started_at=start, completed_at=end)
        assert pr.duration_seconds == 330.0

    def test_phase_result_duration_none(self):
        pr = PhaseResult(phase=EvalPhase.STATIC)
        assert pr.duration_seconds is None


# ---------------------------------------------------------------------------
# generate_phase_tasks 测试
# ---------------------------------------------------------------------------

class TestGeneratePhaseTasks:
    """generate_phase_tasks() 方法测试"""

    def test_generate_static_phase_tasks(self, task_generator):
        """生成静态阶段任务"""
        tasks = task_generator.generate_phase_tasks(EvalPhase.STATIC)
        assert isinstance(tasks, list)
        for task in tasks:
            assert task.metadata.get("eval_phase") == "static"

    def test_generate_dynamic_phase_tasks(self, task_generator):
        """生成动态阶段任务"""
        tasks = task_generator.generate_phase_tasks(EvalPhase.DYNAMIC)
        assert isinstance(tasks, list)
        for task in tasks:
            assert task.metadata.get("eval_phase") == "dynamic"

    def test_generate_trust_phase_tasks(self, task_generator):
        """生成信任阶段任务"""
        tasks = task_generator.generate_phase_tasks(EvalPhase.TRUST)
        assert isinstance(tasks, list)
        for task in tasks:
            assert task.metadata.get("eval_phase") == "trust"

    def test_generate_phase_tasks_with_string(self, task_generator):
        """支持字符串输入"""
        tasks = task_generator.generate_phase_tasks("static")
        assert isinstance(tasks, list)

    def test_generate_phase_tasks_custom_count(self, task_generator):
        """自定义任务数量"""
        tasks = task_generator.generate_phase_tasks(EvalPhase.STATIC, n_tasks=5)
        assert len(tasks) <= 5

    def test_generate_phase_tasks_returns_eval_tasks(self, task_generator):
        """返回的应是 EvalTask 对象"""
        tasks = task_generator.generate_phase_tasks(EvalPhase.STATIC)
        for task in tasks:
            assert isinstance(task, EvalTask)
            assert task.task_id is not None
            assert task.task_type is not None


# ---------------------------------------------------------------------------
# ThreeStagePipeline 测试
# ---------------------------------------------------------------------------

class TestThreeStagePipeline:
    """ThreeStagePipeline 测试"""

    def test_initialization(self, mock_agent, pipeline_config_full):
        """测试初始化"""
        pipeline = ThreeStagePipeline(mock_agent, pipeline_config_full)
        assert pipeline.config.eval_mode == EvalMode.FULL
        assert pipeline._state is None
        assert pipeline._phase_results == {}

    def test_get_phases_to_run_full(self, mock_agent, pipeline_config_full):
        """FULL 模式应运行三个阶段"""
        pipeline = ThreeStagePipeline(mock_agent, pipeline_config_full)
        phases = pipeline._get_phases_to_run()
        assert phases == [EvalPhase.STATIC, EvalPhase.DYNAMIC, EvalPhase.TRUST]

    def test_get_phases_to_run_quick(self, mock_agent, pipeline_config_quick):
        """QUICK 模式应只运行静态阶段"""
        pipeline = ThreeStagePipeline(mock_agent, pipeline_config_quick)
        phases = pipeline._get_phases_to_run()
        assert phases == [EvalPhase.STATIC]

    @pytest.mark.asyncio
    async def test_run_full_mode(self, mock_agent, pipeline_config_full):
        """测试 FULL 模式完整运行"""
        pipeline = ThreeStagePipeline(mock_agent, pipeline_config_full)
        result = await pipeline.run()

        assert result.status == EvalStatus.COMPLETED
        assert result.evaluation_score is not None
        assert result.pipeline_id is not None

        # 验证三个阶段都有结果
        phase_results = pipeline.get_phase_results()
        assert EvalPhase.STATIC in phase_results
        assert EvalPhase.DYNAMIC in phase_results
        assert EvalPhase.TRUST in phase_results

    @pytest.mark.asyncio
    async def test_run_quick_mode(self, mock_agent, pipeline_config_quick):
        """测试 QUICK 模式只运行静态阶段"""
        pipeline = ThreeStagePipeline(mock_agent, pipeline_config_quick)
        result = await pipeline.run()

        assert result.status == EvalStatus.COMPLETED

        # 只有静态阶段有结果
        phase_results = pipeline.get_phase_results()
        assert EvalPhase.STATIC in phase_results
        assert EvalPhase.DYNAMIC not in phase_results
        assert EvalPhase.TRUST not in phase_results

    @pytest.mark.asyncio
    async def test_run_generates_report(self, mock_agent):
        """测试报告生成"""
        config = PipelineConfig(eval_mode=EvalMode.FULL, generate_report=True)
        pipeline = ThreeStagePipeline(mock_agent, config)
        result = await pipeline.run()

        assert result.report is not None
        assert result.report["pipeline_type"] == "three_stage"
        assert "phases" in result.report
        assert "static" in result.report["phases"]
        assert "dynamic" in result.report["phases"]
        assert "trust" in result.report["phases"]

    @pytest.mark.asyncio
    async def test_run_with_agent_error(self, mock_agent, pipeline_config_full):
        """测试 Agent 执行错误时的处理——异常被捕获为错误响应，流水线仍能完成"""
        # 让 agent 抛出异常
        async def failing_ainvoke(query, context=None):
            raise RuntimeError("Agent execution failed")

        mock_agent.ainvoke = failing_ainvoke

        pipeline = ThreeStagePipeline(mock_agent, pipeline_config_full)
        result = await pipeline.run()

        # 流水线应完成（异常被捕获为错误响应）
        assert result.status == EvalStatus.COMPLETED
        # 但评分应反映错误（任务得分为 0）
        assert result.evaluation_score is not None

    @pytest.mark.asyncio
    async def test_state_tracking(self, mock_agent, pipeline_config_full):
        """测试状态跟踪"""
        pipeline = ThreeStagePipeline(mock_agent, pipeline_config_full)
        await pipeline.run()

        state = pipeline.get_state()
        assert state is not None
        assert state["status"] == "completed"
        assert state["current_stage"] == "completed"
        assert state["current_phase"] == "trust"  # 最后执行的是 trust 阶段
        assert len(state["phase_results"]) == 3

    @pytest.mark.asyncio
    async def test_resume_from_state(self, mock_agent, pipeline_config_full):
        """测试从状态恢复"""
        pipeline = ThreeStagePipeline(mock_agent, pipeline_config_full)

        # 先运行到完成
        result1 = await pipeline.run()
        assert result1.status == EvalStatus.COMPLETED

        # 保存状态
        saved_state = pipeline.get_state()

        # 创建新 pipeline 并恢复
        pipeline2 = ThreeStagePipeline(mock_agent, pipeline_config_full)
        result2 = await pipeline2.resume(state=saved_state)

        # 恢复已完成的状态应直接返回 COMPLETED
        assert result2.status == EvalStatus.COMPLETED
        assert result2.evaluation_score is not None

    @pytest.mark.asyncio
    async def test_resume_from_partial_state(self, mock_agent, pipeline_config_full):
        """测试从部分完成的状态恢复（静态阶段已完成）"""
        # 创建一个只完成了静态阶段的状态
        partial_state = PipelineState(
            pipeline_id="test-resume-001",
            agent_id="agent-001",
            eval_mode="full",
            status="running",
            current_stage="static_eval",
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
            current_phase="static",
            phase_results={
                "static": {
                    "phase": "static",
                    "task_count": 3,
                    "overall_score": 75.0,
                    "overall_rating": "A",
                    "dimension_averages": {"accuracy": 80.0},
                    "started_at": datetime.now().isoformat(),
                    "completed_at": datetime.now().isoformat(),
                    "errors": [],
                },
            },
        )

        pipeline = ThreeStagePipeline(mock_agent, pipeline_config_full)
        result = await pipeline.resume(state=partial_state)

        assert result.status == EvalStatus.COMPLETED
        # 验证动态和信任阶段被执行
        phase_results = pipeline.get_phase_results()
        assert EvalPhase.DYNAMIC in phase_results
        assert EvalPhase.TRUST in phase_results

    @pytest.mark.asyncio
    async def test_aggregate_phase_results(self, mock_agent, pipeline_config_full):
        """测试阶段结果聚合"""
        pipeline = ThreeStagePipeline(mock_agent, pipeline_config_full)

        # 手动设置阶段结果
        from finagent.scoring.engine import DimensionScore

        static_score = TaskScore(
            task_id="static_1",
            dimension_scores=[DimensionScore(dimension=EvalDimension.ACCURACY, score=80.0, confidence=0.9)],
            overall_score=80.0,
            rating=RatingLevel.A,
        )
        dynamic_score = TaskScore(
            task_id="dynamic_1",
            dimension_scores=[DimensionScore(dimension=EvalDimension.ROBUSTNESS, score=70.0, confidence=0.8)],
            overall_score=70.0,
            rating=RatingLevel.B,
        )
        trust_score = TaskScore(
            task_id="trust_1",
            dimension_scores=[DimensionScore(dimension=EvalDimension.COMPLIANCE, score=90.0, confidence=0.95)],
            overall_score=90.0,
            rating=RatingLevel.S,
        )

        pipeline._state = PipelineState(
            pipeline_id="test-agg",
            agent_id="agent-001",
            eval_mode="full",
            status="running",
            current_stage="reporting",
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
            current_phase="trust",
            phase_results={},
        )

        from finagent.pipeline.pipeline import PhaseResult
        pipeline._phase_results = {
            EvalPhase.STATIC: PhaseResult(
                phase=EvalPhase.STATIC,
                task_scores=[static_score],
                evaluation_score=EvaluationScore(
                    agent_id="agent-001",
                    task_scores=[static_score],
                    dimension_averages={EvalDimension.ACCURACY: 80.0},
                    overall_score=80.0,
                    overall_rating=RatingLevel.A,
                    total_tasks=1,
                    passed_tasks=1,
                    veto_count=0,
                ),
            ),
            EvalPhase.DYNAMIC: PhaseResult(
                phase=EvalPhase.DYNAMIC,
                task_scores=[dynamic_score],
                evaluation_score=EvaluationScore(
                    agent_id="agent-001",
                    task_scores=[dynamic_score],
                    dimension_averages={EvalDimension.ROBUSTNESS: 70.0},
                    overall_score=70.0,
                    overall_rating=RatingLevel.B,
                    total_tasks=1,
                    passed_tasks=1,
                    veto_count=0,
                ),
            ),
            EvalPhase.TRUST: PhaseResult(
                phase=EvalPhase.TRUST,
                task_scores=[trust_score],
                evaluation_score=EvaluationScore(
                    agent_id="agent-001",
                    task_scores=[trust_score],
                    dimension_averages={EvalDimension.COMPLIANCE: 90.0},
                    overall_score=90.0,
                    overall_rating=RatingLevel.S,
                    total_tasks=1,
                    passed_tasks=1,
                    veto_count=0,
                ),
            ),
        }

        aggregated = pipeline._aggregate_phase_results()
        assert aggregated.total_tasks == 3
        assert aggregated.agent_id == "agent-001"
        # 总分应为 (80 + 70 + 90) / 3 = 80.0
        assert aggregated.overall_score == 80.0


# ---------------------------------------------------------------------------
# 向后兼容性测试
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    """确保原有 EvalPipeline 不受影响"""

    def test_pipeline_config_backward_compatible(self):
        """PipelineConfig 默认值不变"""
        config = PipelineConfig()
        assert config.eval_mode == EvalMode.FULL
        assert config.max_concurrent_tasks == 5
        assert config.task_timeout_seconds == 300
        assert config.max_retries == 3
        assert config.enable_checkpoint is True
        assert config.generate_report is True

    def test_pipeline_stage_original_values_unchanged(self):
        """原有 PipelineStage 值不变"""
        assert PipelineStage.INIT.value == "init"
        assert PipelineStage.COMPLETED.value == "completed"
        assert PipelineStage.FAILED.value == "failed"

    def test_pipeline_result_unchanged(self):
        """PipelineResult 接口不变"""
        result = PipelineResult(
            pipeline_id="test",
            agent_id="agent",
            status=EvalStatus.COMPLETED,
        )
        assert result.pipeline_id == "test"
        assert result.agent_id == "agent"
        assert result.status == EvalStatus.COMPLETED
        assert result.evaluation_score is None
        assert result.report is None
        assert result.errors == []
        assert result.duration_seconds is None


# ---------------------------------------------------------------------------
# __init__.py 导出测试
# ---------------------------------------------------------------------------

class TestModuleExports:
    """测试模块导出"""

    def test_pipeline_module_exports(self):
        """pipeline 模块应导出新增类型"""
        from finagent.pipeline import (
            EvalPipeline,
            PipelineConfig,
            PipelineState,
            PipelineStage,
            EvalPhase,
            PipelineResult,
            PhaseResult,
            ThreeStagePipeline,
            PHASE_DIMENSIONS,
            PHASE_TASK_TYPES,
            PHASE_ORDER,
            PHASE_STAGE_MAP,
        )
        # 确认导入成功
        assert EvalPhase is not None
        assert ThreeStagePipeline is not None
        assert PhaseResult is not None
