"""
监控和工具审计单元测试
"""

import pytest
from finagent.monitor.metrics import MetricsCollector, MetricsConfig
from finagent.audit.tool_auditor import (
    UniversalToolAuditor, AuditConfig, ToolCallStatus, AuditLevel,
)
from finagent.isolation.manager import StateIsolationManager, IsolationConfig
from finagent.pipeline.scheduler import EvaluationScheduler, SchedulerConfig, TaskPriority
from finagent.pipeline.quota import ResourceQuota, QuotaConfig


class TestMetricsCollector:
    """指标采集器测试"""

    @pytest.fixture
    def collector(self):
        return MetricsCollector()

    def test_counter(self, collector):
        collector.increment_counter("test_counter", 1.0)
        assert collector.get_counter("test_counter") == 1.0
        collector.increment_counter("test_counter", 2.0)
        assert collector.get_counter("test_counter") == 3.0

    def test_counter_with_labels(self, collector):
        collector.increment_counter("requests", labels={"method": "GET"})
        collector.increment_counter("requests", labels={"method": "POST"})
        assert collector.get_counter("requests", {"method": "GET"}) == 1.0
        assert collector.get_counter("requests", {"method": "POST"}) == 1.0

    def test_gauge(self, collector):
        collector.set_gauge("temperature", 36.5)
        assert collector.get_gauge("temperature") == 36.5
        collector.set_gauge("temperature", 37.0)
        assert collector.get_gauge("temperature") == 37.0

    def test_histogram(self, collector):
        collector.observe("latency", 100)
        collector.observe("latency", 200)
        collector.observe("latency", 300)
        stats = collector.get_histogram_stats("latency")
        assert stats["count"] == 3
        assert stats["avg"] == 200.0

    def test_render_prometheus(self, collector):
        collector.increment_counter("test_total")
        collector.set_gauge("test_active", 5)
        output = collector.render_prometheus()
        assert "test_total" in output
        assert "test_active" in output
        assert "TYPE test_total counter" in output

    def test_record_evaluation(self, collector):
        collector.record_evaluation_start("agent_001", "full")
        assert collector.get_counter("finagent_evaluations_total", {"agent_id": "agent_001", "mode": "full"}) == 1.0
        collector.record_evaluation_complete("agent_001", "full", True, 120.5)
        assert collector.get_gauge("finagent_evaluations_active") == 0

    def test_reset(self, collector):
        collector.increment_counter("test", 5)
        collector.reset()
        assert collector.get_counter("test") == 0


class TestUniversalToolAuditor:
    """工具审计器测试"""

    @pytest.fixture
    def auditor(self):
        return UniversalToolAuditor()

    def test_record_call(self, auditor):
        record = auditor.record_call(
            evaluation_id="eval_001",
            task_id="task_001",
            agent_id="agent_001",
            tool_name="get_stock_price",
            input_args={"symbol": "600519"},
            status=ToolCallStatus.SUCCESS,
            duration_ms=150.0,
        )
        assert record.tool_name == "get_stock_price"
        assert record.status == ToolCallStatus.SUCCESS

    def test_sensitive_args_filtering(self, auditor):
        record = auditor.record_call(
            evaluation_id="eval_001",
            task_id="task_001",
            agent_id="agent_001",
            tool_name="api_call",
            input_args={"api_key": "secret123", "symbol": "600519"},
        )
        assert record.input_args["api_key"] == "***REDACTED***"
        assert record.input_args["symbol"] == "600519"

    def test_generate_report(self, auditor):
        auditor.record_call("eval_001", "t1", "a1", "tool_a", {}, status=ToolCallStatus.SUCCESS, duration_ms=100)
        auditor.record_call("eval_001", "t2", "a1", "tool_b", {}, status=ToolCallStatus.FAILURE, duration_ms=200)

        report = auditor.generate_report("eval_001", "a1")
        assert report.total_calls == 2
        assert report.success_count == 1
        assert report.failure_count == 1

    def test_auto_audit_timeout(self, auditor):
        record = auditor.record_call(
            "eval_001", "t1", "a1", "slow_tool", {},
            status=ToolCallStatus.SUCCESS, duration_ms=15000,
        )
        assert record.audit_level == AuditLevel.WARNING

    def test_auto_audit_permission_denied(self, auditor):
        record = auditor.record_call(
            "eval_001", "t1", "a1", "dangerous_tool", {},
            status=ToolCallStatus.PERMISSION_DENIED,
        )
        assert record.audit_level == AuditLevel.CRITICAL


class TestStateIsolationManager:
    """状态隔离管理器测试"""

    @pytest.fixture
    def manager(self):
        return StateIsolationManager()

    @pytest.mark.asyncio
    async def test_create_isolation(self, manager):
        iso_id = await manager.create_isolation("eval_001")
        assert iso_id is not None

    @pytest.mark.asyncio
    async def test_update_and_get_state(self, manager):
        iso_id = await manager.create_isolation("eval_001")
        await manager.update_state(iso_id, "task_001", {"key": "value"})
        state = await manager.get_state(iso_id)
        assert state["key"] == "value"

    @pytest.mark.asyncio
    async def test_cleanup(self, manager):
        iso_id = await manager.create_isolation("eval_001")
        await manager.cleanup_isolation(iso_id)
        state = await manager.get_state(iso_id)
        assert state is None


class TestResourceQuota:
    """资源配额测试"""

    @pytest.fixture
    def quota(self):
        return ResourceQuota(QuotaConfig(max_concurrent_evaluations=2))

    def test_can_allocate(self, quota):
        assert quota.can_allocate() is True

    def test_allocate_and_release(self, quota):
        assert quota.allocate("eval_001") is True
        assert quota.allocate("eval_002") is True
        assert quota.can_allocate() is False
        quota.release("eval_001")
        assert quota.can_allocate() is True

    def test_get_usage(self, quota):
        quota.allocate("eval_001")
        usage = quota.get_usage()
        assert usage.active_evaluations == 1
