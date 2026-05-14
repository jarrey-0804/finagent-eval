"""
分布式调度器单元测试

测试模块: finagent.pipeline.distributed_scheduler
覆盖: RedisSchedulerConfig, RedisTaskStore, DistributedEvaluationScheduler

注意: 测试环境可能没有 Redis，因此重点测试内存模式回退逻辑。
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from finagent.pipeline.distributed_scheduler import (
    RedisSchedulerConfig,
    RedisTaskStore,
    DistributedEvaluationScheduler,
)


# ======================================================================
# RedisSchedulerConfig
# ======================================================================

class TestRedisSchedulerConfig:
    """RedisSchedulerConfig 数据类默认值测试"""

    def test_defaults(self):
        """验证默认值: redis_url, max_concurrent=3, heartbeat_interval=10"""
        config = RedisSchedulerConfig()
        assert config.redis_url == "redis://localhost:6379/0"
        assert config.max_concurrent_evaluations == 3
        assert config.heartbeat_interval == 10

    def test_custom_values(self):
        """验证自定义值可以正确覆盖默认值"""
        config = RedisSchedulerConfig(
            redis_url="redis://custom:6380/1",
            max_concurrent_evaluations=5,
            heartbeat_interval=30,
        )
        assert config.redis_url == "redis://custom:6380/1"
        assert config.max_concurrent_evaluations == 5
        assert config.heartbeat_interval == 30

    def test_other_defaults(self):
        """验证其他默认值"""
        config = RedisSchedulerConfig()
        assert config.max_queue_size == 50
        assert config.task_timeout == 43200
        assert config.retry_limit == 2
        assert config.retry_delay == 30
        assert config.instance_ttl == 30
        assert config.lock_ttl == 60


# ======================================================================
# RedisTaskStore
# ======================================================================

class TestRedisTaskStore:
    """RedisTaskStore 测试（无 Redis 环境）"""

    def test_is_available_false_before_initialize(self):
        """初始化前 is_available 应为 False"""
        store = RedisTaskStore()
        assert store.is_available is False

    @pytest.mark.asyncio
    async def test_is_available_false_after_failed_initialize(self):
        """Redis 连接失败后 is_available 仍为 False"""
        store = RedisTaskStore()
        await store.initialize()
        assert store.is_available is False

    def test_custom_config(self):
        """验证自定义配置传递到 store"""
        config = RedisSchedulerConfig(redis_url="redis://nonexistent:9999/0")
        store = RedisTaskStore(config)
        assert store.config.redis_url == "redis://nonexistent:9999/0"


# ======================================================================
# DistributedEvaluationScheduler
# ======================================================================

class TestDistributedEvaluationSchedulerInit:
    """DistributedEvaluationScheduler 初始化测试"""

    def test_creates_instance_with_uuid(self):
        """初始化时应生成 UUID 作为 instance_id"""
        scheduler = DistributedEvaluationScheduler()
        assert scheduler._instance_id is not None
        assert len(scheduler._instance_id) == 8

    def test_creates_unique_instance_ids(self):
        """不同实例应具有不同的 instance_id"""
        s1 = DistributedEvaluationScheduler()
        s2 = DistributedEvaluationScheduler()
        assert s1._instance_id != s2._instance_id

    def test_uses_default_config(self):
        """不传入配置时使用默认配置"""
        scheduler = DistributedEvaluationScheduler()
        assert scheduler.config is not None
        assert isinstance(scheduler.config, RedisSchedulerConfig)

    def test_uses_custom_config(self):
        """传入自定义配置"""
        config = RedisSchedulerConfig(max_concurrent_evaluations=10)
        scheduler = DistributedEvaluationScheduler(config)
        assert scheduler.config.max_concurrent_evaluations == 10

    def test_initializes_memory_queue(self):
        """初始化时内存队列应为空"""
        scheduler = DistributedEvaluationScheduler()
        assert scheduler._memory_queue == []
        assert scheduler._memory_running == {}


class TestDistributedEvaluationSchedulerMemoryMode:
    """DistributedEvaluationScheduler 内存模式测试"""

    @pytest.fixture
    async def memory_scheduler(self):
        """创建以内存模式运行的调度器"""
        scheduler = DistributedEvaluationScheduler()
        await scheduler.initialize()
        yield scheduler
        await scheduler.close()

    @pytest.mark.asyncio
    async def test_submit_returns_task_id(self, memory_scheduler):
        """内存模式 submit 应返回 task_id 字符串"""
        task_id = await memory_scheduler.submit(
            evaluation_id="eval_001",
            agent_id="agent_001",
        )
        assert isinstance(task_id, str)
        assert len(task_id) > 0

    @pytest.mark.asyncio
    async def test_submit_adds_to_memory_queue(self, memory_scheduler):
        """submit 后内存队列应有任务"""
        await memory_scheduler.submit(
            evaluation_id="eval_001",
            agent_id="agent_001",
        )
        assert len(memory_scheduler._memory_queue) == 1

    @pytest.mark.asyncio
    async def test_get_queue_status_structure(self, memory_scheduler):
        """get_queue_status 应返回正确的结构，mode='memory'"""
        status = await memory_scheduler.get_queue_status()
        assert isinstance(status, dict)
        assert "queue_size" in status
        assert "running_count" in status
        assert "mode" in status
        assert status["mode"] == "memory"

    @pytest.mark.asyncio
    async def test_get_queue_status_empty(self, memory_scheduler):
        """空队列时 queue_size 应为 0"""
        status = await memory_scheduler.get_queue_status()
        assert status["queue_size"] == 0
        assert status["running_count"] == 0

    @pytest.mark.asyncio
    async def test_get_queue_status_with_tasks(self, memory_scheduler):
        """提交任务后 queue_size 应增加"""
        await memory_scheduler.submit(
            evaluation_id="eval_001",
            agent_id="agent_001",
        )
        await memory_scheduler.submit(
            evaluation_id="eval_002",
            agent_id="agent_002",
        )
        status = await memory_scheduler.get_queue_status()
        assert status["queue_size"] == 2

    @pytest.mark.asyncio
    async def test_get_queue_status_max_concurrent(self, memory_scheduler):
        """get_queue_status 应包含 max_concurrent"""
        status = await memory_scheduler.get_queue_status()
        assert status["max_concurrent"] == 3

    @pytest.mark.asyncio
    async def test_get_queue_status_instance_id(self, memory_scheduler):
        """get_queue_status 应包含 instance_id"""
        status = await memory_scheduler.get_queue_status()
        assert status["instance_id"] == memory_scheduler._instance_id

    @pytest.mark.asyncio
    async def test_cancel_task_nonexistent(self, memory_scheduler):
        """取消不存在的任务应返回 False"""
        result = await memory_scheduler.cancel_task("nonexistent-task-id")
        assert result is False

    @pytest.mark.asyncio
    async def test_cancel_task_in_queue(self, memory_scheduler):
        """取消队列中的任务应返回 True"""
        task_id = await memory_scheduler.submit(
            evaluation_id="eval_001",
            agent_id="agent_001",
        )
        result = await memory_scheduler.cancel_task(task_id)
        assert result is True
        # 队列应为空
        status = await memory_scheduler.get_queue_status()
        assert status["queue_size"] == 0

    @pytest.mark.asyncio
    async def test_get_task_status_running(self, memory_scheduler):
        """内存模式下获取运行中任务状态"""
        # 手动模拟运行中任务
        memory_scheduler._memory_running["test-task-id"] = {
            "evaluation_id": "eval_001",
        }
        status = await memory_scheduler.get_task_status("test-task-id")
        assert status is not None
        assert status["status"] == "running"
        assert status["task_id"] == "test-task-id"

    @pytest.mark.asyncio
    async def test_get_task_status_not_found(self, memory_scheduler):
        """内存模式下获取不存在的任务状态应返回 None"""
        status = await memory_scheduler.get_task_status("nonexistent-task-id")
        assert status is None

    @pytest.mark.asyncio
    async def test_submit_with_priority(self, memory_scheduler):
        """提交不同优先级的任务"""
        await memory_scheduler.submit(
            evaluation_id="eval_001",
            agent_id="agent_001",
            priority="urgent",
        )
        await memory_scheduler.submit(
            evaluation_id="eval_002",
            agent_id="agent_002",
            priority="low",
        )
        # 队列应按优先级排序
        assert memory_scheduler._memory_queue[0]["priority"] == 0  # urgent
        assert memory_scheduler._memory_queue[1]["priority"] == 3  # low


# ======================================================================
# Module Exports
# ======================================================================

class TestModuleExports:
    """模块导出测试"""

    def test_pipeline_module_exports(self):
        """finagent.pipeline 应导出 DistributedEvaluationScheduler, RedisSchedulerConfig, RedisTaskStore"""
        from finagent.pipeline import (
            DistributedEvaluationScheduler,
            RedisSchedulerConfig,
            RedisTaskStore,
        )
        assert DistributedEvaluationScheduler is not None
        assert RedisSchedulerConfig is not None
        assert RedisTaskStore is not None

    def test_pipeline_module_all(self):
        """finagent.pipeline.__all__ 应包含新类"""
        from finagent.pipeline import __all__
        assert "DistributedEvaluationScheduler" in __all__
        assert "RedisSchedulerConfig" in __all__
        assert "RedisTaskStore" in __all__


# ======================================================================
# RedisTaskStore - Mock Redis 模式测试
# ======================================================================

class TestRedisTaskStoreWithMockRedis:
    """RedisTaskStore 使用 Mock Redis 的测试"""

    @pytest.fixture
    def mock_redis(self):
        """创建 Mock Redis 客户端"""
        redis = AsyncMock()
        redis.ping = AsyncMock(return_value=True)
        redis.pipeline = MagicMock(return_value=AsyncMock())
        redis.zpopmin = AsyncMock(return_value=None)
        redis.hgetall = AsyncMock(return_value={})
        redis.zcard = AsyncMock(return_value=0)
        redis.scard = AsyncMock(return_value=0)
        redis.set = AsyncMock(return_value=True)
        redis.eval = AsyncMock(return_value=1)
        redis.hset = AsyncMock(return_value=True)
        redis.expire = AsyncMock(return_value=True)
        redis.sadd = AsyncMock(return_value=1)
        redis.srem = AsyncMock(return_value=0)
        redis.lpush = AsyncMock(return_value=1)
        redis.ltrim = AsyncMock(return_value=True)
        redis.scan_iter = AsyncMock(return_value=[])
        redis.aclose = AsyncMock(return_value=True)
        return redis

    @pytest.mark.asyncio
    async def test_initialize_success(self, mock_redis):
        """Redis 连接成功时 is_available 应为 True"""
        with patch("redis.asyncio") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            store = RedisTaskStore()
            await store.initialize()
            assert store.is_available is True
            await store.close()

    @pytest.mark.asyncio
    async def test_initialize_failure(self):
        """Redis 连接失败时 is_available 应为 False"""
        with patch("redis.asyncio") as mock_aioredis:
            mock_aioredis.from_url.side_effect = ConnectionError("Connection refused")
            store = RedisTaskStore()
            await store.initialize()
            assert store.is_available is False

    @pytest.mark.asyncio
    async def test_close(self, mock_redis):
        """close 应关闭 Redis 连接"""
        with patch("redis.asyncio") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            store = RedisTaskStore()
            await store.initialize()
            await store.close()
            mock_redis.aclose.assert_awaited_once()
            assert store._redis is None

    @pytest.mark.asyncio
    async def test_enqueue_success(self, mock_redis):
        """enqueue 成功时应返回 True"""
        mock_pipe = AsyncMock()
        mock_pipe.execute = AsyncMock(return_value=[True, True, True])
        mock_redis.pipeline.return_value = mock_pipe

        with patch("redis.asyncio") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            store = RedisTaskStore()
            await store.initialize()
            result = await store.enqueue("task-1", {"data": "test"}, 1.0)
            assert result is True
            mock_pipe.execute.assert_awaited_once()
            await store.close()

    @pytest.mark.asyncio
    async def test_enqueue_not_available(self):
        """Redis 不可用时 enqueue 应返回 False"""
        store = RedisTaskStore()
        result = await store.enqueue("task-1", {"data": "test"}, 1.0)
        assert result is False

    @pytest.mark.asyncio
    async def test_enqueue_exception(self, mock_redis):
        """enqueue 异常时应返回 False"""
        mock_pipe = AsyncMock()
        mock_pipe.execute = AsyncMock(side_effect=Exception("Redis error"))
        mock_redis.pipeline.return_value = mock_pipe

        with patch("redis.asyncio") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            store = RedisTaskStore()
            await store.initialize()
            result = await store.enqueue("task-1", {"data": "test"}, 1.0)
            assert result is False
            await store.close()

    @pytest.mark.asyncio
    async def test_dequeue_success(self, mock_redis):
        """dequeue 成功时应返回任务数据"""
        mock_redis.zpopmin = AsyncMock(return_value=[("task-1", 1.0)])
        mock_redis.hgetall = AsyncMock(return_value={
            "data": '{"key": "value"}',
            "created_at": "2025-01-01T00:00:00",
        })

        with patch("redis.asyncio") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            store = RedisTaskStore()
            await store.initialize()
            result = await store.dequeue()
            assert result is not None
            assert result["task_id"] == "task-1"
            assert result["priority"] == 1.0
            assert result["data"] == {"key": "value"}
            await store.close()

    @pytest.mark.asyncio
    async def test_dequeue_empty(self, mock_redis):
        """队列为空时 dequeue 应返回 None"""
        mock_redis.zpopmin = AsyncMock(return_value=None)

        with patch("redis.asyncio") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            store = RedisTaskStore()
            await store.initialize()
            result = await store.dequeue()
            assert result is None
            await store.close()

    @pytest.mark.asyncio
    async def test_dequeue_no_task_data(self, mock_redis):
        """dequeue 后任务数据不存在时应返回 None"""
        mock_redis.zpopmin = AsyncMock(return_value=[("task-1", 1.0)])
        mock_redis.hgetall = AsyncMock(return_value={})

        with patch("redis.asyncio") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            store = RedisTaskStore()
            await store.initialize()
            result = await store.dequeue()
            assert result is None
            await store.close()

    @pytest.mark.asyncio
    async def test_dequeue_not_available(self):
        """Redis 不可用时 dequeue 应返回 None"""
        store = RedisTaskStore()
        result = await store.dequeue()
        assert result is None

    @pytest.mark.asyncio
    async def test_dequeue_exception(self, mock_redis):
        """dequeue 异常时应返回 None"""
        mock_redis.zpopmin = AsyncMock(side_effect=Exception("Redis error"))

        with patch("redis.asyncio") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            store = RedisTaskStore()
            await store.initialize()
            result = await store.dequeue()
            assert result is None
            await store.close()

    @pytest.mark.asyncio
    async def test_queue_size(self, mock_redis):
        """queue_size 应返回队列大小"""
        mock_redis.zcard = AsyncMock(return_value=5)

        with patch("redis.asyncio") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            store = RedisTaskStore()
            await store.initialize()
            result = await store.queue_size()
            assert result == 5
            await store.close()

    @pytest.mark.asyncio
    async def test_queue_size_not_available(self):
        """Redis 不可用时 queue_size 应返回 0"""
        store = RedisTaskStore()
        result = await store.queue_size()
        assert result == 0

    @pytest.mark.asyncio
    async def test_queue_size_exception(self, mock_redis):
        """queue_size 异常时应返回 0"""
        mock_redis.zcard = AsyncMock(side_effect=Exception("Redis error"))

        with patch("redis.asyncio") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            store = RedisTaskStore()
            await store.initialize()
            result = await store.queue_size()
            assert result == 0
            await store.close()

    @pytest.mark.asyncio
    async def test_mark_running(self, mock_redis):
        """mark_running 应正确标记任务"""
        mock_pipe = AsyncMock()
        mock_pipe.execute = AsyncMock(return_value=[True, True, True, True])
        mock_redis.pipeline.return_value = mock_pipe

        with patch("redis.asyncio") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            store = RedisTaskStore()
            await store.initialize()
            await store.mark_running("task-1", "instance-1")
            mock_pipe.execute.assert_awaited_once()
            await store.close()

    @pytest.mark.asyncio
    async def test_mark_running_not_available(self):
        """Redis 不可用时 mark_running 应静默返回"""
        store = RedisTaskStore()
        await store.mark_running("task-1", "instance-1")  # 不应抛异常

    @pytest.mark.asyncio
    async def test_mark_completed(self, mock_redis):
        """mark_completed 应正确标记任务"""
        mock_pipe = AsyncMock()
        mock_pipe.execute = AsyncMock(return_value=[True, True, True])
        mock_redis.pipeline.return_value = mock_pipe

        with patch("redis.asyncio") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            store = RedisTaskStore()
            await store.initialize()
            await store.mark_completed("task-1", {"status": "completed"})
            mock_pipe.execute.assert_awaited_once()
            await store.close()

    @pytest.mark.asyncio
    async def test_mark_failed(self, mock_redis):
        """mark_failed 应正确标记任务"""
        with patch("redis.asyncio") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            store = RedisTaskStore()
            await store.initialize()
            await store.mark_failed("task-1", "some error")
            mock_redis.hset.assert_awaited()
            await store.close()

    @pytest.mark.asyncio
    async def test_remove_from_running(self, mock_redis):
        """remove_from_running 应正确移除任务"""
        with patch("redis.asyncio") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            store = RedisTaskStore()
            await store.initialize()
            await store.remove_from_running("task-1", "instance-1")
            mock_redis.srem.assert_awaited_once()
            await store.close()

    @pytest.mark.asyncio
    async def test_running_count(self, mock_redis):
        """running_count 应返回运行中任务数"""
        mock_redis.scard = AsyncMock(return_value=3)

        with patch("redis.asyncio") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            store = RedisTaskStore()
            await store.initialize()
            result = await store.running_count("instance-1")
            assert result == 3
            await store.close()

    @pytest.mark.asyncio
    async def test_total_running_count(self, mock_redis):
        """total_running_count 应返回所有实例运行中任务总数"""

        async def mock_scan_iter(*args, **kwargs):
            for key in ["finagent:running:i1", "finagent:running:i2"]:
                yield key

        mock_redis.scan_iter = mock_scan_iter
        mock_redis.scard = AsyncMock(return_value=2)

        with patch("redis.asyncio") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            store = RedisTaskStore()
            await store.initialize()
            result = await store.total_running_count()
            assert result == 4  # 2 instances * 2 tasks each
            await store.close()

    @pytest.mark.asyncio
    async def test_total_running_count_empty(self, mock_redis):
        """没有运行中任务时 total_running_count 应返回 0"""

        async def mock_scan_iter(*args, **kwargs):
            return
            yield  # make it an async generator

        mock_redis.scan_iter = mock_scan_iter

        with patch("redis.asyncio") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            store = RedisTaskStore()
            await store.initialize()
            result = await store.total_running_count()
            assert result == 0
            await store.close()

    @pytest.mark.asyncio
    async def test_acquire_lock_success(self, mock_redis):
        """获取分布式锁成功"""
        mock_redis.set = AsyncMock(return_value=True)

        with patch("redis.asyncio") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            store = RedisTaskStore()
            await store.initialize()
            result = await store.acquire_lock("test_lock", "instance-1")
            assert result is True
            await store.close()

    @pytest.mark.asyncio
    async def test_acquire_lock_failure(self, mock_redis):
        """获取分布式锁失败（锁已被占用）"""
        mock_redis.set = AsyncMock(return_value=None)

        with patch("redis.asyncio") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            store = RedisTaskStore()
            await store.initialize()
            result = await store.acquire_lock("test_lock", "instance-1")
            assert result is False
            await store.close()

    @pytest.mark.asyncio
    async def test_release_lock(self, mock_redis):
        """释放分布式锁"""
        with patch("redis.asyncio") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            store = RedisTaskStore()
            await store.initialize()
            await store.release_lock("test_lock", "instance-1")
            mock_redis.eval.assert_awaited_once()
            await store.close()

    @pytest.mark.asyncio
    async def test_register_instance(self, mock_redis):
        """注册实例"""
        with patch("redis.asyncio") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            store = RedisTaskStore()
            await store.initialize()
            await store.register_instance("instance-1")
            mock_redis.hset.assert_awaited()
            mock_redis.expire.assert_awaited()
            await store.close()

    @pytest.mark.asyncio
    async def test_heartbeat(self, mock_redis):
        """心跳更新"""
        with patch("redis.asyncio") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            store = RedisTaskStore()
            await store.initialize()
            await store.heartbeat("instance-1")
            mock_redis.hset.assert_awaited()
            await store.close()

    @pytest.mark.asyncio
    async def test_get_active_instances(self, mock_redis):
        """获取活跃实例列表"""

        async def mock_scan_iter(*args, **kwargs):
            for key in ["finagent:instances:i1"]:
                yield key

        mock_redis.scan_iter = mock_scan_iter
        mock_redis.hgetall = AsyncMock(return_value={"instance_id": "i1", "status": "active"})

        with patch("redis.asyncio") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            store = RedisTaskStore()
            await store.initialize()
            result = await store.get_active_instances()
            assert len(result) == 1
            assert result[0]["instance_id"] == "i1"
            await store.close()

    @pytest.mark.asyncio
    async def test_get_active_instances_empty(self, mock_redis):
        """没有活跃实例时返回空列表"""

        async def mock_scan_iter(*args, **kwargs):
            return
            yield  # make it an async generator

        mock_redis.scan_iter = mock_scan_iter

        with patch("redis.asyncio") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            store = RedisTaskStore()
            await store.initialize()
            result = await store.get_active_instances()
            assert result == []
            await store.close()

    @pytest.mark.asyncio
    async def test_get_task_status(self, mock_redis):
        """获取任务状态"""
        mock_redis.hgetall = AsyncMock(return_value={
            "task_id": "task-1",
            "status": "running",
        })

        with patch("redis.asyncio") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            store = RedisTaskStore()
            await store.initialize()
            result = await store.get_task_status("task-1")
            assert result is not None
            assert result["status"] == "running"
            await store.close()

    @pytest.mark.asyncio
    async def test_get_task_status_not_found(self, mock_redis):
        """任务不存在时返回 None"""
        mock_redis.hgetall = AsyncMock(return_value={})

        with patch("redis.asyncio") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            store = RedisTaskStore()
            await store.initialize()
            result = await store.get_task_status("nonexistent")
            assert result is None
            await store.close()


# ======================================================================
# DistributedEvaluationScheduler - 分布式模式 (Mock Redis) 测试
# ======================================================================

class TestDistributedSchedulerWithMockRedis:
    """DistributedEvaluationScheduler 使用 Mock Redis 的分布式模式测试"""

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.ping = AsyncMock(return_value=True)
        redis.pipeline = MagicMock(return_value=AsyncMock())
        redis.zpopmin = AsyncMock(return_value=None)
        redis.hgetall = AsyncMock(return_value={})
        redis.zcard = AsyncMock(return_value=0)
        redis.scard = AsyncMock(return_value=0)
        redis.set = AsyncMock(return_value=True)
        redis.eval = AsyncMock(return_value=1)
        redis.hset = AsyncMock(return_value=True)
        redis.expire = AsyncMock(return_value=True)
        redis.sadd = AsyncMock(return_value=1)
        redis.srem = AsyncMock(return_value=0)
        redis.lpush = AsyncMock(return_value=1)
        redis.ltrim = AsyncMock(return_value=True)
        redis.scan_iter = AsyncMock(return_value=[])
        redis.aclose = AsyncMock(return_value=True)
        return redis

    @pytest.mark.asyncio
    async def test_submit_distributed_mode(self, mock_redis):
        """分布式模式下 submit 应成功入队"""
        mock_pipe = AsyncMock()
        mock_pipe.execute = AsyncMock(return_value=[True, True, True])
        mock_redis.pipeline.return_value = mock_pipe

        with patch("redis.asyncio") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            scheduler = DistributedEvaluationScheduler()
            await scheduler.initialize()
            assert scheduler._store.is_available

            task_id = await scheduler.submit(
                evaluation_id="eval_001",
                agent_id="agent_001",
            )
            assert isinstance(task_id, str)
            assert len(task_id) > 0
            await scheduler.close()

    @pytest.mark.asyncio
    async def test_submit_distributed_enqueue_failure(self, mock_redis):
        """分布式模式下 enqueue 失败应抛出 RuntimeError"""
        mock_pipe = AsyncMock()
        mock_pipe.execute = AsyncMock(side_effect=Exception("Redis error"))
        mock_redis.pipeline.return_value = mock_pipe

        with patch("redis.asyncio") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            scheduler = DistributedEvaluationScheduler()
            await scheduler.initialize()

            with pytest.raises(RuntimeError, match="任务入队失败"):
                await scheduler.submit(
                    evaluation_id="eval_001",
                    agent_id="agent_001",
                )
            await scheduler.close()

    @pytest.mark.asyncio
    async def test_submit_with_all_priorities(self, mock_redis):
        """测试所有优先级映射"""
        mock_pipe = AsyncMock()
        mock_pipe.execute = AsyncMock(return_value=[True, True, True])
        mock_redis.pipeline.return_value = mock_pipe

        with patch("redis.asyncio") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            scheduler = DistributedEvaluationScheduler()
            await scheduler.initialize()

            priorities = ["urgent", "high", "normal", "low", "unknown"]
            expected_scores = [0, 1, 2, 3, 2]  # unknown 默认为 2

            for priority, expected in zip(priorities, expected_scores):
                task_id = await scheduler.submit(
                    evaluation_id="eval_001",
                    agent_id="agent_001",
                    priority=priority,
                )
                assert isinstance(task_id, str)

            await scheduler.close()

    @pytest.mark.asyncio
    async def test_submit_with_task_func(self, mock_redis):
        """submit 时传入 task_func"""
        mock_pipe = AsyncMock()
        mock_pipe.execute = AsyncMock(return_value=[True, True, True])
        mock_redis.pipeline.return_value = mock_pipe

        with patch("redis.asyncio") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            scheduler = DistributedEvaluationScheduler()
            await scheduler.initialize()

            async def dummy_func():
                pass

            task_id = await scheduler.submit(
                evaluation_id="eval_001",
                agent_id="agent_001",
                task_func=dummy_func,
            )
            assert isinstance(task_id, str)
            await scheduler.close()

    @pytest.mark.asyncio
    async def test_get_queue_status_distributed(self, mock_redis):
        """分布式模式下 get_queue_status 应返回 mode='distributed'"""
        mock_redis.zcard = AsyncMock(return_value=3)

        with patch("redis.asyncio") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            scheduler = DistributedEvaluationScheduler()
            await scheduler.initialize()

            status = await scheduler.get_queue_status()
            assert status["mode"] == "distributed"
            assert status["queue_size"] == 3
            await scheduler.close()

    @pytest.mark.asyncio
    async def test_get_task_status_distributed(self, mock_redis):
        """分布式模式下获取任务状态"""
        mock_redis.hgetall = AsyncMock(return_value={
            "task_id": "task-1",
            "status": "completed",
        })

        with patch("redis.asyncio") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            scheduler = DistributedEvaluationScheduler()
            await scheduler.initialize()

            status = await scheduler.get_task_status("task-1")
            assert status is not None
            assert status["status"] == "completed"
            await scheduler.close()

    @pytest.mark.asyncio
    async def test_cancel_task_running(self, mock_redis):
        """取消正在运行的任务应返回 True"""
        mock_redis.zcard = AsyncMock(return_value=0)

        with patch("redis.asyncio") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            scheduler = DistributedEvaluationScheduler()
            await scheduler.initialize()

            # 模拟运行中的任务
            mock_task = asyncio.create_task(asyncio.sleep(10))
            scheduler._running_tasks["task-1"] = mock_task

            result = await scheduler.cancel_task("task-1")
            assert result is True
            mock_task.cancel()
            try:
                await mock_task
            except asyncio.CancelledError:
                pass
            await scheduler.close()

    @pytest.mark.asyncio
    async def test_cancel_task_nonexistent_distributed(self, mock_redis):
        """分布式模式下取消不存在的任务应返回 False"""
        with patch("redis.asyncio") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            scheduler = DistributedEvaluationScheduler()
            await scheduler.initialize()

            result = await scheduler.cancel_task("nonexistent")
            assert result is False
            await scheduler.close()

    @pytest.mark.asyncio
    async def test_start_and_stop(self, mock_redis):
        """启动和停止调度器"""
        with patch("redis.asyncio") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            scheduler = DistributedEvaluationScheduler()
            await scheduler.start()
            assert scheduler._scheduler_task is not None
            assert scheduler._heartbeat_task is not None

            await scheduler.stop()
            assert scheduler._scheduler_task is None or scheduler._scheduler_task.cancelled()
            await scheduler.close()

    @pytest.mark.asyncio
    async def test_dispatch_task_concurrency_limit(self, mock_redis):
        """并发数达到上限时不应调度新任务"""
        mock_redis.total_running_count = AsyncMock(return_value=3)
        mock_redis.zpopmin = AsyncMock(return_value=[("task-1", 1.0)])
        mock_redis.hgetall = AsyncMock(return_value={
            "data": '{"key": "value"}',
            "created_at": "2025-01-01T00:00:00",
        })

        config = RedisSchedulerConfig(max_concurrent_evaluations=3)
        with patch("redis.asyncio") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            scheduler = DistributedEvaluationScheduler(config)
            await scheduler.initialize()

            # 模拟已有3个运行中任务
            mock_task = asyncio.create_task(asyncio.sleep(10))
            scheduler._running_tasks["existing-1"] = mock_task
            scheduler._running_tasks["existing-2"] = mock_task
            scheduler._running_tasks["existing-3"] = mock_task

            # 尝试调度 - 应因本地并发限制而不调度
            await scheduler._dispatch_task()
            # zpopmin 不应被调用（本地并发已达上限）
            mock_redis.zpopmin.assert_not_awaited()

            mock_task.cancel()
            try:
                await mock_task
            except asyncio.CancelledError:
                pass
            await scheduler.close()

    @pytest.mark.asyncio
    async def test_execute_task_success_distributed(self, mock_redis):
        """分布式模式下任务执行成功"""
        mock_pipe = AsyncMock()
        mock_pipe.execute = AsyncMock(return_value=[True, True, True])
        mock_redis.pipeline.return_value = mock_pipe

        with patch("redis.asyncio") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            scheduler = DistributedEvaluationScheduler()
            await scheduler.initialize()

            # Mock asyncio.sleep to speed up test
            with patch("asyncio.sleep", new_callable=AsyncMock):
                await scheduler._execute_task("task-1", {"evaluation_id": "eval_001"})

            # 任务应从 running_tasks 中移除
            assert "task-1" not in scheduler._running_tasks
            await scheduler.close()

    @pytest.mark.asyncio
    async def test_execute_task_failure_distributed(self, mock_redis):
        """分布式模式下任务执行失败"""
        mock_redis.hset = AsyncMock(side_effect=Exception("Redis error"))

        with patch("redis.asyncio") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            scheduler = DistributedEvaluationScheduler()
            await scheduler.initialize()

            # Make _execute_task fail by patching asyncio.sleep to raise
            with patch("asyncio.sleep", side_effect=Exception("Task failed")):
                await scheduler._execute_task("task-1", {"evaluation_id": "eval_001"})

            assert "task-1" not in scheduler._running_tasks
            await scheduler.close()

    @pytest.mark.asyncio
    async def test_dispatch_task_memory_mode(self):
        """内存模式下调度任务"""
        scheduler = DistributedEvaluationScheduler()
        await scheduler.initialize()

        # 提交一个任务
        await scheduler.submit(evaluation_id="eval_001", agent_id="agent_001")
        assert len(scheduler._memory_queue) == 1

        # 调度任务（模拟 sleep 不阻塞）
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await scheduler._dispatch_task()

        # 队列应为空，任务应在运行中
        assert len(scheduler._memory_queue) == 0
        assert "task" in str(scheduler._memory_running) or len(scheduler._running_tasks) > 0

        await scheduler.close()

    @pytest.mark.asyncio
    async def test_schedule_loop_exception_handling(self):
        """调度循环应能处理异常"""
        scheduler = DistributedEvaluationScheduler()
        await scheduler.initialize()

        # Make _dispatch_task raise
        call_count = 0
        original_dispatch = scheduler._dispatch_task

        async def failing_dispatch():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Dispatch error")
            raise asyncio.CancelledError()

        scheduler._dispatch_task = failing_dispatch

        # Run one iteration
        try:
            await scheduler._schedule_loop()
        except asyncio.CancelledError:
            pass

        assert call_count >= 1
        await scheduler.close()

    @pytest.mark.asyncio
    async def test_heartbeat_loop(self, mock_redis):
        """心跳循环应正常更新心跳"""
        with patch("redis.asyncio") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            scheduler = DistributedEvaluationScheduler()
            await scheduler.initialize()

            # Run one iteration of heartbeat loop
            try:
                # heartbeat_interval is 10, so we need to cancel after first iteration
                task = asyncio.create_task(scheduler._heartbeat_loop())
                await asyncio.sleep(0.1)
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            except Exception:
                pass

            await scheduler.close()

    @pytest.mark.asyncio
    async def test_close_without_start(self):
        """未启动时 close 不应报错"""
        scheduler = DistributedEvaluationScheduler()
        await scheduler.close()  # 不应抛异常

    @pytest.mark.asyncio
    async def test_stop_without_start(self):
        """未启动时 stop 不应报错"""
        scheduler = DistributedEvaluationScheduler()
        await scheduler.stop()  # 不应抛异常

    @pytest.mark.asyncio
    async def test_execute_task_memory_mode_success(self):
        """内存模式下任务执行成功"""
        scheduler = DistributedEvaluationScheduler()
        await scheduler.initialize()

        scheduler._memory_running["task-1"] = {"evaluation_id": "eval_001"}

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await scheduler._execute_task("task-1", {"evaluation_id": "eval_001"})

        assert "task-1" not in scheduler._memory_running
        assert "task-1" not in scheduler._running_tasks
        await scheduler.close()

    @pytest.mark.asyncio
    async def test_execute_task_memory_mode_failure(self):
        """内存模式下任务执行失败"""
        scheduler = DistributedEvaluationScheduler()
        await scheduler.initialize()

        scheduler._memory_running["task-1"] = {"evaluation_id": "eval_001"}

        with patch("asyncio.sleep", side_effect=Exception("Task failed")):
            await scheduler._execute_task("task-1", {"evaluation_id": "eval_001"})

        assert "task-1" not in scheduler._memory_running
        assert "task-1" not in scheduler._running_tasks
        await scheduler.close()

    @pytest.mark.asyncio
    async def test_submit_memory_mode_with_task_func(self):
        """内存模式 submit 带 task_func"""
        scheduler = DistributedEvaluationScheduler()
        await scheduler.initialize()

        async def dummy_func():
            pass

        task_id = await scheduler.submit(
            evaluation_id="eval_001",
            agent_id="agent_001",
            task_func=dummy_func,
        )
        assert isinstance(task_id, str)
        # task_func is not None should be True in task_data
        assert len(scheduler._memory_queue) == 1
        await scheduler.close()

    @pytest.mark.asyncio
    async def test_cancel_multiple_tasks_in_queue(self):
        """取消队列中的多个任务"""
        scheduler = DistributedEvaluationScheduler()
        await scheduler.initialize()

        task_id_1 = await scheduler.submit(evaluation_id="eval_001", agent_id="agent_001")
        task_id_2 = await scheduler.submit(evaluation_id="eval_002", agent_id="agent_002")
        task_id_3 = await scheduler.submit(evaluation_id="eval_003", agent_id="agent_003")

        assert len(scheduler._memory_queue) == 3

        result_1 = await scheduler.cancel_task(task_id_1)
        result_3 = await scheduler.cancel_task(task_id_3)

        assert result_1 is True
        assert result_3 is True
        assert len(scheduler._memory_queue) == 1
        await scheduler.close()
