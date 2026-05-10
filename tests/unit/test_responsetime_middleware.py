"""
ResponseTime 中间件单元测试

测试模块: finagent.api.middleware.responsetime
覆盖: ResponseTimeConfig, ResponseTimeTracker, ResponseTimeMiddleware
"""

import pytest

from finagent.api.middleware.responsetime import (
    ResponseTimeConfig,
    ResponseTimeStats,
    ResponseTimeTracker,
    ResponseTimeMiddleware,
)


# ======================================================================
# ResponseTimeConfig
# ======================================================================

class TestResponseTimeConfig:
    """ResponseTimeConfig 数据类默认值测试"""

    def test_defaults(self):
        """验证默认值: timeout_ms=5000, p95_threshold_ms=500, window_size=1000"""
        config = ResponseTimeConfig()
        assert config.timeout_ms == 5000.0
        assert config.p95_threshold_ms == 500.0
        assert config.window_size == 1000

    def test_custom_values(self):
        """验证自定义值可以正确覆盖默认值"""
        config = ResponseTimeConfig(
            timeout_ms=3000.0,
            p95_threshold_ms=200.0,
            window_size=500,
        )
        assert config.timeout_ms == 3000.0
        assert config.p95_threshold_ms == 200.0
        assert config.window_size == 500

    def test_exempt_paths_default(self):
        """验证默认豁免路径包含 health/docs 等路径"""
        config = ResponseTimeConfig()
        assert "/health" in config.exempt_paths
        assert "/docs" in config.exempt_paths
        assert "/openapi.json" in config.exempt_paths
        assert "/metrics" in config.exempt_paths


# ======================================================================
# ResponseTimeTracker
# ======================================================================

class TestResponseTimeTrackerRecord:
    """ResponseTimeTracker.record() 测试"""

    def test_record_single(self):
        """记录单条响应时间"""
        tracker = ResponseTimeTracker()
        tracker.record("/api/test", 100.0)
        stats = tracker.get_stats("/api/test")
        assert stats.count == 1
        assert stats.total_ms == 100.0

    def test_record_multiple(self):
        """记录多条响应时间"""
        tracker = ResponseTimeTracker()
        tracker.record("/api/test", 100.0)
        tracker.record("/api/test", 200.0)
        tracker.record("/api/test", 300.0)
        stats = tracker.get_stats("/api/test")
        assert stats.count == 3

    def test_record_respects_window_size(self):
        """记录超过窗口大小时，只保留最近的记录"""
        config = ResponseTimeConfig(window_size=3)
        tracker = ResponseTimeTracker(config)
        for i in range(5):
            tracker.record("/api/test", float(i * 10))
        stats = tracker.get_stats("/api/test")
        # 窗口大小为 3，只保留最后 3 条
        assert stats.count == 3
        assert stats.min_ms == 20.0  # 第 3 条 (index=2)
        assert stats.max_ms == 40.0  # 第 5 条 (index=4)

    def test_record_timeout_flag(self):
        """记录超时标志"""
        tracker = ResponseTimeTracker()
        tracker.record("/api/test", 5000.0, is_timeout=True)
        stats = tracker.get_stats("/api/test")
        assert stats.timeout_count == 1

    def test_record_slow_request(self):
        """慢请求自动计数"""
        config = ResponseTimeConfig(slow_request_threshold_ms=200.0, enable_slow_log=False)
        tracker = ResponseTimeTracker(config)
        tracker.record("/api/test", 300.0)  # 超过阈值
        stats = tracker.get_stats("/api/test")
        assert stats.slow_count == 1


class TestResponseTimeTrackerGetStats:
    """ResponseTimeTracker.get_stats() 统计计算测试"""

    @pytest.fixture
    def tracker_with_data(self):
        """创建包含已知数据的 tracker"""
        tracker = ResponseTimeTracker()
        # 10 条记录: 10, 20, 30, ..., 100
        for i in range(1, 11):
            tracker.record("/api/test", float(i * 10))
        return tracker

    def test_stats_with_known_data(self, tracker_with_data):
        """验证 p50/p95/p99/avg/min/max 计算正确"""
        stats = tracker_with_data.get_stats("/api/test")
        assert stats.count == 10
        assert stats.min_ms == 10.0
        assert stats.max_ms == 100.0
        assert stats.avg_ms == 55.0  # (10+20+...+100)/10 = 550/10

    def test_stats_p50(self, tracker_with_data):
        """验证 P50 计算"""
        stats = tracker_with_data.get_stats("/api/test")
        # 10 条排序数据: [10,20,30,40,50,60,70,80,90,100]
        # P50 index = int(10 * 0.50) = 5 -> sorted_data[5] = 60
        assert stats.p50_ms == 60.0

    def test_stats_p95(self, tracker_with_data):
        """验证 P95 计算"""
        stats = tracker_with_data.get_stats("/api/test")
        # P95 index = int(10 * 0.95) = 9 -> sorted_data[9] = 100
        assert stats.p95_ms == 100.0

    def test_stats_p99(self, tracker_with_data):
        """验证 P99 计算"""
        stats = tracker_with_data.get_stats("/api/test")
        # P99 index = min(int(10 * 0.99), 9) = min(9, 9) = 9 -> sorted_data[9] = 100
        assert stats.p99_ms == 100.0

    def test_stats_empty(self):
        """无数据时返回空统计"""
        tracker = ResponseTimeTracker()
        stats = tracker.get_stats()
        assert stats.count == 0
        assert stats.min_ms == 0.0
        assert stats.max_ms == 0.0
        assert stats.avg_ms == 0.0
        assert stats.p50_ms == 0.0
        assert stats.p95_ms == 0.0
        assert stats.p99_ms == 0.0

    def test_stats_empty_for_unknown_path(self):
        """未知路径返回空统计"""
        tracker = ResponseTimeTracker()
        tracker.record("/api/a", 100.0)
        stats = tracker.get_stats("/api/b")
        assert stats.count == 0

    def test_stats_per_endpoint(self):
        """验证按端点分别统计"""
        tracker = ResponseTimeTracker()
        tracker.record("/api/a", 100.0)
        tracker.record("/api/a", 200.0)
        tracker.record("/api/b", 50.0)

        stats_a = tracker.get_stats("/api/a")
        assert stats_a.count == 2
        assert stats_a.avg_ms == 150.0

        stats_b = tracker.get_stats("/api/b")
        assert stats_b.count == 1
        assert stats_b.avg_ms == 50.0

    def test_stats_global(self):
        """验证全局统计包含所有端点数据"""
        tracker = ResponseTimeTracker()
        tracker.record("/api/a", 100.0)
        tracker.record("/api/b", 200.0)

        stats = tracker.get_stats()
        assert stats.count == 2
        assert stats.avg_ms == 150.0

    def test_stats_single_value_percentiles(self):
        """单条数据时百分位值等于该值"""
        tracker = ResponseTimeTracker()
        tracker.record("/api/test", 42.0)
        stats = tracker.get_stats("/api/test")
        assert stats.p50_ms == 42.0
        assert stats.p95_ms == 42.0
        assert stats.p99_ms == 42.0


class TestResponseTimeTrackerCheckP95Health:
    """ResponseTimeTracker.check_p95_health() 测试"""

    def test_returns_true_when_p95_under_threshold(self):
        """P95 低于阈值时返回 True"""
        config = ResponseTimeConfig(p95_threshold_ms=500.0)
        tracker = ResponseTimeTracker(config)
        # 所有响应时间都远低于 500ms
        for i in range(20):
            tracker.record("/api/test", 100.0 + i)
        assert tracker.check_p95_health() is True

    def test_returns_false_when_p95_over_threshold(self):
        """P95 超过阈值时返回 False"""
        config = ResponseTimeConfig(p95_threshold_ms=50.0)
        tracker = ResponseTimeTracker(config)
        # 20 条记录，P95 index = int(20*0.95) = 19 -> sorted_data[19]
        for i in range(20):
            tracker.record("/api/test", float(i * 10))
        # P95 = sorted_data[19] = 190 > 50
        assert tracker.check_p95_health() is False

    def test_returns_true_when_no_data(self):
        """无数据时 P95=0，应返回 True"""
        tracker = ResponseTimeTracker()
        assert tracker.check_p95_health() is True


class TestResponseTimeTrackerReset:
    """ResponseTimeTracker.reset() 测试"""

    def test_reset_clears_all_data(self):
        """重置后所有统计数据清空"""
        tracker = ResponseTimeTracker()
        tracker.record("/api/a", 100.0)
        tracker.record("/api/b", 200.0, is_timeout=True)

        tracker.reset()

        assert tracker.get_stats("/api/a").count == 0
        assert tracker.get_stats("/api/b").count == 0
        assert tracker.get_stats().count == 0

    def test_reset_clears_timeout_and_slow_counts(self):
        """重置后超时计数和慢请求计数清零"""
        config = ResponseTimeConfig(slow_request_threshold_ms=50.0, enable_slow_log=False)
        tracker = ResponseTimeTracker(config)
        tracker.record("/api/test", 5000.0, is_timeout=True)  # 同时也是慢请求
        assert tracker.get_stats().timeout_count == 1
        assert tracker.get_stats().slow_count == 1

        tracker.reset()

        assert tracker.get_stats().timeout_count == 0
        assert tracker.get_stats().slow_count == 0


# ======================================================================
# ResponseTimeMiddleware
# ======================================================================

class TestResponseTimeMiddleware:
    """ResponseTimeMiddleware 测试"""

    @pytest.fixture
    def middleware(self):
        tracker = ResponseTimeTracker()
        return ResponseTimeMiddleware(tracker)

    def test_is_exempt_health_path(self, middleware):
        """health 路径应被豁免"""
        assert middleware.is_exempt("/health") is True

    def test_is_exempt_docs_path(self, middleware):
        """docs 路径应被豁免"""
        assert middleware.is_exempt("/docs") is True

    def test_is_exempt_live_path(self, middleware):
        """live 路径应被豁免"""
        assert middleware.is_exempt("/live") is True

    def test_is_exempt_ready_path(self, middleware):
        """ready 路径应被豁免"""
        assert middleware.is_exempt("/ready") is True

    def test_is_exempt_openapi_path(self, middleware):
        """openapi.json 路径应被豁免"""
        assert middleware.is_exempt("/openapi.json") is True

    def test_is_exempt_metrics_path(self, middleware):
        """metrics 路径应被豁免"""
        assert middleware.is_exempt("/metrics") is True

    def test_is_not_exempt_api_path(self, middleware):
        """API 路径不应被豁免"""
        assert middleware.is_exempt("/api/evaluate") is False

    def test_is_not_exempt_root_path(self, middleware):
        """根路径不应被豁免"""
        assert middleware.is_exempt("/") is False

    def test_is_not_exempt_random_path(self, middleware):
        """随机路径不应被豁免"""
        assert middleware.is_exempt("/some/random/path") is False

    def test_middleware_uses_default_tracker(self):
        """不传入 tracker 时使用默认 tracker"""
        mw = ResponseTimeMiddleware()
        assert mw.tracker is not None
        assert isinstance(mw.tracker, ResponseTimeTracker)


# ======================================================================
# Module Exports
# ======================================================================

class TestModuleExports:
    """模块导出测试"""

    def test_middleware_module_exports(self):
        """finagent.api.middleware 应导出 ResponseTimeMiddleware, ResponseTimeTracker, ResponseTimeConfig"""
        from finagent.api.middleware import (
            ResponseTimeMiddleware,
            ResponseTimeTracker,
            ResponseTimeConfig,
            ResponseTimeStats,
        )
        assert ResponseTimeMiddleware is not None
        assert ResponseTimeTracker is not None
        assert ResponseTimeConfig is not None
        assert ResponseTimeStats is not None

    def test_middleware_module_all(self):
        """finagent.api.middleware.__all__ 应包含新类"""
        from finagent.api.middleware import __all__
        assert "ResponseTimeMiddleware" in __all__
        assert "ResponseTimeTracker" in __all__
        assert "ResponseTimeConfig" in __all__
        assert "ResponseTimeStats" in __all__
