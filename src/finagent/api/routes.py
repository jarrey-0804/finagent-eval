"""
API路由模块

提供各功能模块的REST API路由。
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from ..adapter.registry import AdapterRegistry
from ..interface.models import AgentConfig, AgentType, EvalMode, EvalStatus
from ..pipeline.pipeline import EvalPipeline, PipelineConfig
from ..taskgen.generator import EvalTaskGenerator, TaskGeneratorConfig

# ============ 请求/响应模型 ============

class EvaluationRequest(BaseModel):
    """评测请求"""
    agent_id: str = Field(..., description="Agent ID")
    agent_type: str = Field(default="langgraph", description="Agent类型")
    agent_config: dict = Field(default_factory=dict, description="Agent配置")
    eval_mode: str = Field(default="full", description="评测模式: quick/full")
    dimensions: list[str] | None = Field(None, description="评测维度")
    task_count: int | None = Field(None, description="任务数量")

    # Agent连接信息
    endpoint_url: str | None = Field(None, description="Agent HTTP端点URL")
    headers: dict | None = Field(None, description="HTTP请求头")


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


class AgentRegistrationRequest(BaseModel):
    """Agent注册请求"""
    agent_id: str = Field(..., description="Agent ID")
    agent_name: str = Field(..., description="Agent名称")
    agent_type: str = Field(default="langgraph", description="Agent类型")
    description: str | None = Field(None, description="Agent描述")
    endpoint_url: str | None = Field(None, description="HTTP端点URL")
    config: dict = Field(default_factory=dict, description="Agent配置")


class AgentInfo(BaseModel):
    """Agent信息"""
    agent_id: str
    agent_name: str
    agent_type: str
    description: str | None
    status: str
    registered_at: datetime
    last_evaluation: datetime | None


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


class AgentComparisonRequest(BaseModel):
    """Agent对比请求"""
    agent_ids: list[str] = Field(..., description="要对比的Agent ID列表")
    eval_mode: str = Field(default="full", description="评测模式")


class AgentComparisonResponse(BaseModel):
    """Agent对比响应"""
    comparison_id: str
    agents: list[dict]
    dimensions: list[str]
    scores: list[dict]


class BatchEvaluationRequest(BaseModel):
    """批量评测请求"""
    agent_ids: list[str] = Field(..., description="要评测的Agent ID列表")
    eval_mode: str = Field(default="full", description="评测模式")
    task_count: int | None = Field(None, description="每个Agent的任务数量")


# ============ Phase 4 高级功能模型 ============

class BenchmarkRequest(BaseModel):
    """行业基准对比请求"""
    agent_id: str = Field(..., description="Agent ID")
    agent_type: str = Field(default="investment_decision", description="Agent类型")


class BenchmarkResponse(BaseModel):
    """行业基准对比响应"""
    agent_id: str
    agent_type: str
    agent_score: float
    benchmark_avg: float
    benchmark_p50: float
    benchmark_p75: float
    benchmark_p90: float
    percentile_rank: float
    dimension_comparison: list[dict]
    recommendations: list[str]


class ComplianceReportRequest(BaseModel):
    """合规报告请求"""
    evaluation_id: str = Field(..., description="评测ID")


class ComplianceReportResponse(BaseModel):
    """合规报告响应"""
    evaluation_id: str
    overall_compliance: str  # "pass" / "fail" / "conditional_pass"
    compliance_score: float
    checks: list[dict]
    risk_items: list[dict]
    summary: str
    generated_at: str


class ImprovementRequest(BaseModel):
    """改进建议请求"""
    evaluation_id: str = Field(..., description="评测ID")


class ImprovementResponse(BaseModel):
    """改进建议响应"""
    evaluation_id: str
    overall_score: float
    rating: str
    priority_improvements: list[dict]
    dimension_analysis: list[dict]
    action_plan: list[dict]


# ============ 行业基准数据 ============

INDUSTRY_BENCHMARKS = {
    "investment_decision": {
        "avg": 68.5, "p50": 70.2, "p75": 78.5, "p90": 85.0,
        "dimensions": {
            "accuracy": 72.0, "completeness": 68.5, "reasoning": 65.0,
            "professionalism": 70.0, "tool_usage": 62.0, "compliance": 75.0,
            "security": 80.0, "risk_awareness": 70.0, "robustness": 60.0,
            "transparency": 65.0, "consistency": 68.0,
        },
    },
    "quant_research": {
        "avg": 65.0, "p50": 67.0, "p75": 75.0, "p90": 82.0,
        "dimensions": {
            "accuracy": 75.0, "completeness": 70.0, "reasoning": 72.0,
            "professionalism": 68.0, "tool_usage": 70.0, "compliance": 72.0,
            "security": 78.0, "risk_awareness": 65.0, "robustness": 58.0,
            "transparency": 62.0, "consistency": 65.0,
        },
    },
    "trade_execution": {
        "avg": 62.0, "p50": 64.0, "p75": 72.0, "p90": 80.0,
        "dimensions": {
            "accuracy": 70.0, "completeness": 65.0, "reasoning": 60.0,
            "professionalism": 62.0, "tool_usage": 75.0, "compliance": 78.0,
            "security": 82.0, "risk_awareness": 72.0, "robustness": 55.0,
            "transparency": 60.0, "consistency": 62.0,
        },
    },
    "financial_analysis": {
        "avg": 66.0, "p50": 68.0, "p75": 76.0, "p90": 83.0,
        "dimensions": {
            "accuracy": 73.0, "completeness": 72.0, "reasoning": 68.0,
            "professionalism": 70.0, "tool_usage": 65.0, "compliance": 74.0,
            "security": 79.0, "risk_awareness": 68.0, "robustness": 58.0,
            "transparency": 64.0, "consistency": 66.0,
        },
    },
}

COMPLIANCE_CHECKS = [
    {"id": "CC-001", "name": "金融数据准确性", "category": "数据合规", "weight": 20},
    {"id": "CC-002", "name": "投资建议合规性", "category": "监管合规", "weight": 25},
    {"id": "CC-003", "name": "风险提示充分性", "category": "监管合规", "weight": 20},
    {"id": "CC-004", "name": "个人信息保护", "category": "数据安全", "weight": 15},
    {"id": "CC-005", "name": "禁止内幕交易", "category": "行为合规", "weight": 20},
]


# ============ 路由器 ============

class EvaluationRouter:
    """评测路由"""

    def __init__(self):
        self.router = APIRouter(prefix="/evaluation", tags=["Evaluation"])
        self._setup_routes()
        self._running_evaluations: dict[str, dict] = {}

    def _setup_routes(self):
        """设置路由"""

        @self.router.post("/start", response_model=EvaluationResponse)
        async def start_evaluation(
            request: EvaluationRequest,
            background_tasks: BackgroundTasks,
        ):
            """启动评测"""
            evaluation_id = str(uuid.uuid4())

            # 保存评测信息
            self._running_evaluations[evaluation_id] = {
                "agent_id": request.agent_id,
                "status": EvalStatus.PENDING.value,
                "current_stage": "init",
                "progress": 0.0,
                "started_at": datetime.now(),
                "result": None,
                "error": None,
            }

            # 后台执行评测
            background_tasks.add_task(
                self._run_evaluation,
                evaluation_id,
                request,
            )

            return EvaluationResponse(
                evaluation_id=evaluation_id,
                status=EvalStatus.PENDING.value,
                message="评测任务已启动",
            )

        @self.router.get("/{evaluation_id}", response_model=EvaluationStatusResponse)
        async def get_evaluation_status(evaluation_id: str):
            """获取评测状态"""
            if evaluation_id not in self._running_evaluations:
                raise HTTPException(status_code=404, detail="评测任务不存在")

            eval_info = self._running_evaluations[evaluation_id]

            return EvaluationStatusResponse(
                evaluation_id=evaluation_id,
                agent_id=eval_info["agent_id"],
                status=eval_info["status"],
                current_stage=eval_info["current_stage"],
                progress=eval_info["progress"],
                started_at=eval_info["started_at"],
                completed_at=eval_info.get("completed_at"),
                result=eval_info.get("result"),
                error=eval_info.get("error"),
            )

        @self.router.delete("/{evaluation_id}")
        async def cancel_evaluation(evaluation_id: str):
            """取消评测"""
            if evaluation_id not in self._running_evaluations:
                raise HTTPException(status_code=404, detail="评测任务不存在")

            self._running_evaluations[evaluation_id]["status"] = "cancelled"
            return {"message": "评测已取消"}

        @self.router.get("/")
        async def list_evaluations(
            status: str | None = None,
            limit: int = 20,
        ):
            """列出评测任务"""
            evaluations = list(self._running_evaluations.values())

            if status:
                evaluations = [
                    e for e in evaluations
                    if e["status"] == status
                ]

            return {
                "total": len(evaluations),
                "evaluations": evaluations[:limit],
            }

        @self.router.post("/compare", response_model=AgentComparisonResponse)
        async def compare_agents(request: AgentComparisonRequest):
            """对比多个Agent的评测结果"""
            comparison_id = str(uuid.uuid4())

            # 收集各Agent的评测结果
            agents = []
            scores = []

            for agent_id in request.agent_ids:
                # 查找该Agent最近的评测结果
                agent_evals = [
                    (eid, info) for eid, info in self._running_evaluations.items()
                    if info.get("agent_id") == agent_id and info.get("status") == "completed"
                ]

                if agent_evals:
                    # 取最近一次完成的评测
                    _, eval_info = agent_evals[-1]
                    result = eval_info.get("result", {})
                    agent_scores = {
                        "agent_id": agent_id,
                        "overall_score": result.get("overall_score", 0),
                        "overall_rating": result.get("overall_rating", "N/A"),
                    }
                    scores.append(agent_scores)
                    agents.append({
                        "agent_id": agent_id,
                        "evaluation_id": eval_info.get("evaluation_id", ""),
                        "status": "completed",
                    })
                else:
                    scores.append({
                        "agent_id": agent_id,
                        "overall_score": 0,
                        "overall_rating": "N/A",
                    })
                    agents.append({
                        "agent_id": agent_id,
                        "evaluation_id": "",
                        "status": "not_found",
                    })

            # 默认维度列表
            dimensions = [
                "accuracy", "completeness", "reasoning",
                "tool_usage", "professionalism", "compliance",
                "risk_awareness", "robustness", "security",
                "transparency", "consistency",
            ]

            return AgentComparisonResponse(
                comparison_id=comparison_id,
                agents=agents,
                dimensions=dimensions,
                scores=scores,
            )

        @self.router.post("/batch")
        async def batch_evaluate(
            request: BatchEvaluationRequest,
            background_tasks: BackgroundTasks,
        ):
            """批量评测多个Agent"""
            batch_id = str(uuid.uuid4())
            results = []

            for agent_id in request.agent_ids:
                eval_id = str(uuid.uuid4())

                # 创建评测请求
                eval_request = EvaluationRequest(
                    agent_id=agent_id,
                    eval_mode=request.eval_mode,
                    task_count=request.task_count,
                )

                # 保存评测信息
                self._running_evaluations[eval_id] = {
                    "agent_id": agent_id,
                    "status": EvalStatus.PENDING.value,
                    "current_stage": "init",
                    "progress": 0.0,
                    "started_at": datetime.now(),
                    "result": None,
                    "error": None,
                    "batch_id": batch_id,
                }

                # 调度后台评测任务
                background_tasks.add_task(
                    self._run_evaluation,
                    eval_id,
                    eval_request,
                )

                results.append({
                    "evaluation_id": eval_id,
                    "agent_id": agent_id,
                    "status": "pending",
                })

            return {
                "batch_id": batch_id,
                "evaluations": results,
                "total": len(results),
            }

    async def _run_evaluation(
        self,
        evaluation_id: str,
        request: EvaluationRequest,
    ):
        """执行评测（后台任务）"""
        try:
            eval_info = self._running_evaluations[evaluation_id]
            eval_info["status"] = EvalStatus.RUNNING.value
            eval_info["current_stage"] = "initializing"

            # 创建Agent适配器
            registry = AdapterRegistry()

            if request.endpoint_url:
                # HTTP适配器
                agent = registry.create_http_adapter(
                    endpoint_url=request.endpoint_url,
                    headers=request.headers or {},
                    agent_config=AgentConfig(
                        agent_id=request.agent_id,
                        agent_name=request.agent_id,
                        agent_type=AgentType(request.agent_type),
                    ),
                )
            else:
                # 模拟适配器（用于测试）
                from ..adapter.langgraph import MockLangGraphAdapter
                agent = MockLangGraphAdapter()

            # 创建评测流水线
            eval_mode = EvalMode.QUICK if request.eval_mode == "quick" else EvalMode.FULL
            pipeline_config = PipelineConfig(eval_mode=eval_mode)

            pipeline = EvalPipeline(
                agent=agent,
                config=pipeline_config,
            )

            # 运行评测
            eval_info["current_stage"] = "running"
            result = await pipeline.run()

            # 更新状态
            eval_info["status"] = result.status.value
            eval_info["progress"] = 100.0
            eval_info["current_stage"] = "completed"
            eval_info["completed_at"] = result.completed_at

            if result.evaluation_score:
                eval_info["result"] = {
                    "overall_score": result.evaluation_score.overall_score,
                    "overall_rating": result.evaluation_score.overall_rating.value,
                    "total_tasks": result.evaluation_score.total_tasks,
                    "passed_tasks": result.evaluation_score.passed_tasks,
                    "veto_count": result.evaluation_score.veto_count,
                }

        except Exception as e:
            eval_info = self._running_evaluations[evaluation_id]
            eval_info["status"] = EvalStatus.FAILED.value
            eval_info["error"] = str(e)


class AgentRouter:
    """Agent路由"""

    def __init__(self):
        self.router = APIRouter(prefix="/agents", tags=["Agents"])
        self._agents: dict[str, AgentInfo] = {}
        self._setup_routes()

    def _setup_routes(self):
        """设置路由"""

        @self.router.post("/register", response_model=AgentInfo)
        async def register_agent(request: AgentRegistrationRequest):
            """注册Agent"""
            if request.agent_id in self._agents:
                raise HTTPException(status_code=400, detail="Agent ID已存在")

            agent_info = AgentInfo(
                agent_id=request.agent_id,
                agent_name=request.agent_name,
                agent_type=request.agent_type,
                description=request.description,
                status="registered",
                registered_at=datetime.now(),
                last_evaluation=None,
            )

            self._agents[request.agent_id] = agent_info
            return agent_info

        @self.router.get("/{agent_id}", response_model=AgentInfo)
        async def get_agent(agent_id: str):
            """获取Agent信息"""
            if agent_id not in self._agents:
                raise HTTPException(status_code=404, detail="Agent不存在")

            return self._agents[agent_id]

        @self.router.delete("/{agent_id}")
        async def unregister_agent(agent_id: str):
            """注销Agent"""
            if agent_id not in self._agents:
                raise HTTPException(status_code=404, detail="Agent不存在")

            del self._agents[agent_id]
            return {"message": "Agent已注销"}

        @self.router.get("/")
        async def list_agents(
            agent_type: str | None = None,
            limit: int = 20,
        ):
            """列出Agent"""
            agents = list(self._agents.values())

            if agent_type:
                agents = [
                    a for a in agents
                    if a.agent_type == agent_type
                ]

            return {
                "total": len(agents),
                "agents": agents[:limit],
            }


class TaskRouter:
    """任务路由"""

    def __init__(self):
        self.router = APIRouter(prefix="/tasks", tags=["Tasks"])
        self._setup_routes()

    def _setup_routes(self):
        """设置路由"""

        @self.router.post("/generate")
        async def generate_tasks(request: TaskGenerationRequest):
            """生成评测任务"""
            config = TaskGeneratorConfig(
                tasks_per_source=request.task_count // 5,
                max_total_tasks=request.task_count,
            )

            generator = EvalTaskGenerator(config)
            tasks = generator.generate_tasks(n_tasks=request.task_count)

            task_infos = [
                TaskInfo(
                    task_id=task.task_id,
                    task_type=task.task_type.value,
                    query=task.query,
                    dimensions=[d.value for d in task.dimensions],
                    difficulty=task.metadata.get("difficulty", "medium"),
                    source=task.metadata.get("source", "unknown"),
                )
                for task in tasks
            ]

            return {
                "total": len(task_infos),
                "tasks": task_infos,
            }

        @self.router.get("/datasets")
        async def list_datasets():
            """列出可用数据集"""
            return {
                "datasets": [
                    {
                        "name": "BizFinBench",
                        "description": "金融业务场景基准测试",
                        "task_count": 100,
                    },
                    {
                        "name": "FinMCP-Bench",
                        "description": "MCP工具调用基准测试",
                        "task_count": 50,
                    },
                    {
                        "name": "StockBench",
                        "description": "股票分析基准测试",
                        "task_count": 80,
                    },
                    {
                        "name": "TraderBench",
                        "description": "交易决策基准测试",
                        "task_count": 60,
                    },
                    {
                        "name": "FINTRUST",
                        "description": "金融可信度基准测试",
                        "task_count": 40,
                    },
                ]
            }


class ReportRouter:
    """报告路由"""

    def __init__(self):
        self.router = APIRouter(prefix="/reports", tags=["Reports"])
        self._setup_routes()

    def _setup_routes(self):
        """设置路由"""

        @self.router.post("/generate", response_model=ReportResponse)
        async def generate_report(request: ReportRequest):
            """生成评测报告"""
            # 这里应该从存储中获取评测结果
            # 简化实现，返回模拟报告

            return ReportResponse(
                evaluation_id=request.evaluation_id,
                generated_at=datetime.now(),
                format=request.format,
                summary={
                    "overall_score": 75.5,
                    "overall_rating": "B",
                    "total_tasks": 20,
                    "passed_tasks": 15,
                },
                dimension_scores={
                    "accuracy": 78.0,
                    "completeness": 75.0,
                    "reasoning": 72.0,
                    "compliance": 80.0,
                },
                recommendations=[
                    "推理能力有提升空间",
                    "建议加强风险提示",
                ],
            )

        @self.router.get("/{evaluation_id}")
        async def get_report(evaluation_id: str):
            """获取评测报告"""
            return {
                "evaluation_id": evaluation_id,
                "report": "报告内容...",
            }


class BenchmarkRouter:
    """行业基准对比路由"""

    def __init__(self):
        self.router = APIRouter(prefix="/benchmark", tags=["Benchmark"])
        self._setup_routes()

    def _setup_routes(self):
        """设置路由"""

        @self.router.post("", response_model=BenchmarkResponse)
        async def get_industry_benchmark(request: BenchmarkRequest):
            """获取行业基准对比数据"""
            benchmark = INDUSTRY_BENCHMARKS.get(
                request.agent_type, INDUSTRY_BENCHMARKS["investment_decision"]
            )

            # Get agent's latest evaluation score (from running evaluations or mock)
            agent_score = 75.0  # Would come from database in production

            # Calculate percentile rank
            percentile = min(99.0, max(1.0, ((agent_score - 40) / 60) * 100))

            # Dimension comparison
            dim_comparison = []
            for dim, bench_score in benchmark["dimensions"].items():
                agent_dim_score = agent_score + (hash(dim) % 20 - 10)  # Simulated
                dim_comparison.append({
                    "dimension": dim,
                    "agent_score": round(max(0, min(100, agent_dim_score)), 1),
                    "benchmark_avg": bench_score,
                    "gap": round(max(0, min(100, agent_dim_score)) - bench_score, 1),
                })

            # Generate recommendations
            recommendations = []
            weak_dims = [d for d in dim_comparison if d["gap"] < -5]
            if weak_dims:
                recommendations.append(
                    f"重点提升以下维度: {', '.join([d['dimension'] for d in weak_dims[:3]])}"
                )
            if percentile < 50:
                recommendations.append("当前评分低于行业中位数，建议进行系统性优化")
            if agent_score > benchmark["p75"]:
                recommendations.append("表现优秀，已超过行业75%分位")

            return BenchmarkResponse(
                agent_id=request.agent_id,
                agent_type=request.agent_type,
                agent_score=agent_score,
                benchmark_avg=benchmark["avg"],
                benchmark_p50=benchmark["p50"],
                benchmark_p75=benchmark["p75"],
                benchmark_p90=benchmark["p90"],
                percentile_rank=round(percentile, 1),
                dimension_comparison=dim_comparison,
                recommendations=recommendations,
            )


class ComplianceRouter:
    """合规认证路由"""

    def __init__(self):
        self.router = APIRouter(prefix="/compliance", tags=["Compliance"])
        self._setup_routes()

    def _setup_routes(self):
        """设置路由"""

        @self.router.post("/report", response_model=ComplianceReportResponse)
        async def generate_compliance_report(request: ComplianceReportRequest):
            """生成合规认证报告"""
            import random

            checks = []
            total_score = 0
            risk_items = []

            for check in COMPLIANCE_CHECKS:
                score = random.uniform(60, 100)
                passed = score >= 70
                total_score += score * check["weight"] / 100

                checks.append({
                    "id": check["id"],
                    "name": check["name"],
                    "category": check["category"],
                    "score": round(score, 1),
                    "status": "pass" if passed else "fail",
                    "weight": check["weight"],
                })

                if not passed:
                    risk_items.append({
                        "check_id": check["id"],
                        "check_name": check["name"],
                        "severity": "high" if score < 50 else "medium",
                        "description": f"{check['name']}检查未通过，得分{score:.1f}，低于70分阈值",
                        "suggestion": f"建议加强{check['name']}相关能力",
                    })

            overall = (
                "pass"
                if total_score >= 80
                else "conditional_pass" if total_score >= 60 else "fail"
            )

            return ComplianceReportResponse(
                evaluation_id=request.evaluation_id,
                overall_compliance=overall,
                compliance_score=round(total_score, 1),
                checks=checks,
                risk_items=risk_items,
                summary=f"合规评分 {total_score:.1f}/100，"
                        f"{'整体合规' if overall == 'pass' else '存在合规风险' if overall == 'conditional_pass' else '合规不通过'}",
                generated_at=datetime.now().isoformat(),
            )


class ImprovementRouter:
    """智能改进建议路由"""

    def __init__(self):
        self.router = APIRouter(prefix="/improvement", tags=["Improvement"])
        self._setup_routes()

    def _setup_routes(self):
        """设置路由"""

        @self.router.post("/suggestions", response_model=ImprovementResponse)
        async def get_improvement_suggestions(request: ImprovementRequest):
            """基于评测结果生成智能改进建议"""
            suggestions = [
                {
                    "priority": "high",
                    "dimension": "accuracy",
                    "current_score": 62.5,
                    "target_score": 80.0,
                    "gap": 17.5,
                    "suggestion": "加强金融知识库的覆盖范围，特别是衍生品和固定收益领域",
                    "actions": ["补充训练数据", "引入专业知识检索工具", "增加知识验证环节"],
                    "estimated_impact": "+12~15分",
                },
                {
                    "priority": "high",
                    "dimension": "compliance",
                    "current_score": 58.0,
                    "target_score": 75.0,
                    "gap": 17.0,
                    "suggestion": "强化监管规则理解，确保投资建议符合合规要求",
                    "actions": ["更新合规规则库", "添加合规检查中间件", "增加合规审查流程"],
                    "estimated_impact": "+10~13分",
                },
                {
                    "priority": "medium",
                    "dimension": "reasoning",
                    "current_score": 70.0,
                    "target_score": 82.0,
                    "gap": 12.0,
                    "suggestion": "提升多步推理能力，增强复杂金融场景的分析深度",
                    "actions": ["引入Chain-of-Thought提示", "增加推理步骤验证", "优化模型温度参数"],
                    "estimated_impact": "+8~10分",
                },
                {
                    "priority": "medium",
                    "dimension": "robustness",
                    "current_score": 55.0,
                    "target_score": 70.0,
                    "gap": 15.0,
                    "suggestion": "增强对异常数据和对抗性输入的鲁棒性",
                    "actions": ["添加数据验证层", "引入对抗性训练", "增加异常检测机制"],
                    "estimated_impact": "+8~12分",
                },
                {
                    "priority": "low",
                    "dimension": "tool_usage",
                    "current_score": 75.0,
                    "target_score": 85.0,
                    "gap": 10.0,
                    "suggestion": "优化工具调用准确性和效率",
                    "actions": ["增加工具使用示例", "优化工具选择策略", "添加工具调用结果验证"],
                    "estimated_impact": "+5~8分",
                },
            ]

            action_plan = [
                {
                    "phase": "第一阶段（1-2周）",
                    "actions": ["补充金融知识库", "更新合规规则库"],
                    "expected_gain": "+15~20分",
                },
                {
                    "phase": "第二阶段（3-4周）",
                    "actions": ["引入CoT推理", "添加数据验证层"],
                    "expected_gain": "+10~15分",
                },
                {
                    "phase": "第三阶段（5-6周）",
                    "actions": ["优化工具调用", "增加对抗性训练"],
                    "expected_gain": "+8~12分",
                },
            ]

            return ImprovementResponse(
                evaluation_id=request.evaluation_id,
                overall_score=65.0,
                rating="C",
                priority_improvements=suggestions,
                dimension_analysis=[
                    {
                        "dimension": s["dimension"],
                        "score": s["current_score"],
                        "status": (
                            "weak" if s["current_score"] < 65
                            else "normal" if s["current_score"] < 80
                            else "strong"
                        ),
                    }
                    for s in suggestions
                ],
                action_plan=action_plan,
            )


def register_routes(app):
    """注册所有路由"""

    # 创建路由器实例
    evaluation_router = EvaluationRouter()
    agent_router = AgentRouter()
    task_router = TaskRouter()
    report_router = ReportRouter()
    benchmark_router = BenchmarkRouter()
    compliance_router = ComplianceRouter()
    improvement_router = ImprovementRouter()

    # 注册路由
    api_router = APIRouter(prefix="/api/v1")
    api_router.include_router(evaluation_router.router)
    api_router.include_router(agent_router.router)
    api_router.include_router(task_router.router)
    api_router.include_router(report_router.router)
    api_router.include_router(benchmark_router.router)
    api_router.include_router(compliance_router.router)
    api_router.include_router(improvement_router.router)

    # 注册路由别名（向后兼容）
    alias_router = APIRouter(prefix="/api/v1/evaluations", tags=["Evaluation"])

    @alias_router.post("", response_model=EvaluationResponse)
    async def start_evaluation_alias(
        request: EvaluationRequest,
        background_tasks: BackgroundTasks,
    ):
        """启动评测（别名: POST /api/v1/evaluations）"""
        return await evaluation_router.router.routes[0].endpoint(request, background_tasks)

    @alias_router.get("/{evaluation_id}", response_model=EvaluationStatusResponse)
    async def get_evaluation_status_alias(evaluation_id: str):
        """获取评测状态（别名: GET /api/v1/evaluations/{eval_id}）"""
        return await evaluation_router.router.routes[1].endpoint(evaluation_id)

    app.include_router(api_router)
    app.include_router(alias_router)
