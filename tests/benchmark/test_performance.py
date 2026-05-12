"""
性能基准测试 — 关键操作吞吐量测量

对 finagent-eval 评测流水线中的核心操作进行微基准测试，
测量不同负载级别下的耗时与吞吐量，并验证性能边界。

所有测试使用 time.perf_counter() 进行高精度计时，
结果以格式化表格输出，并附带合理性断言。
"""

import time
import pytest

from finagent.interface.models import EvalTask, EvalResponse, TaskType, EvalDimension
from finagent.taskgen.generator import EvalTaskGenerator, TaskGeneratorConfig
from finagent.scoring.engine import ScoringEngine
from finagent.scoring.veto import VetoChecker
from finagent.scoring.rules import RuleBasedScorer
from finagent.report.generator import ReportGenerator, ReportFormat
from finagent.monitor.metrics import MetricsCollector, MetricsConfig


# ============================================================
# 注册自定义 pytest marker
# ============================================================
def pytest_configure(config):
    """注册 benchmark 标记"""
    config.addinivalue_line(
        "markers", "benchmark: 性能基准测试标记"
    )


# ============================================================
# 辅助函数
# ============================================================

def _format_benchmark_table(results: list[dict]) -> str:
    """
    将基准测试结果格式化为可读表格。

    Args:
        results: 包含 operation, count, total_time 的字典列表

    Returns:
        str: 格式化的表格字符串
    """
    header = (
        f"{'操作':<35} {'数量':>6} {'总耗时(s)':>10} "
        f"{'平均耗时':>12} {'吞吐量(ops/s)':>14}"
    )
    sep = "-" * len(header)
    lines = [sep, header, sep]
    for r in results:
        count = r["count"]
        total = r["total_time"]
        avg = total / count if count > 0 else 0
        ops = count / total if total > 0 else 0
        lines.append(
            f"{r['operation']:<35} {count:>6} {total:>10.4f} "
            f"{avg:>12.6f} {ops:>14.2f}"
        )
    lines.append(sep)
    return "\n".join(lines)


def _make_veto_task_and_response(index: int):
    """
    构造用于否决检查的模拟任务和响应。

    Args:
        index: 序号，用于生成不同的 task_id

    Returns:
        tuple: (EvalTask, EvalResponse, dimension_scores)
    """
    task = EvalTask(
        task_id=f"veto_bench_{index}",
        task_type=TaskType.KNOWLEDGE_QA,
        dimension=EvalDimension.COMPLIANCE,
        input_data={"query": "请分析贵州茅台的投资价值"},
    )
    response = EvalResponse(
        task_id=task.task_id,
        output=(
            "根据分析，贵州茅台基本面良好，ROE为18.5%。"
            "投资有风险，请谨慎决策。"
        ),
    )
    dimension_scores = {
        "compliance": 75.0 + (index % 30),
        "security": 80.0 + (index % 20),
    }
    return task, response, dimension_scores


def _make_rule_task_and_response(index: int):
    """
    构造用于规则评分的模拟任务和响应。

    Args:
        index: 序号，用于生成不同的 task_id

    Returns:
        tuple: (EvalTask, EvalResponse)
    """
    task = EvalTask(
        task_id=f"rule_bench_{index}",
        task_type=TaskType.KNOWLEDGE_QA,
        dimension=EvalDimension.ACCURACY,
        input_data={"query": "分析2024年Q3财报数据"},
        context={"expected_tools": ["get_financial", "get_market_data"]},
    )
    response = EvalResponse(
        task_id=task.task_id,
        output=(
            "根据财务数据分析，公司2024年Q3营收388亿元，同比增长15%。"
            "因为毛利率稳定在65%，所以盈利能力较强。"
            "建议关注市场风险，投资需谨慎。"
        ),
        tool_calls=[
            {"tool_name": "get_financial", "args": {"symbol": "600519"}, "success": True},
            {"tool_name": "get_market_data", "args": {"period": "1y"}, "success": True},
        ],
    )
    return task, response


# ============================================================
# 测试用例
# ============================================================

class TestPerformanceBenchmark:
    """性能基准测试套件"""

    @pytest.mark.benchmark
    def test_task_generation_throughput(self, benchmark_logger):
        """
        测试1: 任务生成吞吐量

        测量在不同任务数量（10/50/100）下的任务生成耗时。
        预期: 单个任务生成时间 < 50ms。
        """
        results = []
        task_counts = [10, 50, 100]

        for n in task_counts:
            config = TaskGeneratorConfig(
                tasks_per_source=n,
                max_total_tasks=n,
                random_seed=42,
            )
            generator = EvalTaskGenerator(config)

            start = time.perf_counter()
            tasks = generator.generate_tasks(n_tasks=n)
            elapsed = time.perf_counter() - start

            # 验证生成的任务数量
            assert len(tasks) > 0, f"生成 {n} 个任务时返回空列表"

            result = {
                "operation": f"任务生成(n={n})",
                "count": len(tasks),
                "total_time": elapsed,
            }
            results.append(result)
            benchmark_logger(result)

        # 性能断言: 100个任务应在5秒内完成（单个 < 50ms）
        assert results[-1]["total_time"] < 5.0, (
            f"100个任务生成耗时 {results[-1]['total_time']:.2f}s，超过5秒阈值"
        )

        # 打印汇总表格
        print("\n" + _format_benchmark_table(results))

    @pytest.mark.benchmark
    def test_scoring_throughput(self, sample_tasks, sample_responses, scoring_engine, benchmark_logger):
        """
        测试2: 评分吞吐量

        测量在不同任务数量（10/50）下的评分引擎耗时。
        预期: 单个任务评分时间 < 1s。
        """
        results = []
        task_counts = [10, 50]

        for n in task_counts:
            tasks = sample_tasks[:n]
            responses = sample_responses[:n]

            start = time.perf_counter()
            for task, response in zip(tasks, responses):
                score = scoring_engine.score_task(task, response)
                # 验证评分结果有效性
                assert 0 <= score.overall_score <= 100, (
                    f"评分结果超出范围: {score.overall_score}"
                )
            elapsed = time.perf_counter() - start

            result = {
                "operation": f"任务评分(n={n})",
                "count": n,
                "total_time": elapsed,
            }
            results.append(result)
            benchmark_logger(result)

        # 性能断言: 单个任务评分 < 1s
        for r in results:
            avg_time = r["total_time"] / r["count"]
            assert avg_time < 1.0, (
                f"评分 {r['count']} 个任务时平均耗时 {avg_time:.3f}s，超过1秒阈值"
            )

        print("\n" + _format_benchmark_table(results))

    @pytest.mark.benchmark
    def test_veto_check_throughput(self, veto_checker, benchmark_logger):
        """
        测试3: 否决检查吞吐量

        测量 1000 次否决检查的总耗时。
        预期: 单次否决检查 < 1ms。
        """
        n = 1000
        checker = veto_checker

        # 预构造测试数据，避免构造时间影响测量
        test_data = [_make_veto_task_and_response(i) for i in range(n)]

        start = time.perf_counter()
        for task, response, dim_scores in test_data:
            result = checker.check(task, response, dim_scores)
            # 验证返回类型
            assert hasattr(result, "vetoed"), "否决检查结果缺少 vetoed 属性"
        elapsed = time.perf_counter() - start

        result = {
            "operation": "否决检查",
            "count": n,
            "total_time": elapsed,
        }
        benchmark_logger(result)

        # 性能断言: 单次检查 < 1ms
        avg_time = elapsed / n
        assert avg_time < 0.001, (
            f"单次否决检查耗时 {avg_time * 1000:.3f}ms，超过1ms阈值"
        )

        print("\n" + _format_benchmark_table([result]))

    @pytest.mark.benchmark
    def test_rule_based_scoring_throughput(self, rule_scorer, benchmark_logger):
        """
        测试4: 基于规则的评分吞吐量

        测量 1000 次规则评分的总耗时。
        预期: 单次规则评分 < 5ms。
        """
        n = 1000
        scorer = rule_scorer

        # 预构造测试数据
        test_data = [_make_rule_task_and_response(i) for i in range(n)]

        start = time.perf_counter()
        for task, response in test_data:
            results = scorer.evaluate(task, response)
            # 验证返回结果
            assert len(results) > 0, "规则评分返回空列表"
            for r in results:
                assert 0 <= r.score <= 100, f"规则评分超出范围: {r.score}"
        elapsed = time.perf_counter() - start

        result = {
            "operation": "规则评分",
            "count": n,
            "total_time": elapsed,
        }
        benchmark_logger(result)

        # 性能断言: 单次评分 < 5ms
        avg_time = elapsed / n
        assert avg_time < 0.005, (
            f"单次规则评分耗时 {avg_time * 1000:.3f}ms，超过5ms阈值"
        )

        print("\n" + _format_benchmark_table([result]))

    @pytest.mark.benchmark
    def test_report_generation_time(self, sample_eval_data, report_generator, benchmark_logger):
        """
        测试5: 报告生成时间

        分别测量 JSON / Markdown / HTML 三种格式的报告生成耗时。
        预期: 每种格式报告生成 < 500ms。
        """
        results = []
        formats = [
            (ReportFormat.JSON, "JSON报告"),
            (ReportFormat.MARKDOWN, "Markdown报告"),
            (ReportFormat.HTML, "HTML报告"),
        ]

        for fmt, label in formats:
            start = time.perf_counter()
            report = report_generator.generate(sample_eval_data, fmt)
            elapsed = time.perf_counter() - start

            # 验证报告非空
            assert len(report) > 0, f"{label} 生成为空"

            result = {
                "operation": f"{label}生成",
                "count": 1,
                "total_time": elapsed,
            }
            results.append(result)
            benchmark_logger(result)

        # 性能断言: 每种格式 < 500ms
        for r in results:
            assert r["total_time"] < 0.5, (
                f"{r['operation']} 耗时 {r['total_time'] * 1000:.1f}ms，超过500ms阈值"
            )

        print("\n" + _format_benchmark_table(results))

    @pytest.mark.benchmark
    def test_metrics_render_time(self, metrics_collector, benchmark_logger):
        """
        测试6: Prometheus 指标渲染时间

        测量在预填充指标数据下的 Prometheus 文本格式渲染耗时。
        预期: 渲染时间 < 50ms。
        """
        collector = metrics_collector

        # 额外填充更多数据以模拟真实负载
        for i in range(100):
            collector.observe(
                "finagent_evaluation_duration_seconds",
                0.5 + i * 0.01,
                labels={"agent_id": f"agent_{i % 10}", "mode": "full"},
            )

        start = time.perf_counter()
        output = collector.render_prometheus()
        elapsed = time.perf_counter() - start

        # 验证输出非空且包含 Prometheus 格式标记
        assert len(output) > 0, "Prometheus 指标输出为空"
        assert "# TYPE" in output, "输出缺少 Prometheus TYPE 标记"

        result = {
            "operation": "Prometheus指标渲染",
            "count": 1,
            "total_time": elapsed,
        }
        benchmark_logger(result)

        # 性能断言: 渲染 < 50ms
        assert elapsed < 0.05, (
            f"Prometheus 指标渲染耗时 {elapsed * 1000:.1f}ms，超过50ms阈值"
        )

        print("\n" + _format_benchmark_table([result]))
