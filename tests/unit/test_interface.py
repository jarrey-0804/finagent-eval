"""
接口模块单元测试
"""

import pytest
from finagent.interface.models import (
    AgentConfig, AgentType, EvalTask, EvalResponse, EvalMode,
    EvalStatus, EvalDimension, TaskType, DifficultyLevel,
)
from finagent.interface.exceptions import (
    EvaluationException, TaskTimeoutException, AgentExecutionException,
    ToolCallException, EnvironmentException, ScoringException,
)


class TestModels:
    """数据模型测试"""

    def test_agent_config_creation(self):
        """测试AgentConfig创建"""
        config = AgentConfig(
            agent_name="Test Agent",
            agent_type=AgentType.INVESTMENT_DECISION,
            version="1.0.0",
            framework="langgraph",
            llm_backend="gpt-4o",
        )
        assert config.agent_name == "Test Agent"
        assert config.agent_type == AgentType.INVESTMENT_DECISION

    def test_eval_task_creation(self):
        """测试EvalTask创建"""
        task = EvalTask(
            task_id="task_001",
            task_type=TaskType.KNOWLEDGE_QA,
            dimension="accuracy",
            input_data={"query": "分析贵州茅台的财务状况"},
        )
        assert task.task_id == "task_001"
        assert task.task_type == TaskType.KNOWLEDGE_QA

    def test_eval_response_creation(self):
        """测试EvalResponse创建"""
        response = EvalResponse(
            task_id="task_001",
            output="贵州茅台2024年Q3营收...",
            tool_calls=[{"tool_name": "get_financial_data", "args": {"symbol": "600519"}}],
        )
        assert response.task_id == "task_001"
        assert response.output is not None
        assert len(response.tool_calls) == 1

    def test_eval_response_has_error_field(self):
        """测试EvalResponse有error字段且默认为None"""
        # 需要提供有效输出或错误才能创建
        response = EvalResponse(
            task_id="task_001",
            output="test output",
        )
        assert response.error is None
        response_with_error = EvalResponse(
            task_id="task_001",
            output="",
            error="some error",
        )
        assert response_with_error.error == "some error"

    def test_enum_values(self):
        """测试枚举值"""
        assert EvalMode.FULL.value == "full"
        assert EvalMode.QUICK.value == "quick"
        assert EvalStatus.PENDING.value == "pending"
        assert TaskType.KNOWLEDGE_QA.value == "knowledge_qa"
        assert TaskType.TOOL_USE.value == "tool_use"
        assert TaskType.TRADING.value == "trading"
        assert DifficultyLevel.EASY.value == "easy"
        assert DifficultyLevel.EXPERT.value == "expert"

    def test_all_dimensions(self):
        """测试所有评测维度"""
        dimensions = list(EvalDimension)
        assert len(dimensions) == 11
        assert EvalDimension.ACCURACY in dimensions
        assert EvalDimension.COMPLIANCE in dimensions
        assert EvalDimension.SECURITY in dimensions


class TestExceptions:
    """异常类测试"""

    def test_evaluation_exception(self):
        """测试基础异常"""
        exc = EvaluationException("评测失败")
        assert str(exc) == "[EVAL_UNKNOWN] 评测失败"

    def test_task_timeout_exception(self):
        """测试任务超时异常"""
        exc = TaskTimeoutException(task_id="task_001", timeout_seconds=120)
        assert "task_001" in str(exc)
        assert "120" in str(exc)

    def test_agent_execution_exception(self):
        """测试Agent执行异常"""
        exc = AgentExecutionException(message="Agent执行失败: 连接失败")
        assert "连接失败" in str(exc)

    def test_tool_call_exception(self):
        """测试工具调用异常"""
        exc = ToolCallException(tool_name="get_stock_price", error="参数错误")
        assert "get_stock_price" in str(exc)

    def test_exception_hierarchy(self):
        """测试异常继承"""
        assert issubclass(TaskTimeoutException, EvaluationException)
        assert issubclass(AgentExecutionException, EvaluationException)
        assert issubclass(ToolCallException, EvaluationException)
        assert issubclass(EnvironmentException, EvaluationException)
        assert issubclass(ScoringException, EvaluationException)
