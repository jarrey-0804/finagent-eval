"""
API数据模型模块

提供REST API的请求和响应数据模型。
"""

import re
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, model_validator

# ============ 评测相关模型 ============

class EvaluationRequest(BaseModel):
    """评测请求"""
    agent_id: str = Field(..., description="Agent ID")
    agent_type: str = Field(default="langgraph", description="Agent类型")
    agent_config: dict = Field(default_factory=dict, description="Agent配置")
    eval_mode: str = Field(default="full", description="评测模式: quick/full")
    dimensions: list[str] | None = Field(None, description="评测维度")
    task_count: int | None = Field(None, description="任务数量")
    endpoint_url: str | None = Field(None, description="Agent HTTP端点URL")
    headers: dict | None = Field(None, description="HTTP请求头")

    @field_validator('agent_id')
    @classmethod
    def validate_agent_id(cls, v: str) -> str:
        """验证 Agent ID"""
        if not v or len(v.strip()) == 0:
            raise ValueError('Agent ID 不能为空')
        if len(v) > 128:
            raise ValueError('Agent ID 长度不能超过 128 字符')
        if not re.match(r'^[a-zA-Z0-9_\-\.]+$', v):
            raise ValueError('Agent ID 只能包含字母、数字、下划线、连字符和点')
        return v.strip()

    @field_validator('eval_mode')
    @classmethod
    def validate_eval_mode(cls, v: str) -> str:
        """验证评测模式"""
        valid_modes = {'quick', 'full'}
        if v not in valid_modes:
            raise ValueError(f'评测模式必须是以下之一: {valid_modes}')
        return v

    @field_validator('endpoint_url')
    @classmethod
    def validate_endpoint_url(cls, v: str | None) -> str | None:
        """验证 HTTP 端点 URL"""
        if v is None:
            return v
        if len(v) > 2048:
            raise ValueError('URL 长度不能超过 2048 字符')
        try:
            parsed = urlparse(v)
            if not parsed.scheme or parsed.scheme not in ('http', 'https'):
                raise ValueError('URL 必须使用 http 或 https 协议')
            if not parsed.netloc:
                raise ValueError('URL 必须包含主机名')
        except Exception as e:
            raise ValueError(f'无效的 URL 格式: {e}')
        return v

    @field_validator('task_count')
    @classmethod
    def validate_task_count(cls, v: int | None) -> int | None:
        """验证任务数量"""
        if v is None:
            return v
        if v < 1:
            raise ValueError('任务数量必须大于 0')
        if v > 1000:
            raise ValueError('任务数量不能超过 1000')
        return v

    @field_validator('headers')
    @classmethod
    def validate_headers(cls, v: dict | None) -> dict | None:
        """验证 HTTP 请求头"""
        if v is None:
            return v
        # 检查是否包含敏感信息
        sensitive_keys = {'authorization', 'x-api-key', 'api-key', 'token', 'password'}
        for key in v.keys():
            if key.lower() in sensitive_keys:
                # 允许存在，但记录警告（实际实现中）
                pass
        return v


class EvaluationResponse(BaseModel):
    """评测响应"""
    evaluation_id: str = Field(..., description="评测ID")
    status: str = Field(..., description="状态")
    message: str = Field(..., description="消息")
    created_at: datetime = Field(default_factory=datetime.now)


class EvaluationStatusResponse(BaseModel):
    """评测状态响应"""
    evaluation_id: str
    agent_id: str
    status: str
    current_stage: str
    progress: float
    started_at: datetime | None
    completed_at: datetime | None
    result: dict | None = None
    error: str | None = None


class EvaluationResultSummary(BaseModel):
    """评测结果摘要"""
    overall_score: float = Field(..., description="总体分数")
    overall_rating: str = Field(..., description="总体评级")
    total_tasks: int = Field(..., description="总任务数")
    passed_tasks: int = Field(..., description="通过任务数")
    pass_rate: float = Field(..., description="通过率")
    veto_count: int = Field(default=0, description="一票否决次数")


# ============ Agent相关模型 ============

class AgentRegistrationRequest(BaseModel):
    """Agent注册请求"""
    agent_id: str = Field(..., description="Agent ID")
    agent_name: str = Field(..., description="Agent名称")
    agent_type: str = Field(default="langgraph", description="Agent类型")
    description: str | None = Field(None, description="Agent描述")
    endpoint_url: str | None = Field(None, description="HTTP端点URL")
    config: dict = Field(default_factory=dict, description="Agent配置")

    @field_validator('agent_id')
    @classmethod
    def validate_agent_id(cls, v: str) -> str:
        """验证 Agent ID"""
        if not v or len(v.strip()) == 0:
            raise ValueError('Agent ID 不能为空')
        if len(v) > 128:
            raise ValueError('Agent ID 长度不能超过 128 字符')
        if not re.match(r'^[a-zA-Z0-9_\-\.]+$', v):
            raise ValueError('Agent ID 只能包含字母、数字、下划线、连字符和点')
        return v.strip()

    @field_validator('agent_name')
    @classmethod
    def validate_agent_name(cls, v: str) -> str:
        """验证 Agent 名称"""
        if not v or len(v.strip()) == 0:
            raise ValueError('Agent 名称不能为空')
        if len(v) > 128:
            raise ValueError('Agent 名称长度不能超过 128 字符')
        return v.strip()

    @field_validator('endpoint_url')
    @classmethod
    def validate_endpoint_url(cls, v: str | None) -> str | None:
        """验证 HTTP 端点 URL"""
        if v is None:
            return v
        if len(v) > 2048:
            raise ValueError('URL 长度不能超过 2048 字符')
        try:
            parsed = urlparse(v)
            if not parsed.scheme or parsed.scheme not in ('http', 'https'):
                raise ValueError('URL 必须使用 http 或 https 协议')
            if not parsed.netloc:
                raise ValueError('URL 必须包含主机名')
        except Exception as e:
            raise ValueError(f'无效的 URL 格式: {e}')
        return v


class AgentInfo(BaseModel):
    """Agent信息"""
    agent_id: str
    agent_name: str
    agent_type: str
    description: str | None
    status: str
    registered_at: datetime
    last_evaluation: datetime | None


class AgentListResponse(BaseModel):
    """Agent列表响应"""
    total: int
    agents: list[AgentInfo]


# ============ 任务相关模型 ============

class TaskGenerationRequest(BaseModel):
    """任务生成请求"""
    sources: list[str] | None = Field(None, description="数据源列表")
    task_count: int = Field(default=20, description="任务数量")
    eval_mode: str = Field(default="full", description="评测模式")
    difficulty_distribution: dict | None = Field(None, description="难度分布")


class TaskInfo(BaseModel):
    """任务信息"""
    task_id: str
    task_type: str
    query: str
    dimensions: list[str]
    difficulty: str
    source: str


class TaskListResponse(BaseModel):
    """任务列表响应"""
    total: int
    tasks: list[TaskInfo]


class DatasetInfo(BaseModel):
    """数据集信息"""
    name: str
    description: str
    task_count: int
    version: str = "1.0"


# ============ 报告相关模型 ============

class ReportRequest(BaseModel):
    """报告请求"""
    evaluation_id: str = Field(..., description="评测ID")
    format: str = Field(default="json", description="报告格式: json/markdown/html")
    include_details: bool = Field(default=True, description="是否包含详细结果")


class ReportResponse(BaseModel):
    """报告响应"""
    evaluation_id: str
    generated_at: datetime
    format: str
    summary: dict
    dimension_scores: dict
    recommendations: list[str]
    download_url: str | None = None


class ReportSummary(BaseModel):
    """报告摘要"""
    overall_score: float
    overall_rating: str
    total_tasks: int
    passed_tasks: int
    pass_rate: float
    veto_count: int


class DimensionScoreDetail(BaseModel):
    """维度分数详情"""
    dimension: str
    score: float
    confidence: float
    reasoning: str
    evidence: list[str]


class TaskScoreDetail(BaseModel):
    """任务分数详情"""
    task_id: str
    overall_score: float
    rating: str
    veto_triggered: bool
    dimension_scores: list[DimensionScoreDetail]


# ============ 对抗性测试相关模型 ============

class AdversarialTestRequest(BaseModel):
    """对抗性测试请求"""
    agent_id: str = Field(..., description="Agent ID")
    levels: list[str] = Field(
        default_factory=lambda: ["baseline", "noisy", "meta_cognitive", "adversarial"],
        description="测试等级"
    )
    attack_types: list[str] = Field(
        default_factory=lambda: ["prompt_injection", "jailbreak", "data_leakage", "compliance_bypass"],
        description="攻击类型"
    )
    attacks_per_level: int = Field(default=10, description="每级攻击数")


class AdversarialTestResponse(BaseModel):
    """对抗性测试响应"""
    test_id: str
    agent_id: str
    status: str
    total_attacks: int
    successful_attacks: int
    vulnerability_rate: float
    security_score: float
    recommendations: list[str]


# ============ 错误响应模型 ============

class ErrorResponse(BaseModel):
    """错误响应"""
    error: str = Field(..., description="错误类型")
    message: str = Field(..., description="错误消息")
    details: dict | None = Field(None, description="错误详情")
    timestamp: datetime = Field(default_factory=datetime.now)


# ============ 分页模型 ============

class PaginationParams(BaseModel):
    """分页参数"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")


class PaginatedResponse(BaseModel):
    """分页响应"""
    total: int
    page: int
    page_size: int
    total_pages: int
    items: list[Any]
