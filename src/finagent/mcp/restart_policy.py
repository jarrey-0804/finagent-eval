"""
MCP 重启策略模块

提供自动重启策略，当 MCP 服务器故障时自动恢复。
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from .._compat import StrEnum


class RestartStrategy(StrEnum):
    """重启策略"""

    IMMEDIATE = "immediate"  # 立即重启
    DELAYED = "delayed"  # 延迟重启
    EXPONENTIAL_BACKOFF = "exponential_backoff"  # 指数退避
    CIRCUIT_BREAKER = "circuit_breaker"  # 熔断器


@dataclass
class RestartRecord:
    """重启记录"""

    server_name: str
    attempt: int
    strategy: RestartStrategy
    delay_seconds: float
    success: bool
    timestamp: datetime

    def to_dict(self) -> dict:
        return {
            "server_name": self.server_name,
            "attempt": self.attempt,
            "strategy": self.strategy.value,
            "delay_seconds": self.delay_seconds,
            "success": self.success,
            "timestamp": self.timestamp.isoformat(),
        }


class RestartPolicy:
    """
    MCP 服务器重启策略

    支持多种重启策略，防止频繁重启导致雪崩。
    """

    def __init__(
        self,
        strategy: RestartStrategy = RestartStrategy.EXPONENTIAL_BACKOFF,
        max_attempts: int = 5,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_reset_time: int = 300,
    ):
        self.strategy = strategy
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_reset_time = circuit_breaker_reset_time

        self._attempt_counts: dict[str, int] = {}
        self._circuit_open: dict[str, bool] = {}
        self._circuit_opened_at: dict[str, datetime] = {}
        self._records: list[RestartRecord] = []

    def should_restart(self, server_name: str) -> tuple[bool, float]:
        """
        判断是否应该重启

        Returns:
            tuple: (是否应该重启, 延迟秒数)
        """
        # 检查熔断器
        if self._is_circuit_open(server_name):
            return False, 0.0

        # 检查最大尝试次数
        attempts = self._attempt_counts.get(server_name, 0)
        if attempts >= self.max_attempts:
            return False, 0.0

        # 计算延迟
        delay = self._calculate_delay(attempts)

        return True, delay

    async def execute_restart(
        self,
        server_name: str,
        restart_func: Callable,
    ) -> bool:
        """
        执行重启

        Args:
            server_name: 服务器名称
            restart_func: 重启函数 (async) -> bool
        """
        should, delay = self.should_restart(server_name)

        if not should:
            return False

        # 等待延迟
        if delay > 0:
            await asyncio.sleep(delay)

        # 增加尝试计数
        self._attempt_counts[server_name] = self._attempt_counts.get(server_name, 0) + 1
        attempts = self._attempt_counts[server_name]

        # 执行重启
        try:
            success = await restart_func()
        except Exception:
            success = False

        # 记录
        record = RestartRecord(
            server_name=server_name,
            attempt=attempts,
            strategy=self.strategy,
            delay_seconds=delay,
            success=success,
            timestamp=datetime.now(),
        )
        self._records.append(record)

        if success:
            # 重置计数
            self._attempt_counts[server_name] = 0
            self._close_circuit(server_name)
        else:
            # 检查是否需要打开熔断器
            if attempts >= self.circuit_breaker_threshold:
                self._open_circuit(server_name)

        return success

    def reset(self, server_name: str):
        """重置重启策略"""
        self._attempt_counts.pop(server_name, None)
        self._close_circuit(server_name)

    def get_records(
        self,
        server_name: str | None = None,
    ) -> list[dict]:
        """获取重启记录"""
        records = self._records
        if server_name:
            records = [r for r in records if r.server_name == server_name]
        return [r.to_dict() for r in records]

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "strategy": self.strategy.value,
            "max_attempts": self.max_attempts,
            "servers": {
                name: {
                    "attempts": count,
                    "circuit_open": self._is_circuit_open(name),
                }
                for name, count in self._attempt_counts.items()
            },
            "total_restarts": len(self._records),
            "successful_restarts": sum(1 for r in self._records if r.success),
        }

    def _calculate_delay(self, attempt: int) -> float:
        """计算重启延迟"""
        if self.strategy == RestartStrategy.IMMEDIATE:
            return 0.0

        elif self.strategy == RestartStrategy.DELAYED:
            return self.base_delay

        elif self.strategy == RestartStrategy.EXPONENTIAL_BACKOFF:
            delay = self.base_delay * (2**attempt)
            return min(delay, self.max_delay)

        elif self.strategy == RestartStrategy.CIRCUIT_BREAKER:
            return self.base_delay

        return self.base_delay

    def _is_circuit_open(self, server_name: str) -> bool:
        """检查熔断器是否打开"""
        if not self._circuit_open.get(server_name, False):
            return False

        # 检查是否已过重置时间
        opened_at = self._circuit_opened_at.get(server_name)
        if opened_at:
            elapsed = (datetime.now() - opened_at).total_seconds()
            if elapsed >= self.circuit_breaker_reset_time:
                self._close_circuit(server_name)
                return False

        return True

    def _open_circuit(self, server_name: str):
        """打开熔断器"""
        self._circuit_open[server_name] = True
        self._circuit_opened_at[server_name] = datetime.now()

    def _close_circuit(self, server_name: str):
        """关闭熔断器"""
        self._circuit_open[server_name] = False
        self._circuit_opened_at.pop(server_name, None)
