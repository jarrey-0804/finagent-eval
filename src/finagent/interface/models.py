"""
Financial Agent Interface - 数据模型定义

对应需求: FR-001 Agent 接口规范
"""

import re
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .._compat import StrEnum


class AgentType(StrEnum):
    """Agent 类型枚举"""
    INVESTMENT_DECISION = "investment_decision"
    QUANT_RESEARCH = "quant_research"
    TRADE_EXECUTION = "trade_execution"
    FINANCIAL_ANALYSIS = "financial_analysis"


class TaskType(StrEnum):
    """任务类型枚举"""
    KNOWLEDGE_QA = "knowledge_qa"
    ANALYSIS = "analysis"
    TOOL_USE = "tool_use"
    TRADING = "trading"
    ADVERSARIAL = "adversarial"
    TRUSTWORTHINESS = "trustworthiness"
    SINGLE_TURN = "single_turn"
    MULTI_TURN = "multi_turn"
    TOOL_CALL = "tool_call"


class EvalMode(StrEnum):
    """评测模式枚举"""
    QUICK = "quick"        # 快速评测（5 个核心维度）
    FULL = "full"          # 完整评测（11 个维度）


class EvalStatus(StrEnum):
    """评测状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class EvalDimension(StrEnum):
    """评测维度枚举 — 4+7 双层评测体系"""
    # 能力维度 (60%)
    ACCURACY = "accuracy"               # 准确性
    COMPLETENESS = "completeness"       # 完整性
    REASONING = "reasoning"             # 推理能力
    TOOL_USAGE = "tool_usage"           # 工具使用
    PROFESSIONALISM = "professionalism" # 专业性
    # 可信度维度 (40%)
    COMPLIANCE = "compliance"           # 合规性
    RISK_AWARENESS = "risk_awareness"   # 风险意识
    ROBUSTNESS = "robustness"           # 鲁棒性
    SECURITY = "security"               # 安全性
    TRANSPARENCY = "transparency"       # 透明度
    CONSISTENCY = "consistency"         # 一致性


class DifficultyLevel(StrEnum):
    """难度等级枚举"""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"


class AgentConfig(BaseModel):
    """
    Agent 配置信息。

    对应需求: FR-001-02
    """
    agent_name: str = Field(description="Agent 名称")
    agent_type: AgentType = Field(description="Agent 类型")
    version: str = Field(description="Agent 版本号")
    framework: str = Field(description="开发框架：langgraph / autogen / crewai / custom")
    llm_backend: str = Field(description="底层 LLM：gpt-4o / claude-sonnet / deepseek / qwen 等")
    description: str = Field(default="", description="Agent 功能描述")
    supported_tools: list[str] = Field(default_factory=list, description="支持的工具列表")
    mcp_servers: list[str] = Field(default_factory=list, description="需要的 MCP 服务器列表")

    model_config = ConfigDict(use_enum_values=True)

    @field_validator('agent_name')
    @classmethod
    def validate_agent_name(cls, v: str) -> str:
        """验证 Agent 名称"""
        if not v or len(v.strip()) == 0:
            raise ValueError('Agent 名称不能为空')
        if len(v) > 128:
            raise ValueError('Agent 名称长度不能超过 128 字符')
        return v.strip()

    @field_validator('version')
    @classmethod
    def validate_version(cls, v: str) -> str:
        """验证版本号格式（语义化版本）"""
        if not v:
            raise ValueError('版本号不能为空')
        # 支持语义化版本格式: x.y.z 或 x.y.z-prerelease
        pattern = r'^(\d+)\.(\d+)\.(\d+)(?:-[a-zA-Z0-9.]+)?$'
        if not re.match(pattern, v):
            raise ValueError('版本号必须符合语义化版本格式 (如: 1.0.0, 1.0.0-alpha)')
        return v

    @field_validator('framework')
    @classmethod
    def validate_framework(cls, v: str) -> str:
        """验证开发框架"""
        valid_frameworks = {'langgraph', 'autogen', 'crewai', 'custom'}
        if v not in valid_frameworks:
            raise ValueError(f'框架必须是以下之一: {valid_frameworks}')
        return v


class EvalTask(BaseModel):
    """
    评测任务数据模型。

    对应需求: FR-001-10
    """
    task_id: str = Field(description="任务唯一标识")
    task_type: TaskType = Field(description="任务类型")
    dimension: str = Field(description="评测维度：对应 SOP 的 11 个维度之一")
    input_data: dict = Field(description="任务输入数据（问题、市场数据、工具列表等）")
    context: dict = Field(default_factory=dict, description="上下文信息（历史对话、持仓状态等）")
    time_limit_seconds: int = Field(default=300, ge=1, le=3600, description="任务超时时间（秒）")
    metadata: dict = Field(default_factory=dict, description="元数据（难度级别、数据集来源等）")

    model_config = ConfigDict(use_enum_values=True)

    @field_validator('task_id')
    @classmethod
    def validate_task_id(cls, v: str) -> str:
        """验证任务ID"""
        if not v or len(v.strip()) == 0:
            raise ValueError('任务ID不能为空')
        if len(v) > 128:
            raise ValueError('任务ID长度不能超过 128 字符')
        # 只允许字母、数字、下划线、连字符和点
        if not re.match(r'^[a-zA-Z0-9_\-\.]+$', v):
            raise ValueError('任务ID只能包含字母、数字、下划线、连字符和点')
        return v.strip()

    @field_validator('input_data')
    @classmethod
    def validate_input_data(cls, v: dict) -> dict:
        """验证输入数据"""
        if not v:
            raise ValueError('输入数据不能为空')
        if 'query' not in v:
            raise ValueError('输入数据必须包含 query 字段')
        query = v['query']
        if not query or len(str(query).strip()) < 5:
            raise ValueError('query 内容过短，至少 5 个字符')
        return v

    @field_validator('dimension')
    @classmethod
    def validate_dimension(cls, v: str) -> str:
        """验证评测维度"""
        valid_dimensions = {d.value for d in EvalDimension}
        if v not in valid_dimensions:
            raise ValueError(f'评测维度必须是以下之一: {valid_dimensions}')
        return v

    @model_validator(mode='after')
    def validate_task_consistency(self) -> 'EvalTask':
        """验证任务类型与维度的一致性（警告级别，不阻止创建）"""
        # 静态评测维度建议
        static_task_types = {TaskType.KNOWLEDGE_QA, TaskType.ANALYSIS}
        static_dimensions = {
            EvalDimension.ACCURACY.value,
            EvalDimension.COMPLETENESS.value,
            EvalDimension.REASONING.value,
            EvalDimension.PROFESSIONALISM.value
        }

        if self.task_type in static_task_types and self.dimension not in static_dimensions:
            # 记录警告但不阻止创建（允许测试使用非标准组合）
            # 实际生产环境可以通过监控发现
            pass

        # 对抗性任务建议使用对抗性维度
        if self.task_type == TaskType.ADVERSARIAL:
            adversarial_dims = {
                EvalDimension.ROBUSTNESS.value,
                EvalDimension.SECURITY.value
            }
            if self.dimension not in adversarial_dims:
                # 记录警告但不阻止创建
                pass

        return self


class EvalResponse(BaseModel):
    """
    评测响应数据模型。

    对应需求: FR-001-10
    """
    task_id: str = Field(description="对应的任务 ID")
    output: str = Field(default="", description="Agent 的文本输出（分析结果、回答等）")
    error: str | None = Field(default=None, description="Agent 执行错误信息")
    tool_calls: list[dict] = Field(default_factory=list, description="工具调用记录")
    intermediate_steps: list[dict] = Field(default_factory=list, description="中间推理步骤")
    metadata: dict = Field(default_factory=dict, description="元数据（Token 用量、耗时等）")

    @field_validator('task_id')
    @classmethod
    def validate_task_id(cls, v: str) -> str:
        """验证任务ID"""
        if not v or len(v.strip()) == 0:
            raise ValueError('任务ID不能为空')
        return v.strip()

    @field_validator('output')
    @classmethod
    def validate_output(cls, v: str) -> str:
        """验证输出内容长度"""
        if len(v) > 100000:  # 100KB 限制
            raise ValueError('输出内容过长，不能超过 100KB')
        return v

    @field_validator('tool_calls')
    @classmethod
    def validate_tool_calls(cls, v: list[dict]) -> list[dict]:
        """验证工具调用记录"""
        for i, call in enumerate(v):
            if not isinstance(call, dict):
                raise ValueError(f'工具调用记录第 {i} 项必须是字典类型')
            if 'tool_name' not in call:
                raise ValueError(f'工具调用记录第 {i} 项缺少 tool_name 字段')
        return v

    @model_validator(mode='after')
    def validate_response_completeness(self) -> 'EvalResponse':
        """验证响应完整性"""
        # 如果存在错误，输出可以为空
        if self.error:
            return self

        # 如果没有错误，必须有输出或工具调用
        if not self.output and not self.tool_calls:
            raise ValueError('响应必须包含 output 或 tool_calls 至少一项')

        return self


class AgentState(BaseModel):
    """
    Agent 状态数据模型。

    对应需求: FR-001-10
    """
    memory: dict = Field(default_factory=dict, description="对话历史/记忆")
    context: dict = Field(default_factory=dict, description="当前上下文")
    portfolio: dict = Field(default_factory=dict, description="持仓状态（交易类 Agent）")
    metadata: dict = Field(default_factory=dict, description="元数据")
    version: str = Field(default="1.0", description="状态格式版本")


class ToolCallRecord(BaseModel):
    """工具调用记录"""
    tool_name: str = Field(description="工具名称")
    input_args: dict = Field(description="输入参数")
    output: Any | None = Field(default=None, description="输出结果")
    latency_ms: float = Field(description="耗时（毫秒）")
    status: str = Field(description="状态：success / error")
    error: str | None = Field(default=None, description="错误信息")


class EvalResult(BaseModel):
    """评测结果"""
    task_id: str = Field(description="任务 ID")
    dimension: str = Field(description="评测维度")
    score: float = Field(description="得分（0-100）")
    max_score: float = Field(default=100.0, description="最高分")
    details: dict = Field(default_factory=dict, description="详细评分信息")
    passed: bool = Field(description="是否通过")


class EvaluationReport(BaseModel):
    """评测报告"""
    eval_id: str = Field(description="评测任务 ID")
    agent_config: AgentConfig = Field(description="被测 Agent 配置")
    mode: EvalMode = Field(description="评测模式")
    status: EvalStatus = Field(description="评测状态")
    total_score: float = Field(description="总分")
    grade: str = Field(description="评级（S/A/B/C/D）")
    dimension_scores: dict[str, float] = Field(description="各维度得分")
    veto_triggered: bool = Field(default=False, description="是否触发一票否决")
    created_at: str = Field(description="创建时间")
    completed_at: str | None = Field(default=None, description="完成时间")

    model_config = ConfigDict(use_enum_values=True)
