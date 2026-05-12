"""
端到端集成测试 — 快速评测模式

验证从任务生成到评分报告的完整评测流程。
"""

import pytest
import asyncio

from finagent.interface.models import (
    EvalTask, EvalResponse, TaskType, EvalDimension,
    EvalMode, AgentConfig,
)
from finagent.taskgen.generator import EvalTaskGenerator, TaskGeneratorConfig
from finagent.scoring.engine import ScoringEngine, ScoringConfig
from finagent.scoring.veto import VetoChecker
from finagent.scoring.rules import RuleBasedScorer
from finagent.report.generator import ReportGenerator, ReportFormat


class MockAgent:
    """模拟Agent用于测试"""
    
    def __init__(self, responses: dict = None):
        self._responses = responses or {}
    
    async def ainvoke(self, message: str, context: dict = None):
        task_id = context.get("task_id", "") if context else ""
        response = self._responses.get(task_id, self._default_response(message))
        return EvalResponse(
            task_id=task_id,
            output=response,
            tool_calls=[{"tool_name": "get_data", "args": {}, "success": True}],
        )
    
    def _default_response(self, message: str) -> str:
        return f"根据分析，{message}。该股票当前市盈率为15.2，市净率为2.1，ROE为18.5%。从财务指标来看，公司基本面良好。但请注意投资有风险，过往业绩不代表未来表现。"


class TestQuickEvalIntegration:
    """快速评测端到端集成测试"""
    
    @pytest.fixture
    def task_generator(self):
        config = TaskGeneratorConfig(
            tasks_per_source=3,
            max_total_tasks=10,
        )
        return EvalTaskGenerator(config)
    
    @pytest.fixture
    def scoring_engine(self):
        return ScoringEngine()
    
    @pytest.fixture
    def mock_agent(self):
        return MockAgent()
    
    def test_task_generation(self, task_generator):
        """测试1: 任务生成"""
        tasks = task_generator.generate_tasks(n_tasks=5)
        assert len(tasks) > 0
        for task in tasks:
            assert task.task_id.startswith("task_")
            assert len(task.input_data.get("query", "")) > 0
    
    def test_scoring_pipeline(self, task_generator, scoring_engine):
        """测试2: 评分流水线"""
        tasks = task_generator.generate_tasks(n_tasks=3)
        
        for task in tasks:
            response = EvalResponse(
                task_id=task.task_id,
                output="根据分析，该股票基本面良好。ROE为18.5%，毛利率为65%。请注意投资有风险。",
                tool_calls=[{"tool_name": "get_data", "args": {}, "success": True}],
            )
            
            score = scoring_engine.score_task(task, response)
            assert score.overall_score >= 0
            assert score.overall_score <= 100
    
    def test_veto_checker(self):
        """测试3: 否决检查"""
        checker = VetoChecker(threshold=30.0)
        
        # 测试合规性否决
        task = EvalTask(
            task_id="veto_test",
            task_type=TaskType.KNOWLEDGE_QA,
            dimension=EvalDimension.COMPLIANCE,
            input_data={"query": "这是一个测试问题"},
        )
        
        response_safe = EvalResponse(
            task_id="veto_test",
            output="投资有风险，请谨慎决策。",
        )
        
        result_safe = checker.check(task, response_safe, {"compliance": 85.0})
        assert result_safe.vetoed is False
        
        # 测试触发否决
        result_veto = checker.check(task, response_safe, {"compliance": 20.0})
        assert result_veto.vetoed is True
    
    def test_rule_based_scorer(self, task_generator):
        """测试4: 基于规则的评分"""
        scorer = RuleBasedScorer()
        tasks = task_generator.generate_tasks(n_tasks=1)
        task = tasks[0]
        
        response = EvalResponse(
            task_id=task.task_id,
            output="根据财务数据分析，贵州茅台2024年Q3营收388亿元，同比增长15%。建议关注风险。",
            tool_calls=[{"tool_name": "get_financial", "args": {"symbol": "600519"}, "success": True}],
        )
        
        results = scorer.evaluate(task, response)
        assert len(results) > 0
        for result in results:
            assert 0 <= result.score <= 100
    
    def test_report_generation(self, task_generator, scoring_engine):
        """测试5: 报告生成"""
        generator = ReportGenerator()
        tasks = task_generator.generate_tasks(n_tasks=3)
        
        # 模拟评测数据
        eval_data = {
            "agent_id": "test-agent",
            "eval_mode": "quick",
            "generated_at": "2026-05-08T12:00:00",
            "summary": {
                "overall_score": 78.5,
                "overall_rating": "B",
                "total_tasks": 3,
                "passed_tasks": 2,
                "pass_rate": 0.667,
                "veto_count": 0,
            },
            "dimension_scores": {
                "accuracy": 82.0,
                "completeness": 75.0,
                "reasoning": 78.0,
                "tool_usage": 85.0,
                "compliance": 72.0,
            },
            "task_details": [
                {"task_id": "t1", "overall_score": 85, "rating": "A", "veto_triggered": False},
                {"task_id": "t2", "overall_score": 72, "rating": "B", "veto_triggered": False},
                {"task_id": "t3", "overall_score": 65, "rating": "C", "veto_triggered": False},
            ],
            "recommendations": [
                "推理能力有提升空间",
                "建议加强风险提示",
            ],
        }
        
        # JSON格式
        report_json = generator.generate(eval_data, ReportFormat.JSON)
        assert "overall_score" in report_json
        
        # Markdown格式
        report_md = generator.generate(eval_data, ReportFormat.MARKDOWN)
        assert "评测报告" in report_md
        assert "78.5" in report_md
        
        # HTML格式
        report_html = generator.generate(eval_data, ReportFormat.HTML)
        assert "<html" in report_html
        assert "78.5" in report_html
    
    @pytest.mark.asyncio
    async def test_mock_agent_execution(self, mock_agent):
        """测试6: 模拟Agent执行"""
        response = await mock_agent.ainvoke(
            "分析贵州茅台",
            {"task_id": "test_001"},
        )
        assert response.output is not None
        assert len(response.output) > 0
    
    def test_dataset_stats(self, task_generator):
        """测试7: 数据集统计"""
        stats = task_generator.get_dataset_stats()
        assert len(stats) == 5
        for source, info in stats.items():
            assert "name" in info
            assert "count" in info
