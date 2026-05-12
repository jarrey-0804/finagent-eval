"""
数据质量 Prometheus 指标导出模块

将 DataQualityMonitor 的质量指标桥接到现有的 MetricsCollector，
实现 Prometheus 格式导出。

对应数据质量治理方案 - 阶段 2
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .metrics import MetricsCollector
    from .data_quality import DataQualityMonitor


class DataQualityMetricsExporter:
    """
    数据质量指标导出器

    将 DataQualityMonitor 的质量指标同步到 MetricsCollector，
    实现 Prometheus 格式导出。
    """

    def __init__(
        self,
        monitor: DataQualityMonitor,
        collector: MetricsCollector,
    ):
        self._monitor = monitor
        self._collector = collector

    def export(self) -> None:
        """
        将当前数据质量指标同步到 MetricsCollector。

        调用后可通过 collector.render_prometheus() 获取 Prometheus 文本格式。
        """
        report = self._monitor.generate_report()

        # ---- 综合评分 (Gauge) ----
        self._collector.set_gauge(
            "finagent_data_quality_overall_score",
            report.metrics.overall_score,
        )

        # ---- 六维度评分 (Gauge) ----
        dimension_scores = {
            "completeness": report.metrics.completeness_rate,
            "accuracy": report.metrics.accuracy_rate,
            "consistency": report.metrics.consistency_rate,
            "timeliness": report.metrics.timeliness_rate,
            "uniqueness": report.metrics.uniqueness_rate,
            "validity": report.metrics.validity_rate,
        }
        for dim, score in dimension_scores.items():
            self._collector.set_gauge(
                "finagent_data_quality_dimension_score",
                score,
                labels={"dimension": dim},
            )

        # ---- 字段完整率 (Gauge) ----
        for field_name, stats in report.details.get("field_stats", {}).items():
            total = stats.get("total", 0)
            missing = stats.get("missing", 0)
            rate = 1.0 - (missing / total) if total > 0 else 1.0
            self._collector.set_gauge(
                "finagent_data_quality_field_completeness",
                rate,
                labels={"model": "EvalTask", "field": field_name},
            )

        # ---- 响应统计 (Gauge) ----
        response_stats = report.details.get("response_stats", {})
        total_responses = sum(response_stats.values())
        if total_responses > 0:
            for status, count in response_stats.items():
                self._collector.set_gauge(
                    "finagent_data_quality_response_count",
                    float(count),
                    labels={"status": status},
                )

        # ---- 验证错误 (Counter) ----
        error_count = report.details.get("validation_error_count", 0)
        self._collector.set_gauge(
            "finagent_data_quality_validation_errors",
            float(error_count),
        )

        # ---- 已检查任务总数 (Gauge) ----
        self._collector.set_gauge(
            "finagent_data_quality_tasks_checked",
            float(len(self._monitor.task_ids)),
        )

    def render_prometheus(self) -> str:
        """
        导出 Prometheus 文本格式。

        Returns:
            Prometheus exposition format 文本
        """
        self.export()
        return self._collector.render_prometheus()
