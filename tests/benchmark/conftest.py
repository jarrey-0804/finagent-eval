"""
conftest.py — 性能测试与压力测试共享 fixtures

提供评测流水线各组件的预配置实例，以及辅助工具函数。
"""

import sys
import time
import random
from pathlib import Path
from typing import Optional

import pytest

# 确保项目根目录在 Python 路径中
project_root = Path(__file__).parent.parent.parent / "src"
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from finagent.interface.models import (
    EvalTask, EvalResponse, TaskType, EvalDimension,
    EvalMode, AgentConfig,
)
from finagent.taskgen.generator import EvalTaskGenerator, TaskGeneratorConfig
from finagent.scoring.engine import ScoringEngine, ScoringConfig
from finagent.scoring.veto import VetoChecker
from finagent.scoring.rules import RuleBasedScorer
from finagent.report.generator import ReportGenerator, ReportFormat
from finagent.monitor.metrics import MetricsCollector, MetricsConfig
from finagent.pipeline.scheduler import (
    EvaluationScheduler, SchedulerConfig, TaskPriority,
)
from finagent.pipeline.quota import ResourceQuota, QuotaConfig


# ============================================================
# 评测数据构建辅助
# ============================================================

@pytest.fixture
def sample_tasks():
    """
    预生成一批评测任务，避免在性能测试中重复生成。

    Returns:
        list[EvalTask]: 100 个预生成的评测任务
    """
    config = TaskGeneratorConfig(
        tasks_per_source=20,
        max_total_tasks=100,
        random_seed=42,
    )
    generator = EvalTaskGenerator(config)
    return generator.generate_tasks(n_tasks=100)


@pytest.fixture
def sample_responses(sample_tasks):
    """
    为预生成的任务构造对应的模拟评测响应。

    Returns:
        list[EvalResponse]: 与 sample_tasks 一一对应的响应列表
    """
    responses = []
    for task in sample_tasks:
        responses.append(EvalResponse(
            task_id=task.task_id,
            output=(
                "根据财务数据分析，该股票2024年Q3营收388亿元，同比增长15%。"
                "净利润率22.5%，ROE为18.5%。建议关注市场风险，投资需谨慎。"
            ),
            tool_calls=[
                {"name": "get_financial", "args": {"symbol": "600519"}, "success": True},
                {"name": "get_market_data", "args": {"period": "1y"}, "success": True},
            ],
        ))
    return responses


@pytest.fixture
def sample_eval_data():
    """
    构造一份完整的评测数据字典，用于报告生成测试。

    Returns:
        dict: 包含摘要、维度评分、任务详情和建议的评测数据
    """
    return {
        "agent_id": "bench-agent",
        "eval_mode": "full",
        "generated_at": "2026-05-09T12:00:00",
        "summary": {
            "overall_score": 78.5,
            "overall_rating": "B",
            "total_tasks": 10,
            "passed_tasks": 7,
            "pass_rate": 0.7,
            "veto_count": 1,
        },
        "dimension_scores": {
            "accuracy": 82.0,
            "completeness": 75.0,
            "reasoning": 78.0,
            "tool_usage": 85.0,
            "professionalism": 80.0,
            "compliance": 72.0,
            "risk_awareness": 70.0,
            "robustness": 76.0,
            "security": 88.0,
            "transparency": 74.0,
            "consistency": 80.0,
        },
        "task_details": [
            {
                "task_id": f"t{i}",
                "overall_score": random.randint(55, 95),
                "rating": random.choice(["A", "B", "C", "D"]),
                "veto_triggered": False,
            }
            for i in range(10)
        ],
        "recommendations": [
            "推理能力有提升空间",
            "建议加强风险提示",
            "工具调用覆盖率可进一步提高",
        ],
    }


# ============================================================
# 组件 Fixtures
# ============================================================

@pytest.fixture
def task_generator():
    """任务生成器实例（快速模式，少量任务）"""
    config = TaskGeneratorConfig(
        tasks_per_source=5,
        max_total_tasks=50,
        random_seed=42,
    )
    return EvalTaskGenerator(config)


@pytest.fixture
def scoring_engine():
    """评分引擎实例（默认配置）"""
    return ScoringEngine()


@pytest.fixture
def veto_checker():
    """否决检查器实例"""
    return VetoChecker(threshold=30.0)


@pytest.fixture
def rule_scorer():
    """基于规则的评分器实例"""
    return RuleBasedScorer()


@pytest.fixture
def report_generator():
    """报告生成器实例"""
    return ReportGenerator(include_details=True)


@pytest.fixture
def metrics_collector():
    """指标采集器实例（预填充数据）"""
    collector = MetricsCollector(MetricsConfig(enabled=True))

    # 预填充一些指标数据，模拟真实场景
    for i in range(20):
        collector.record_evaluation_start(f"agent_{i % 5}", "full")
        collector.record_evaluation_complete(
            f"agent_{i % 5}", "full", success=(i % 7 != 0),
            duration_s=1.5 + i * 0.1,
        )
        collector.record_llm_call(
            model=f"model_{i % 3}",
            latency_ms=200 + i * 10,
            tokens=500 + i * 50,
            cost_usd=0.01 + i * 0.002,
        )
        collector.record_mcp_call(
            server=f"server_{i % 4}",
            tool=f"tool_{i % 8}",
            success=(i % 9 != 0),
        )

    return collector


@pytest.fixture
def scheduler_config():
    """调度器配置（压力测试用，较高并发）"""
    return SchedulerConfig(
        max_concurrent_evaluations=5,
        max_queue_size=100,
        task_timeout=60,
        retry_limit=1,
        retry_delay=1,
    )


@pytest.fixture
def scheduler(scheduler_config):
    """调度器实例"""
    return EvaluationScheduler(scheduler_config)


@pytest.fixture
def quota_config():
    """配额配置（限制资源以测试竞争）"""
    return QuotaConfig(
        max_cpu_percent=80.0,
        max_memory_mb=2048.0,
        max_network_mbps=100.0,
        max_concurrent_evaluations=3,
        max_daily_evaluations=50,
    )


@pytest.fixture
def resource_quota(quota_config):
    """资源配额管理器实例"""
    return ResourceQuota(quota_config)


# ============================================================
# 辅助工具
# ============================================================

@pytest.fixture
def benchmark_logger():
    """
    性能结果格式化打印器。

    用法:
        logger = benchmark_logger()
        logger({"operation": "任务生成", "count": 100, "total_time": 1.23})
    """
    _results = []

    def _log(result: dict):
        _results.append(result)

    def _print_summary():
        """打印格式化的性能结果表格"""
        header = f"{'操作':<30} {'数量':>6} {'总耗时(s)':>10} {'平均耗时':>12} {'吞吐量(ops/s)':>14}"
        sep = "-" * len(header)
        lines = [sep, header, sep]
        for r in _results:
            count = r["count"]
            total = r["total_time"]
            avg = total / count if count > 0 else 0
            ops = count / total if total > 0 else 0
            lines.append(
                f"{r['operation']:<30} {count:>6} {total:>10.4f} {avg:>12.6f} {ops:>14.2f}"
            )
        lines.append(sep)
        print("\n" + "\n".join(lines) + "\n")

    _log.print_summary = _print_summary
    _log.results = _results
    return _log
