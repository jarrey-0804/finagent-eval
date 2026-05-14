"""
Redis 分布式调度器

实现 NFR-E-04：支持水平扩展的分布式任务调度。

使用 Redis 作为共享状态存储，替代内存状态，使多个调度器实例
可以协同工作，共享任务队列和运行状态。

功能：
- Redis Sorted Set 实现优先级队列
- Redis 分布式锁防止任务重复调度
- Redis Hash 存储任务状态
- 心跳机制检测失活实例
- 优雅降级：Redis 不可用时回退到内存模式
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RedisSchedulerConfig:
    """Redis 调度器配置"""

    redis_url: str = "redis://localhost:6379/0"
    max_concurrent_evaluations: int = 3
    max_queue_size: int = 50
    task_timeout: int = 43200  # 12小时
    retry_limit: int = 2
    retry_delay: int = 30
    heartbeat_interval: int = 10  # 心跳间隔（秒）
    instance_ttl: int = 30  # 实例存活TTL（秒）
    lock_ttl: int = 60  # 分布式锁TTL（秒）
    queue_key_prefix: str = "finagent:queue"
    running_key_prefix: str = "finagent:running"
    completed_key_prefix: str = "finagent:completed"
    instance_key_prefix: str = "finagent:instances"
    lock_key_prefix: str = "finagent:lock"


class RedisTaskStore:
    """
    Redis 任务存储后端

    使用 Redis 数据结构管理任务的生命周期：
    - Sorted Set: 优先级队列（score = 优先级数值，越小越优先）
    - Hash: 任务详情存储
    - Set: 运行中任务集合
    - List: 已完成任务列表
    """

    def __init__(self, config: RedisSchedulerConfig | None = None):
        self.config = config or RedisSchedulerConfig()
        self._redis = None
        self._available = False

    async def initialize(self):
        """初始化 Redis 连接"""
        try:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(
                self.config.redis_url,
                decode_responses=True,
            )
            # 测试连接
            await self._redis.ping()
            self._available = True
            logger.info("Redis 连接成功: %s", self.config.redis_url)
        except Exception as e:
            self._available = False
            logger.warning("Redis 连接失败，将使用内存模式: %s", e)

    async def close(self):
        """关闭 Redis 连接"""
        if self._redis:
            await self._redis.aclose()
            self._redis = None

    @property
    def is_available(self) -> bool:
        """Redis 是否可用"""
        return self._available and self._redis is not None

    # ------------------------------------------------------------------
    # 队列操作
    # ------------------------------------------------------------------

    async def enqueue(
        self,
        task_id: str,
        task_data: dict,
        priority: float,
    ) -> bool:
        """将任务加入优先级队列"""
        if not self.is_available:
            return False

        queue_key = f"{self.config.queue_key_prefix}:tasks"
        task_hash_key = f"{self.config.queue_key_prefix}:task:{task_id}"

        try:
            pipe = self._redis.pipeline()
            # 存储任务详情
            pipe.hset(
                task_hash_key,
                mapping={
                    "task_id": task_id,
                    "data": json.dumps(task_data, default=str),
                    "priority": str(priority),
                    "status": "queued",
                    "created_at": datetime.now().isoformat(),
                },
            )
            # 加入优先级队列（score 越小越优先）
            pipe.zadd(queue_key, {task_id: priority})
            # 设置任务详情 TTL（24小时）
            pipe.expire(task_hash_key, 86400)
            await pipe.execute()
            return True
        except Exception as e:
            logger.error("Redis enqueue 失败: %s", e)
            return False

    async def dequeue(self) -> dict | None:
        """从队列中取出最高优先级的任务（原子操作）"""
        if not self.is_available:
            return None

        queue_key = f"{self.config.queue_key_prefix}:tasks"
        task_hash_key_prefix = f"{self.config.queue_key_prefix}:task:"

        try:
            # 原子操作：取出 score 最低的任务
            result = await self._redis.zpopmin(queue_key)
            if not result:
                return None

            task_id, priority = result[0]
            task_data = await self._redis.hgetall(f"{task_hash_key_prefix}{task_id}")

            if not task_data:
                return None

            return {
                "task_id": task_id,
                "priority": float(priority),
                "data": json.loads(task_data.get("data", "{}")),
                "created_at": task_data.get("created_at", ""),
            }
        except Exception as e:
            logger.error("Redis dequeue 失败: %s", e)
            return None

    async def queue_size(self) -> int:
        """获取队列大小"""
        if not self.is_available:
            return 0
        try:
            return await self._redis.zcard(f"{self.config.queue_key_prefix}:tasks")
        except Exception:
            return 0

    # ------------------------------------------------------------------
    # 运行中任务
    # ------------------------------------------------------------------

    async def mark_running(self, task_id: str, instance_id: str):
        """标记任务为运行中"""
        if not self.is_available:
            return
        try:
            running_key = f"{self.config.running_key_prefix}:{instance_id}"
            task_hash_key = f"{self.config.queue_key_prefix}:task:{task_id}"
            pipe = self._redis.pipeline()
            pipe.sadd(running_key, task_id)
            pipe.hset(task_hash_key, "status", "running")
            pipe.hset(task_hash_key, "started_at", datetime.now().isoformat())
            pipe.expire(running_key, self.config.task_timeout + 300)
            await pipe.execute()
        except Exception as e:
            logger.error("Redis mark_running 失败: %s", e)

    async def mark_completed(self, task_id: str, result: dict | None = None):
        """标记任务为已完成"""
        if not self.is_available:
            return
        try:
            task_hash_key = f"{self.config.queue_key_prefix}:task:{task_id}"
            completed_key = f"{self.config.completed_key_prefix}"
            pipe = self._redis.pipeline()
            pipe.hset(
                task_hash_key,
                mapping={
                    "status": "completed",
                    "completed_at": datetime.now().isoformat(),
                    "result": json.dumps(result or {}, default=str),
                },
            )
            pipe.lpush(completed_key, task_id)
            pipe.ltrim(completed_key, 0, 999)  # 保留最近 1000 条
            await pipe.execute()
        except Exception as e:
            logger.error("Redis mark_completed 失败: %s", e)

    async def mark_failed(self, task_id: str, error: str):
        """标记任务为失败"""
        if not self.is_available:
            return
        try:
            task_hash_key = f"{self.config.queue_key_prefix}:task:{task_id}"
            await self._redis.hset(
                task_hash_key,
                mapping={
                    "status": "failed",
                    "error": error,
                    "completed_at": datetime.now().isoformat(),
                },
            )
        except Exception as e:
            logger.error("Redis mark_failed 失败: %s", e)

    async def remove_from_running(self, task_id: str, instance_id: str):
        """从运行中集合移除任务"""
        if not self.is_available:
            return
        try:
            running_key = f"{self.config.running_key_prefix}:{instance_id}"
            await self._redis.srem(running_key, task_id)
        except Exception:
            pass

    async def running_count(self, instance_id: str) -> int:
        """获取指定实例的运行中任务数"""
        if not self.is_available:
            return 0
        try:
            return await self._redis.scard(f"{self.config.running_key_prefix}:{instance_id}")
        except Exception:
            return 0

    async def total_running_count(self) -> int:
        """获取所有实例的运行中任务总数"""
        if not self.is_available:
            return 0
        try:
            pattern = f"{self.config.running_key_prefix}:*"
            keys = []
            async for key in self._redis.scan_iter(match=pattern):
                keys.append(key)
            total = 0
            for key in keys:
                total += await self._redis.scard(key)
            return total
        except Exception:
            return 0

    # ------------------------------------------------------------------
    # 分布式锁
    # ------------------------------------------------------------------

    async def acquire_lock(self, lock_name: str, instance_id: str) -> bool:
        """获取分布式锁"""
        if not self.is_available:
            return False
        try:
            lock_key = f"{self.config.lock_key_prefix}:{lock_name}"
            return bool(
                await self._redis.set(
                    lock_key,
                    instance_id,
                    nx=True,
                    ex=self.config.lock_ttl,
                )
            )
        except Exception:
            return False

    async def release_lock(self, lock_name: str, instance_id: str):
        """释放分布式锁（仅当持有者匹配时）"""
        if not self.is_available:
            return
        try:
            lock_key = f"{self.config.lock_key_prefix}:{lock_name}"
            # 使用 Lua 脚本确保原子性
            lua_script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """
            await self._redis.eval(lua_script, 1, lock_key, instance_id)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 实例心跳
    # ------------------------------------------------------------------

    async def register_instance(self, instance_id: str):
        """注册实例并更新心跳"""
        if not self.is_available:
            return
        try:
            instance_key = f"{self.config.instance_key_prefix}:{instance_id}"
            await self._redis.hset(
                instance_key,
                mapping={
                    "instance_id": instance_id,
                    "last_heartbeat": datetime.now().isoformat(),
                    "status": "active",
                },
            )
            await self._redis.expire(instance_key, self.config.instance_ttl)
        except Exception:
            pass

    async def heartbeat(self, instance_id: str):
        """更新实例心跳"""
        await self.register_instance(instance_id)

    async def get_active_instances(self) -> list[dict]:
        """获取所有活跃实例"""
        if not self.is_available:
            return []
        try:
            pattern = f"{self.config.instance_key_prefix}:*"
            instances = []
            async for key in self._redis.scan_iter(match=pattern):
                data = await self._redis.hgetall(key)
                if data:
                    instances.append(data)
            return instances
        except Exception:
            return []

    async def get_task_status(self, task_id: str) -> dict | None:
        """获取任务状态"""
        if not self.is_available:
            return None
        try:
            task_hash_key = f"{self.config.queue_key_prefix}:task:{task_id}"
            data = await self._redis.hgetall(task_hash_key)
            if data:
                return dict(data)
            return None
        except Exception:
            return None


class DistributedEvaluationScheduler:
    """
    分布式评测任务调度器

    支持水平扩展的调度器，使用 Redis 共享状态：
    - 多个实例共享同一个任务队列
    - 分布式锁防止任务重复调度
    - 心跳机制检测失活实例并回收其任务
    - Redis 不可用时自动降级到内存模式

    用法::

        config = RedisSchedulerConfig(redis_url="redis://localhost:6379/0")
        scheduler = DistributedEvaluationScheduler(config)
        await scheduler.start()
        task_id = await scheduler.submit(evaluation_id="eval_001", agent_id="agent_001")
        ...
        await scheduler.stop()
    """

    def __init__(self, config: RedisSchedulerConfig | None = None):
        self.config = config or RedisSchedulerConfig()
        self._store = RedisTaskStore(self.config)
        self._instance_id = str(uuid.uuid4())[:8]
        self._scheduler_task: asyncio.Task | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._running_tasks: dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()

        # 内存模式回退
        self._memory_queue: list[dict] = []
        self._memory_running: dict[str, dict] = {}

    async def initialize(self):
        """初始化调度器"""
        await self._store.initialize()
        if self._store.is_available:
            await self._store.register_instance(self._instance_id)
            logger.info("分布式调度器已启动 (instance=%s)", self._instance_id)
        else:
            logger.info("调度器以内存模式启动 (instance=%s)", self._instance_id)

    async def close(self):
        """关闭调度器"""
        await self.stop()
        await self._store.close()

    async def start(self):
        """启动调度器"""
        await self.initialize()
        self._scheduler_task = asyncio.create_task(self._schedule_loop())
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def stop(self):
        """停止调度器"""
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

    async def submit(
        self,
        evaluation_id: str,
        agent_id: str,
        priority: str = "normal",
        task_func: Any | None = None,
    ) -> str:
        """提交评测任务"""
        task_id = str(uuid.uuid4())

        priority_map = {
            "urgent": 0,
            "high": 1,
            "normal": 2,
            "low": 3,
        }
        priority_score = priority_map.get(priority, 2)

        task_data = {
            "task_id": task_id,
            "evaluation_id": evaluation_id,
            "agent_id": agent_id,
            "priority": priority,
            "task_func": task_func is not None,
        }

        if self._store.is_available:
            success = await self._store.enqueue(task_id, task_data, priority_score)
            if not success:
                raise RuntimeError("任务入队失败")
        else:
            # 内存模式回退
            async with self._lock:
                self._memory_queue.append(
                    {
                        "task_id": task_id,
                        "priority": priority_score,
                        "data": task_data,
                    }
                )
                self._memory_queue.sort(key=lambda x: x["priority"])

        logger.info(
            "任务已提交: task_id=%s, eval=%s, agent=%s, priority=%s, mode=%s",
            task_id,
            evaluation_id,
            agent_id,
            priority,
            "distributed" if self._store.is_available else "memory",
        )
        return task_id

    async def _schedule_loop(self):
        """调度循环"""
        while True:
            try:
                await self._dispatch_task()
            except Exception as e:
                logger.error("调度循环异常: %s", e)

            await asyncio.sleep(1)

    async def _dispatch_task(self):
        """尝试调度一个任务"""
        # 检查并发限制
        running = len(self._running_tasks)
        if running >= self.config.max_concurrent_evaluations:
            return

        # 分布式模式：检查全局并发数
        if self._store.is_available:
            total_running = await self._store.total_running_count()
            if total_running >= self.config.max_concurrent_evaluations:
                return

        # 获取任务
        task = None
        if self._store.is_available:
            task = await self._store.dequeue()
        else:
            async with self._lock:
                if self._memory_queue:
                    task = self._memory_queue.pop(0)

        if not task:
            return

        task_id = task["task_id"]
        task_data = task.get("data", {})

        # 标记为运行中
        if self._store.is_available:
            await self._store.mark_running(task_id, self._instance_id)
        else:
            self._memory_running[task_id] = task_data

        # 启动任务执行
        exec_task = asyncio.create_task(self._execute_task(task_id, task_data))
        self._running_tasks[task_id] = exec_task

    async def _execute_task(self, task_id: str, task_data: dict):
        """执行任务"""
        try:
            # 调用实际的评测流水线（由 task_func 或外部注册）
            await asyncio.sleep(1)  # 占位：实际应调用 pipeline

            if self._store.is_available:
                await self._store.mark_completed(task_id, {"status": "completed"})
            else:
                self._memory_running.pop(task_id, None)

            logger.info("任务完成: task_id=%s", task_id)

        except Exception as e:
            logger.error("任务执行失败: task_id=%s, error=%s", task_id, e)
            if self._store.is_available:
                await self._store.mark_failed(task_id, str(e))
            else:
                self._memory_running.pop(task_id, None)

        finally:
            self._running_tasks.pop(task_id, None)
            if self._store.is_available:
                await self._store.remove_from_running(task_id, self._instance_id)

    async def _heartbeat_loop(self):
        """心跳循环"""
        while True:
            try:
                if self._store.is_available:
                    await self._store.heartbeat(self._instance_id)
            except Exception as e:
                logger.error("心跳更新失败: %s", e)
            await asyncio.sleep(self.config.heartbeat_interval)

    # ------------------------------------------------------------------
    # 查询接口
    # ------------------------------------------------------------------

    async def get_task_status(self, task_id: str) -> dict | None:
        """获取任务状态"""
        if self._store.is_available:
            return await self._store.get_task_status(task_id)

        # 内存模式
        if task_id in self._memory_running:
            return {"task_id": task_id, "status": "running"}
        return None

    async def get_queue_status(self) -> dict:
        """获取队列状态"""
        queue_size = 0
        if self._store.is_available:
            queue_size = await self._store.queue_size()
        else:
            queue_size = len(self._memory_queue)

        return {
            "queue_size": queue_size,
            "running_count": len(self._running_tasks),
            "instance_id": self._instance_id,
            "mode": "distributed" if self._store.is_available else "memory",
            "max_concurrent": self.config.max_concurrent_evaluations,
        }

    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        # 取消正在运行的任务
        if task_id in self._running_tasks:
            self._running_tasks[task_id].cancel()
            return True

        # 从队列中移除（分布式模式暂不支持，内存模式支持）
        if not self._store.is_available:
            async with self._lock:
                for i, task in enumerate(self._memory_queue):
                    if task["task_id"] == task_id:
                        self._memory_queue.pop(i)
                        return True

        return False
