"""
API 限流中间件

提供基于滑动窗口的请求限流功能。
"""

import time
from collections import defaultdict
from dataclasses import dataclass


@dataclass
class RateLimitConfig:
    """限流配置"""

    max_requests: int = 100  # 时间窗口内最大请求数
    window_seconds: int = 60  # 时间窗口(秒)
    burst_size: int = 10  # 突发请求数
    key_func: str = "ip"  # 限流键: ip | user_id | endpoint


@dataclass
class RateLimitResult:
    """限流结果"""

    allowed: bool
    remaining: int
    reset_at: float
    retry_after: float | None = None
    limit: int = 0


class RateLimitMiddleware:
    """
    API 限流中间件

    支持基于 IP、用户 ID 或端点的滑动窗口限流。
    """

    def __init__(self, config: RateLimitConfig | None = None):
        self.config = config or RateLimitConfig()
        self._windows: dict[str, list[float]] = defaultdict(list)

    def check_rate_limit(
        self,
        key: str,
        now: float | None = None,
    ) -> RateLimitResult:
        """
        检查限流

        Args:
            key: 限流键（IP、用户ID等）
            now: 当前时间戳

        Returns:
            限流结果
        """
        now = now or time.time()
        window_start = now - self.config.window_seconds

        # 清理过期记录
        self._windows[key] = [t for t in self._windows[key] if t > window_start]

        current_count = len(self._windows[key])

        if current_count >= self.config.max_requests:
            # 计算重试时间
            oldest = min(self._windows[key]) if self._windows[key] else now
            retry_after = oldest + self.config.window_seconds - now

            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_at=oldest + self.config.window_seconds,
                retry_after=max(0, retry_after),
                limit=self.config.max_requests,
            )

        return RateLimitResult(
            allowed=True,
            remaining=self.config.max_requests - current_count - 1,
            reset_at=now + self.config.window_seconds,
            limit=self.config.max_requests,
        )

    def record_request(self, key: str, now: float | None = None):
        """记录请求"""
        now = now or time.time()
        self._windows[key].append(now)

    def get_usage(self, key: str) -> dict:
        """获取使用情况"""
        now = time.time()
        window_start = now - self.config.window_seconds

        active = [t for t in self._windows.get(key, []) if t > window_start]

        return {
            "key": key,
            "requests_in_window": len(active),
            "max_requests": self.config.max_requests,
            "window_seconds": self.config.window_seconds,
            "utilization": len(active) / self.config.max_requests
            if self.config.max_requests > 0
            else 0,
        }

    def cleanup(self, max_age: float = 3600):
        """清理过期数据"""
        now = time.time()
        expired_keys = [
            key
            for key, timestamps in self._windows.items()
            if not timestamps or timestamps[-1] < now - max_age
        ]
        for key in expired_keys:
            del self._windows[key]

    def reset(self, key: str | None = None):
        """重置限流"""
        if key:
            self._windows.pop(key, None)
        else:
            self._windows.clear()
