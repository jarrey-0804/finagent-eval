"""
分布式调度器单元测试

测试模块: finagent.pipeline.distributed_scheduler
覆盖: RedisSchedulerConfig, RedisTaskStore, DistributedEvaluationScheduler

注意: 测试环境可能没有 Redis，因此重点测试内存模式回退逻辑。
"""

import asyncio
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
