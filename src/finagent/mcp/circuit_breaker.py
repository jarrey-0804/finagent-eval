"""
熔断器模块

实现熔断器模式，防止级联故障。
对应数据质量治理方案 - 阶段 3
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Any


class CircuitState(Enum):
    """熔断器状态"""
    CLOSED = "closed"       # 正常，请求通过
    OPEN = "open"           # 熔断，请求拒绝
    HALF_OPEN = "half_open" # 半开，试探性请求


@dataclass
class CircuitBreakerConfig:
    """熔断器配置"""
    failure_threshold: int = 5          # 触发熔断的失败次数阈值
    success_threshold: int = 3          # 半开状态下恢复所需的连续成功次数
    timeout: float = 60.0               # 熔断持续时间（秒）
    half_open_max_calls: int = 3        # 半开状态下最大试探请求数


@dataclass
class CircuitBreakerStats:
    """熔断器统计"""
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float | None = None
    total_failures: int = 0
    total_successes: int = 0
    state_changes: list[tuple[float, CircuitState]] = field(default_factory=list)


class CircuitBreaker:
    """
    熔断器

    防止外部服务故障导致级联崩溃。

    状态转换:
    - CLOSED -> OPEN: 失败次数达到阈值
    - OPEN -> HALF_OPEN: 熔断超时
    - HALF_OPEN -> CLOSED: 连续成功次数达到阈值
    - HALF_OPEN -> OPEN: 任一请求失败
    """

    def __init__(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None,
        on_state_change: Callable[[CircuitState, CircuitState], Any] | None = None,
    ):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._stats = CircuitBreakerStats()
        self._on_state_change = on_state_change
        self._half_open_calls = 0

    @property
    def state(self) -> CircuitState:
        """当前状态"""
        return self._stats.state

    @property
    def stats(self) -> CircuitBreakerStats:
        """获取统计信息"""
        return self._stats

    def can_execute(self) -> bool:
        """检查是否可以执行请求"""
        if self._stats.state == CircuitState.CLOSED:
            return True

        if self._stats.state == CircuitState.OPEN:
            # 检查是否超时
            if self._stats.last_failure_time:
                elapsed = time.time() - self._stats.last_failure_time
                if elapsed >= self.config.timeout:
                    self._transition_to(CircuitState.HALF_OPEN)
                    return True
            return False

        if self._stats.state == CircuitState.HALF_OPEN:
            # 限制半开状态下的请求数
            return self._half_open_calls < self.config.half_open_max_calls

        return True

    def record_success(self) -> None:
        """记录成功"""
        self._stats.total_successes += 1

        if self._stats.state == CircuitState.HALF_OPEN:
            self._stats.success_count += 1
            self._half_open_calls += 1

            if self._stats.success_count >= self.config.success_threshold:
                self._transition_to(CircuitState.CLOSED)
                self._stats.failure_count = 0
                self._stats.success_count = 0
                self._half_open_calls = 0

        elif self._stats.state == CircuitState.CLOSED:
            self._stats.failure_count = 0

    def record_failure(self) -> None:
        """记录失败"""
        self._stats.total_failures += 1
        self._stats.failure_count += 1
        self._stats.last_failure_time = time.time()

        if self._stats.state == CircuitState.HALF_OPEN:
            self._half_open_calls += 1
            self._transition_to(CircuitState.OPEN)

        elif self._stats.state == CircuitState.CLOSED:
            if self._stats.failure_count >= self.config.failure_threshold:
                self._transition_to(CircuitState.OPEN)

    def _transition_to(self, new_state: CircuitState) -> None:
        """状态转换"""
        old_state = self._stats.state
        if old_state != new_state:
            self._stats.state = new_state
            self._stats.state_changes.append((time.time(), new_state))

            if self._on_state_change:
                try:
                    self._on_state_change(old_state, new_state)
                except Exception:
                    pass

    def reset(self) -> None:
        """手动重置熔断器"""
        self._transition_to(CircuitState.CLOSED)
        self._stats.failure_count = 0
        self._stats.success_count = 0
        self._half_open_calls = 0

    def get_state_summary(self) -> dict:
        """获取状态摘要"""
        return {
            "name": self.name,
            "state": self._stats.state.value,
            "failure_count": self._stats.failure_count,
            "success_count": self._stats.success_count,
            "total_failures": self._stats.total_failures,
            "total_successes": self._stats.total_successes,
            "last_failure_time": self._stats.last_failure_time,
            "can_execute": self.can_execute(),
        }


class CircuitBreakerRegistry:
    """熔断器注册表（管理多个熔断器）"""

    def __init__(self):
        self._breakers: dict[str, CircuitBreaker] = {}

    def get_or_create(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None,
    ) -> CircuitBreaker:
        """获取或创建熔断器"""
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(name, config)
        return self._breakers[name]

    def get(self, name: str) -> CircuitBreaker | None:
        """获取熔断器"""
        return self._breakers.get(name)

    def remove(self, name: str) -> bool:
        """移除熔断器"""
        if name in self._breakers:
            del self._breakers[name]
            return True
        return False

    def get_all_summaries(self) -> dict[str, dict]:
        """获取所有熔断器摘要"""
        return {name: cb.get_state_summary() for name, cb in self._breakers.items()}

    def reset_all(self) -> None:
        """重置所有熔断器"""
        for cb in self._breakers.values():
            cb.reset()


# 全局熔断器注册表
_circuit_breaker_registry: CircuitBreakerRegistry | None = None


def get_circuit_breaker_registry() -> CircuitBreakerRegistry:
    """获取全局熔断器注册表"""
    global _circuit_breaker_registry
    if _circuit_breaker_registry is None:
        _circuit_breaker_registry = CircuitBreakerRegistry()
    return _circuit_breaker_registry
