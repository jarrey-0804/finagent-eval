"""
数据质量监控阶段2单元测试

覆盖: DataQualityMetricsExporter、Prometheus 指标导出
"""

import pytest

from finagent.monitor.metrics import MetricsCollector
from finagent.monitor.data_quality import DataQualityMonitor
from finagent.monitor.quality_metrics import DataQualityMetricsExporter
from finagent.interface.models import (
    EvalTask, EvalResponse, TaskType, EvalDimension
)


class TestDataQualityMetricsExporter:
    """测试数据质量指标导出器"""

    def setup_method(self):
        self.monitor = DataQualityMonitor()
        self.collector = MetricsCollector()
        self.exporter = DataQualityMetricsExporter(self.monitor, self.collector)

    def test_export_sets_overall_score(self):
        """测试导出综合评分"""
        task = EvalTask(
            task_id="task_001",
            task_type=TaskType.KNOWLEDGE_QA,
            dimension=EvalDimension.ACCURACY,
            input_data={"query": "这是一个测试问题"}
        )
        self.monitor.check_task(task)

        self.exporter.export()

        score = self.collector.get_gauge("finagent_data_quality_overall_score")
        assert score > 0

    def test_export_sets_dimension_scores(self):
        """测试导出六维度评分"""
        task = EvalTask(
            task_id="task_001",
            task_type=TaskType.KNOWLEDGE_QA,
            dimension=EvalDimension.ACCURACY,
            input_data={"query": "这是一个测试问题"}
        )
        self.monitor.check_task(task)

        self.exporter.export()

        for dim in ["completeness", "accuracy", "consistency", "timeliness", "uniqueness", "validity"]:
            score = self.collector.get_gauge(
                "finagent_data_quality_dimension_score",
                labels={"dimension": dim}
            )
            assert score >= 0

    def test_export_sets_field_completeness(self):
        """测试导出字段完整率"""
        task = EvalTask(
            task_id="task_001",
            task_type=TaskType.KNOWLEDGE_QA,
            dimension=EvalDimension.ACCURACY,
            input_data={"query": "这是一个测试问题"}
        )
        self.monitor.check_task(task)

        self.exporter.export()

        for field_name in ["task_id", "task_type", "dimension", "input_data"]:
            rate = self.collector.get_gauge(
                "finagent_data_quality_field_completeness",
                labels={"model": "EvalTask", "field": field_name}
            )
            assert rate == 1.0  # 所有字段都完整

    def test_export_sets_tasks_checked(self):
        """测试导出已检查任务数"""
        for i in range(5):
            task = EvalTask(
                task_id=f"task_{i:03d}",
                task_type=TaskType.KNOWLEDGE_QA,
                dimension=EvalDimension.ACCURACY,
                input_data={"query": f"这是一个测试问题 {i}"}
            )
            self.monitor.check_task(task)

        self.exporter.export()

        count = self.collector.get_gauge("finagent_data_quality_tasks_checked")
        assert count == 5.0

    def test_export_sets_response_stats(self):
        """测试导出响应统计"""
        for i in range(3):
            response = EvalResponse(
                task_id=f"task_{i:03d}",
                output=f"回答 {i}"
            )
            self.monitor.check_response(response)

        self.exporter.export()

        success_count = self.collector.get_gauge(
            "finagent_data_quality_response_count",
            labels={"status": "success"}
        )
        assert success_count == 3.0

    def test_export_records_validation_errors(self):
        """测试导出验证错误数"""
        task = EvalTask(
            task_id="task_001",
            task_type=TaskType.KNOWLEDGE_QA,
            dimension=EvalDimension.ACCURACY,
            input_data={"query": "这是一个测试问题"}
        )
        self.monitor.check_task(task)
        # 重复 ID 会产生验证错误
        self.monitor.check_task(task)

        self.exporter.export()

        errors = self.collector.get_gauge("finagent_data_quality_validation_errors")
        assert errors == 1.0

    def test_render_prometheus_output(self):
        """测试 Prometheus 文本格式输出"""
        task = EvalTask(
            task_id="task_001",
            task_type=TaskType.KNOWLEDGE_QA,
            dimension=EvalDimension.ACCURACY,
            input_data={"query": "这是一个测试问题"}
        )
        self.monitor.check_task(task)

        output = self.exporter.render_prometheus()

        assert "# TYPE finagent_data_quality_overall_score gauge" in output
        assert "# TYPE finagent_data_quality_dimension_score gauge" in output
        assert "# TYPE finagent_data_quality_tasks_checked gauge" in output
        assert "finagent_data_quality_overall_score" in output

    def test_render_prometheus_includes_labels(self):
        """测试 Prometheus 输出包含标签"""
        task = EvalTask(
            task_id="task_001",
            task_type=TaskType.KNOWLEDGE_QA,
            dimension=EvalDimension.ACCURACY,
            input_data={"query": "这是一个测试问题"}
        )
        self.monitor.check_task(task)

        output = self.exporter.render_prometheus()

        assert 'dimension="completeness"' in output
        assert 'dimension="validity"' in output

    def test_export_with_mixed_responses(self):
        """测试混合响应场景"""
        # 成功响应
        for i in range(7):
            response = EvalResponse(
                task_id=f"task_{i:03d}",
                output=f"回答 {i}"
            )
            self.monitor.check_response(response)

        # 错误响应
        for i in range(2):
            response = EvalResponse(
                task_id=f"task_err_{i:03d}",
                output="",
                error="超时"
            )
            self.monitor.check_response(response)

        self.exporter.export()

        success = self.collector.get_gauge(
            "finagent_data_quality_response_count",
            labels={"status": "success"}
        )
        error = self.collector.get_gauge(
            "finagent_data_quality_response_count",
            labels={"status": "error"}
        )
        assert success == 7.0
        assert error == 2.0

    def test_export_idempotent(self):
        """测试多次导出结果一致"""
        task = EvalTask(
            task_id="task_001",
            task_type=TaskType.KNOWLEDGE_QA,
            dimension=EvalDimension.ACCURACY,
            input_data={"query": "这是一个测试问题"}
        )
        self.monitor.check_task(task)

        self.exporter.export()
        first_score = self.collector.get_gauge("finagent_data_quality_overall_score")

        self.exporter.export()
        second_score = self.collector.get_gauge("finagent_data_quality_overall_score")

        assert first_score == second_score
