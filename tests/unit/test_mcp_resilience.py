"""
MCP 弹性机制单元测试

覆盖: 熔断器、重试机制、缓存
对应数据质量治理方案 - 阶段 3
"""

import asyncio
import time
import pytest
from unittest.mock import Mock, AsyncMock

from finagent.mcp.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerRegistry,
    CircuitState,
    get_circuit_breaker_registry,
)
from finagent.mcp.retry import (
    RetryConfig,
    RetryHandler,
    RetryExhaustedError,
    with_retry,
)
from finagent.mcp.cache import (
    DataCache,
    MCPDataCache,
    MemoryCacheBackend,
)


class TestCircuitBreaker:
    """测试熔断器"""

    def test_initial_state(self):
        """测试初始状态"""
        cb = CircuitBreaker("test")
        assert cb.state == CircuitState.CLOSED
        assert cb.can_execute() is True

    def test_record_success_in_closed(self):
        """测试 CLOSED 状态下记录成功"""
        cb = CircuitBreaker("test")
        cb.record_success()
        assert cb.stats.success_count == 0  # CLOSED 状态下不累计

    def test_record_failure_in_closed(self):
        """测试 CLOSED 状态下记录失败"""
        cb = CircuitBreaker("test", config=CircuitBreakerConfig(failure_threshold=3))

        cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        assert cb.can_execute() is True

        cb.record_failure()
        assert cb.state == CircuitState.CLOSED

        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.can_execute() is False

    def test_open_to_half_open_timeout(self):
        """测试 OPEN 超时后转为 HALF_OPEN"""
        cb = CircuitBreaker(
            "test",
            config=CircuitBreakerConfig(failure_threshold=1, timeout=0.1)
        )

        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.can_execute() is False

        # 等待超时
        import time
        time.sleep(0.15)

        assert cb.can_execute() is True
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_to_closed(self):
        """测试 HALF_OPEN 成功恢复为 CLOSED"""
        cb = CircuitBreaker(
            "test",
            config=CircuitBreakerConfig(
                failure_threshold=1,
                success_threshold=2,
                timeout=0.05
            )
        )

        cb.record_failure()
        time.sleep(0.1)  # 等待超时

        # 触发状态检查（通过 can_execute）
        cb.can_execute()
        assert cb.state == CircuitState.HALF_OPEN

        cb.record_success()
        assert cb.state == CircuitState.HALF_OPEN

        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_half_open_to_open_on_failure(self):
        """测试 HALF_OPEN 失败转为 OPEN"""
        cb = CircuitBreaker(
            "test",
            config=CircuitBreakerConfig(failure_threshold=1, timeout=0.05)
        )

        cb.record_failure()
        time.sleep(0.1)

        # 触发状态检查（通过 can_execute）
        cb.can_execute()
        assert cb.state == CircuitState.HALF_OPEN

        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_state_change_callback(self):
        """测试状态变化回调"""
        callback = Mock()
        cb = CircuitBreaker(
            "test",
            config=CircuitBreakerConfig(failure_threshold=1),
            on_state_change=callback
        )

        cb.record_failure()
        callback.assert_called_once_with(CircuitState.CLOSED, CircuitState.OPEN)

    def test_reset(self):
        """测试手动重置"""
        cb = CircuitBreaker("test", config=CircuitBreakerConfig(failure_threshold=1))
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.stats.failure_count == 0

    def test_get_state_summary(self):
        """测试获取状态摘要"""
        cb = CircuitBreaker("test_service")
        summary = cb.get_state_summary()

        assert summary["name"] == "test_service"
        assert summary["state"] == "closed"
        assert "failure_count" in summary
        assert "can_execute" in summary


class TestCircuitBreakerRegistry:
    """测试熔断器注册表"""

    def setup_method(self):
        """每个测试前清理"""
        registry = get_circuit_breaker_registry()
        registry.reset_all()
        # 清空注册表
        registry._breakers.clear()

    def test_get_or_create(self):
        """测试获取或创建"""
        registry = CircuitBreakerRegistry()

        cb1 = registry.get_or_create("service1")
        cb2 = registry.get_or_create("service1")

        assert cb1 is cb2

    def test_get_existing(self):
        """测试获取已存在的熔断器"""
        registry = CircuitBreakerRegistry()
        registry.get_or_create("service1")

        cb = registry.get("service1")
        assert cb is not None
        assert cb.name == "service1"

    def test_get_nonexistent(self):
        """测试获取不存在的熔断器"""
        registry = CircuitBreakerRegistry()
        cb = registry.get("nonexistent")
        assert cb is None

    def test_remove(self):
        """测试移除熔断器"""
        registry = CircuitBreakerRegistry()
        registry.get_or_create("service1")

        assert registry.remove("service1") is True
        assert registry.get("service1") is None
        assert registry.remove("service1") is False

    def test_get_all_summaries(self):
        """测试获取所有摘要"""
        registry = CircuitBreakerRegistry()
        registry.get_or_create("service1")
        registry.get_or_create("service2")

        summaries = registry.get_all_summaries()
        assert len(summaries) == 2
        assert "service1" in summaries
        assert "service2" in summaries


class TestRetryHandler:
    """测试重试处理器"""

    def test_calculate_delay_exponential(self):
        """测试指数退避延迟计算"""
        config = RetryConfig(base_delay=1.0, exponential_base=2.0, jitter=False)
        handler = RetryHandler(config)

        assert handler.calculate_delay(0) == 1.0
        assert handler.calculate_delay(1) == 2.0
        assert handler.calculate_delay(2) == 4.0

    def test_calculate_delay_with_max(self):
        """测试最大延迟限制"""
        config = RetryConfig(base_delay=1.0, max_delay=5.0, exponential_base=2.0, jitter=False)
        handler = RetryHandler(config)

        assert handler.calculate_delay(10) == 5.0  # 超过 max_delay

    def test_calculate_delay_with_jitter(self):
        """测试抖动"""
        config = RetryConfig(base_delay=1.0, jitter=True, jitter_max=0.5)
        handler = RetryHandler(config)

        delay = handler.calculate_delay(0)
        assert 0.75 <= delay <= 1.25  # 1.0 ± 0.25

    @pytest.mark.asyncio
    async def test_execute_success(self):
        """测试成功执行"""
        handler = RetryHandler(RetryConfig(max_attempts=3))

        async def success_func():
            return "success"

        result = await handler.execute(success_func)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_execute_retry_then_success(self):
        """测试重试后成功"""
        config = RetryConfig(max_attempts=3, base_delay=0.01)
        handler = RetryHandler(config)

        call_count = 0

        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("temporary error")
            return "success"

        result = await handler.execute(flaky_func)
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_execute_exhausted(self):
        """测试重试次数耗尽"""
        config = RetryConfig(max_attempts=2, base_delay=0.01)
        handler = RetryHandler(config)

        async def always_fail():
            raise ValueError("always fails")

        with pytest.raises(RetryExhaustedError) as exc_info:
            await handler.execute(always_fail)

        assert exc_info.value.attempts == 2
        assert "always fails" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_with_callback(self):
        """测试带回调的重试"""
        config = RetryConfig(max_attempts=3, base_delay=0.01)
        handler = RetryHandler(config)

        callback = Mock()

        async def fail_once():
            if callback.call_count < 1:
                raise ValueError("error")
            return "success"

        result = await handler.execute(fail_once, on_retry=callback)
        assert result == "success"
        assert callback.called

    def test_execute_sync(self):
        """测试同步执行"""
        config = RetryConfig(max_attempts=2, base_delay=0.01)
        handler = RetryHandler(config)

        call_count = 0

        def sync_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("error")
            return "success"

        result = handler.execute_sync(sync_func)
        assert result == "success"
        assert call_count == 2


class TestWithRetryDecorator:
    """测试重试装饰器"""

    @pytest.mark.asyncio
    async def test_async_decorator(self):
        """测试异步装饰器"""
        call_count = 0

        @with_retry(max_attempts=3, base_delay=0.01)
        async def async_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("error")
            return "success"

        result = await async_func()
        assert result == "success"
        assert call_count == 2

    def test_sync_decorator(self):
        """测试同步装饰器"""
        call_count = 0

        @with_retry(max_attempts=3, base_delay=0.01)
        def sync_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("error")
            return "success"

        result = sync_func()
        assert result == "success"
        assert call_count == 2


class TestMemoryCacheBackend:
    """测试内存缓存后端"""

    @pytest.mark.asyncio
    async def test_set_and_get(self):
        """测试设置和获取"""
        cache = MemoryCacheBackend()
        await cache.set("key1", "value1", ttl=60)

        value = await cache.get("key1")
        assert value == "value1"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self):
        """测试获取不存在的键"""
        cache = MemoryCacheBackend()
        value = await cache.get("nonexistent")
        assert value is None

    @pytest.mark.asyncio
    async def test_expired_entry(self):
        """测试过期条目"""
        cache = MemoryCacheBackend()
        await cache.set("key1", "value1", ttl=0.01)

        import time
        time.sleep(0.02)

        value = await cache.get("key1")
        assert value is None

    @pytest.mark.asyncio
    async def test_delete(self):
        """测试删除"""
        cache = MemoryCacheBackend()
        await cache.set("key1", "value1", ttl=60)

        assert await cache.delete("key1") is True
        assert await cache.get("key1") is None
        assert await cache.delete("key1") is False

    @pytest.mark.asyncio
    async def test_exists(self):
        """测试存在检查"""
        cache = MemoryCacheBackend()
        await cache.set("key1", "value1", ttl=60)

        assert await cache.exists("key1") is True
        assert await cache.exists("nonexistent") is False

    @pytest.mark.asyncio
    async def test_clear(self):
        """测试清空"""
        cache = MemoryCacheBackend()
        await cache.set("key1", "value1", ttl=60)
        await cache.set("key2", "value2", ttl=60)

        await cache.clear()

        assert await cache.get("key1") is None
        assert await cache.get("key2") is None

    def test_get_stats(self):
        """测试获取统计"""
        cache = MemoryCacheBackend()
        stats = cache.get_stats()

        assert "total_entries" in stats
        assert "active_entries" in stats


class TestDataCache:
    """测试数据缓存"""

    @pytest.mark.asyncio
    async def test_basic_operations(self):
        """测试基本操作"""
        cache = DataCache(default_ttl=60)

        await cache.set("key1", "value1")
        value = await cache.get("key1")
        assert value == "value1"

    @pytest.mark.asyncio
    async def test_custom_ttl(self):
        """测试自定义 TTL"""
        cache = DataCache(default_ttl=300)

        await cache.set("key1", "value1", ttl=0.01)

        import time
        time.sleep(0.02)

        value = await cache.get("key1")
        assert value is None

    @pytest.mark.asyncio
    async def test_make_key(self):
        """测试构建缓存键"""
        key = DataCache.make_key("yahoo", "AAPL", "price")
        assert key == "yahoo:AAPL:price"

    def test_get_stats(self):
        """测试获取统计"""
        cache = DataCache()
        stats = cache.get_stats()

        assert "total_entries" in stats


class TestMCPDataCache:
    """测试 MCP 数据缓存"""

    @pytest.mark.asyncio
    async def test_tool_result_caching(self):
        """测试工具结果缓存"""
        cache = MCPDataCache()

        result = {"price": 150.0, "currency": "USD"}
        await cache.set_tool_result("yahoo", "get_price", {"symbol": "AAPL"}, result)

        cached = await cache.get_tool_result("yahoo", "get_price", {"symbol": "AAPL"})
        assert cached == result

    @pytest.mark.asyncio
    async def test_tool_result_args_order(self):
        """测试参数顺序无关"""
        cache = MCPDataCache()

        result = {"data": "test"}
        await cache.set_tool_result(
            "server", "tool",
            {"a": 1, "b": 2},
            result
        )

        # 不同顺序应返回相同结果
        cached = await cache.get_tool_result(
            "server", "tool",
            {"b": 2, "a": 1}
        )
        assert cached == result

    @pytest.mark.asyncio
    async def test_invalidate_server(self):
        """测试使服务器缓存失效"""
        cache = MCPDataCache()

        await cache.set_tool_result("yahoo", "tool1", {}, "result1")
        await cache.set_tool_result("yahoo", "tool2", {}, "result2")
        await cache.set_tool_result("other", "tool1", {}, "result3")

        count = await cache.invalidate_server("yahoo")
        assert count == 2

        assert await cache.get_tool_result("yahoo", "tool1", {}) is None
        assert await cache.get_tool_result("yahoo", "tool2", {}) is None
        assert await cache.get_tool_result("other", "tool1", {}) is not None

    @pytest.mark.asyncio
    async def test_invalidate_tool(self):
        """测试使工具缓存失效"""
        cache = MCPDataCache()

        await cache.set_tool_result("server", "tool1", {}, "result1")
        await cache.set_tool_result("server", "tool1", {"arg": 1}, "result2")
        await cache.set_tool_result("server", "tool2", {}, "result3")

        count = await cache.invalidate_tool("server", "tool1")
        assert count == 2

        assert await cache.get_tool_result("server", "tool1", {}) is None
        assert await cache.get_tool_result("server", "tool2", {}) is not None


class TestResilienceIntegration:
    """弹性机制集成测试"""

    @pytest.mark.asyncio
    async def test_circuit_breaker_with_retry(self):
        """测试熔断器与重试结合"""
        cb = CircuitBreaker("test", config=CircuitBreakerConfig(failure_threshold=5))
        retry_handler = RetryHandler(RetryConfig(max_attempts=3, base_delay=0.01))

        call_count = 0

        async def operation():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ValueError("temporary error")
            return "success"

        # 使用重试执行操作
        result = await retry_handler.execute(operation)

        # 记录成功（熔断器状态不变）
        cb.record_success()
        assert cb.state == CircuitState.CLOSED
        assert result == "success"

    @pytest.mark.asyncio
    async def test_cache_with_circuit_breaker(self):
        """测试缓存与熔断器结合"""
        cb = CircuitBreaker("yahoo_finance")
        cache = MCPDataCache()

        # 模拟缓存命中（不触发熔断器）
        await cache.set_tool_result("yahoo", "get_price", {"symbol": "AAPL"}, {"price": 150.0})

        result = await cache.get_tool_result("yahoo", "get_price", {"symbol": "AAPL"})
        assert result is not None

        # 熔断器未触发
        assert cb.can_execute() is True
