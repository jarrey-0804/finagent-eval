"""
Financial Agent Interface - 接口模块

对应需求: FR-001 Agent 接口规范
"""

from .base import FinancialAgentInterface
from .exceptions import (
    AgentExecutionException,
    DatabaseException,
    EnvironmentException,
    EvaluationException,
    LLMJudgeException,
    MCPConnectionException,
    ScoringException,
    TaskTimeoutException,
    ToolCallException,
    ValidationException,
)
from .models import (
    AgentConfig,
    AgentState,
    AgentType,
    DifficultyLevel,
    EvalDimension,
    EvalMode,
    EvalResponse,
    EvalResult,
    EvalStatus,
    EvalTask,
    EvaluationReport,
    TaskType,
    ToolCallRecord,
)

__all__ = [
    # 核心接口
    "FinancialAgentInterface",
    # 数据模型
    "AgentConfig",
    "AgentState",
    "AgentType",
    "DifficultyLevel",
    "EvalDimension",
    "EvalMode",
    "EvalResponse",
    "EvalStatus",
    "EvalTask",
    "EvalResult",
    "EvaluationReport",
    "TaskType",
    "ToolCallRecord",
    # 异常
    "EvaluationException",
    "TaskTimeoutException",
    "AgentExecutionException",
    "ToolCallException",
    "EnvironmentException",
    "MCPConnectionException",
    "DatabaseException",
    "ValidationException",
    "ScoringException",
    "LLMJudgeException",
]
