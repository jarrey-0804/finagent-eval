"""
重试机制模块

实现指数退避重试策略。
对应数据质量治理方案 - 阶段 3
"""

import asyncio
import random
from dataclasses import dataclass
from typing import Callable, TypeVar, Any
from functools import wraps

T = TypeVar("T")


@dataclass
class RetryConfig:
    """重试配置"""
    max_attempts: int = 3           # 最大尝试次数
    base_delay: float = 1.0         # 基础延迟（秒）
    max_delay: float = 60.0         # 最大延迟（秒）
    exponential_base: float = 2.0   # 指数基数
    jitter: bool = True             # 是否添加随机抖动
    jitter_max: float = 1.0         # 最大抖动（秒）
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,)  # 可重试的异常类型


class RetryExhaustedError(Exception):
    """重试次数耗尽错误"""
    def __init__(self, attempts: int, last_exception: Exception | None = None):
        self.attempts = attempts
        self.last_exception = last_exception
        msg = f"重试 {attempts} 次后仍然失败"
        if last_exception:
            msg += f": {last_exception}"
        super().__init__(msg)


class RetryHandler:
    """重试处理器"""

    def __init__(self, config: RetryConfig | None = None):
        self.config = config or RetryConfig()

    def calculate_delay(self, attempt: int) -> float:
        """
        计算重试延迟

        使用指数退避算法：delay = min(base_delay * (base ^ attempt), max_delay)
        可选添加随机抖动避免惊群效应
        """
        delay = self.config.base_delay * (self.config.exponential_base ** attempt)
        delay = min(delay, self.config.max_delay)

        if self.config.jitter:
            # 添加随机抖动 [-jitter_max/2, jitter_max/2]
            jitter = random.uniform(
                -self.config.jitter_max / 2,
                self.config.jitter_max / 2
            )
            delay = max(0, delay + jitter)

        return delay

    async def execute(
        self,
        func: Callable[..., T],
        *args,
        on_retry: Callable[[int, Exception, float], Any] | None = None,
        **kwargs,
    ) -> T:
        """
        执行带重试的函数

        Args:
            func: 要执行的函数
            *args: 函数参数
            on_retry: 重试回调 (attempt, exception, next_delay)
            **kwargs: 函数关键字参数

        Returns:
            函数执行结果

        Raises:
            RetryExhaustedError: 重试次数耗尽
        """
        last_exception: Exception | None = None

        for attempt in range(self.config.max_attempts):
            try:
                return await func(*args, **kwargs)
            except self.config.retryable_exceptions as e:
                last_exception = e

                if attempt < self.config.max_attempts - 1:
                    delay = self.calculate_delay(attempt)

                    if on_retry:
                        try:
                            on_retry(attempt + 1, e, delay)
                        except Exception:
                            pass

                    await asyncio.sleep(delay)

        raise RetryExhaustedError(self.config.max_attempts, last_exception)

    def execute_sync(
        self,
        func: Callable[..., T],
        *args,
        on_retry: Callable[[int, Exception, float], Any] | None = None,
        **kwargs,
    ) -> T:
        """同步版本的执行"""
        last_exception: Exception | None = None

        for attempt in range(self.config.max_attempts):
            try:
                return func(*args, **kwargs)
            except self.config.retryable_exceptions as e:
                last_exception = e

                if attempt < self.config.max_attempts - 1:
                    delay = self.calculate_delay(attempt)

                    if on_retry:
                        try:
                            on_retry(attempt + 1, e, delay)
                        except Exception:
                            pass

                    import time
                    time.sleep(delay)

        raise RetryExhaustedError(self.config.max_attempts, last_exception)


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
):
    """
    重试装饰器

    用法:
        @with_retry(max_attempts=3, base_delay=1.0)
        async def fetch_data():
            ...
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        retryable_exceptions=retryable_exceptions,
    )
    handler = RetryHandler(config)

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            return await handler.execute(func, *args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            return handler.execute_sync(func, *args, **kwargs)

        # 根据函数类型返回合适的包装器
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
