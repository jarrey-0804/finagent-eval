"""
资源配额管理

管理评测任务的资源使用限制。
"""

import time
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ResourceUsage:
    """资源使用情况"""

    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    network_mbps: float = 0.0
    active_evaluations: int = 0
    total_tasks_today: int = 0

    def to_dict(self) -> dict:
        return {
            "cpu_percent": self.cpu_percent,
            "memory_mb": self.memory_mb,
            "network_mbps": self.network_mbps,
            "active_evaluations": self.active_evaluations,
            "total_tasks_today": self.total_tasks_today,
        }


@dataclass
class QuotaConfig:
    """配额配置"""

    max_cpu_percent: float = 80.0
    max_memory_mb: float = 4096.0
    max_network_mbps: float = 100.0
    max_concurrent_evaluations: int = 3
    max_daily_evaluations: int = 50


@dataclass
class Allocation:
    """资源分配记录"""

    evaluation_id: str
    allocated_at: float = field(default_factory=time.time)
    cpu_reserved: float = 25.0
    memory_reserved: float = 512.0


class ResourceQuota:
    """
    资源配额管理器

    管理 CPU、内存、网络和并发数的资源限制。
    """

    def __init__(self, config: QuotaConfig | None = None):
        self.config = config or QuotaConfig()
        self._allocations: dict[str, Allocation] = {}

    def can_allocate(self) -> bool:
        """检查是否可以分配资源"""
        usage = self.get_usage()

        if usage.active_evaluations >= self.config.max_concurrent_evaluations:
            return False

        if usage.cpu_percent >= self.config.max_cpu_percent:
            return False

        if usage.memory_mb >= self.config.max_memory_mb:
            return False

        return True

    def allocate(self, evaluation_id: str) -> bool:
        """分配资源"""
        if not self.can_allocate():
            return False

        self._allocations[evaluation_id] = Allocation(
            evaluation_id=evaluation_id,
        )
        return True

    def release(self, evaluation_id: str):
        """释放资源"""
        self._allocations.pop(evaluation_id, None)

    def get_usage(self) -> ResourceUsage:
        """获取当前资源使用情况"""
        active = len(self._allocations)

        cpu = sum(a.cpu_reserved for a in self._allocations.values())
        memory = sum(a.memory_reserved for a in self._allocations.values())

        return ResourceUsage(
            cpu_percent=min(cpu, 100.0),
            memory_mb=memory,
            active_evaluations=active,
        )

    def get_remaining(self) -> dict:
        """获取剩余资源"""
        usage = self.get_usage()
        return {
            "cpu_remaining": max(0, self.config.max_cpu_percent - usage.cpu_percent),
            "memory_remaining_mb": max(0, self.config.max_memory_mb - usage.memory_mb),
            "concurrent_remaining": max(
                0, self.config.max_concurrent_evaluations - usage.active_evaluations
            ),
        }

    def get_allocation(self, evaluation_id: str) -> dict | None:
        """获取分配信息"""
        alloc = self._allocations.get(evaluation_id)
        if alloc is None:
            return None
        return {
            "evaluation_id": alloc.evaluation_id,
            "cpu_reserved": alloc.cpu_reserved,
            "memory_reserved": alloc.memory_reserved,
            "allocated_at": datetime.fromtimestamp(alloc.allocated_at).isoformat(),
        }
