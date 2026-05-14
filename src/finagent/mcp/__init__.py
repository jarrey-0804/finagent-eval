"""
MCP 服务器管理模块

提供 MCP (Model Context Protocol) 服务器的生命周期管理、健康检查、自动重启、
熔断器、重试机制和缓存支持。
"""

from .health import HealthStatus, MCPHealthChecker
from .manager import MCPServerConfig, MCPServerManager, MCPServerStatus
from .restart_policy import RestartPolicy, RestartStrategy
from .circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerRegistry,
    CircuitState,
    get_circuit_breaker_registry,
)
from .retry import (
    RetryConfig,
    RetryHandler,
    RetryExhaustedError,
    with_retry,
)
from .cache import (
    DataCache,
    MCPDataCache,
    MemoryCacheBackend,
    CacheBackend,
)

__all__ = [
    # 基础组件
    "MCPServerManager",
    "MCPServerConfig",
    "MCPServerStatus",
    "MCPHealthChecker",
    "HealthStatus",
    "RestartPolicy",
    "RestartStrategy",
    # 熔断器
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerRegistry",
    "CircuitState",
    "get_circuit_breaker_registry",
    # 重试机制
    "RetryConfig",
    "RetryHandler",
    "RetryExhaustedError",
    "with_retry",
    # 缓存
    "DataCache",
    "MCPDataCache",
    "MemoryCacheBackend",
    "CacheBackend",
]
