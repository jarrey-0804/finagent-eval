"""
API 响应时间监控与超时中间件

实现 NFR-P-03：API 响应时间 P95 < 500ms 硬性限制。

功能：
- 记录每个 API 请求的响应时间
- 维护滑动窗口响应时间统计（P50/P95/P99）
- 超时请求自动返回 504 Gateway Timeout
- 超过 P95 阈值的慢请求记录告警日志
- 提供 /metrics 端点所需的响应时间指标
"""

import logging
import statistics
import time
from collections import defaultdict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ResponseTimeConfig:
    """响应时间监控配置"""
    # 超时限制（毫秒）
    timeout_ms: float = 5000.0  # 单请求硬超时 5s

    # P95 告警阈值（毫秒）
    p95_threshold_ms: float = 500.0  # SRS 要求 P95 < 500ms

    # P99 告警阈值（毫秒）
    p99_threshold_ms: float = 1000.0

    # 滑动窗口大小（保留最近 N 个请求的响应时间）
    window_size: int = 1000

    # 是否启用超时强制中断
    enable_timeout: bool = True

    # 是否启用慢请求日志
    enable_slow_log: bool = True

    # 慢请求阈值（超过此值记录 warning 日志）
    slow_request_threshold_ms: float = 300.0

    # 豁免路径（不进行超时限制的路径，如健康检查）
    exempt_paths: list[str] = field(default_factory=lambda: [
        "/health", "/live", "/ready", "/docs", "/openapi.json", "/metrics",
    ])


@dataclass
class ResponseTimeStats:
    """响应时间统计"""
    count: int = 0
    total_ms: float = 0.0
    min_ms: float = 0.0
    max_ms: float = 0.0
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    avg_ms: float = 0.0
    timeout_count: int = 0
    slow_count: int = 0

    def to_dict(self) -> dict:
        return {
            "count": self.count,
            "total_ms": round(self.total_ms, 2),
            "min_ms": round(self.min_ms, 2),
            "max_ms": round(self.max_ms, 2),
            "p50_ms": round(self.p50_ms, 2),
            "p95_ms": round(self.p95_ms, 2),
            "p99_ms": round(self.p99_ms, 2),
            "avg_ms": round(self.avg_ms, 2),
            "timeout_count": self.timeout_count,
            "slow_count": self.slow_count,
        }


class ResponseTimeTracker:
    """
    API 响应时间追踪器

    维护每个端点的滑动窗口响应时间统计，提供 P50/P95/P99 计算。
    """

    def __init__(self, config: ResponseTimeConfig | None = None):
        self.config = config or ResponseTimeConfig()
        # 每个端点的响应时间窗口
        self._windows: dict[str, list[float]] = defaultdict(list)
        # 全局统计
        self._global_window: list[float] = []
        self._timeout_count: int = 0
        self._slow_count: int = 0

    def record(self, path: str, elapsed_ms: float, is_timeout: bool = False):
        """记录一次请求的响应时间"""
        # 更新端点窗口
        window = self._windows[path]
        window.append(elapsed_ms)
        if len(window) > self.config.window_size:
            self._windows[path] = window[-self.config.window_size:]

        # 更新全局窗口
        self._global_window.append(elapsed_ms)
        if len(self._global_window) > self.config.window_size:
            self._global_window = self._global_window[-self.config.window_size:]

        if is_timeout:
            self._timeout_count += 1

        if elapsed_ms > self.config.slow_request_threshold_ms:
            self._slow_count += 1
            if self.config.enable_slow_log:
                logger.warning(
                    "慢请求检测: path=%s, elapsed=%.1fms, threshold=%.0fms",
                    path, elapsed_ms, self.config.slow_request_threshold_ms,
                )

    def get_stats(self, path: str | None = None) -> ResponseTimeStats:
        """获取响应时间统计"""
        if path:
            data = self._windows.get(path, [])
        else:
            data = self._global_window

        if not data:
            return ResponseTimeStats()

        sorted_data = sorted(data)
        n = len(sorted_data)

        stats = ResponseTimeStats(
            count=n,
            total_ms=sum(sorted_data),
            min_ms=sorted_data[0],
            max_ms=sorted_data[-1],
            avg_ms=statistics.mean(sorted_data),
            timeout_count=self._timeout_count,
            slow_count=self._slow_count,
        )

        # 百分位计算
        if n >= 2:
            stats.p50_ms = sorted_data[int(n * 0.50)]
            stats.p95_ms = sorted_data[int(n * 0.95)]
            stats.p99_ms = sorted_data[min(int(n * 0.99), n - 1)]
        elif n == 1:
            stats.p50_ms = sorted_data[0]
            stats.p95_ms = sorted_data[0]
            stats.p99_ms = sorted_data[0]

        return stats

    def get_all_endpoint_stats(self) -> dict[str, dict]:
        """获取所有端点的统计"""
        result = {}
        for path in self._windows:
            result[path] = self.get_stats(path).to_dict()
        return result

    def check_p95_health(self) -> bool:
        """检查全局 P95 是否在阈值内"""
        stats = self.get_stats()
        return stats.p95_ms <= self.config.p95_threshold_ms

    def reset(self):
        """重置所有统计"""
        self._windows.clear()
        self._global_window.clear()
        self._timeout_count = 0
        self._slow_count = 0


class ResponseTimeMiddleware:
    """
    API 响应时间中间件

    用于 FastAPI/Starlette 集成，提供：
    1. 请求超时强制中断
    2. 响应时间追踪和统计
    3. P95 健康检查
    4. 慢请求日志告警

    用法::

        tracker = ResponseTimeTracker()
        middleware = ResponseTimeMiddleware(tracker)

        @app.middleware("http")
        async def response_time_middleware(request, call_next):
            return await middleware(request, call_next)
    """

    def __init__(self, tracker: ResponseTimeTracker | None = None):
        self.tracker = tracker or ResponseTimeTracker()

    def is_exempt(self, path: str) -> bool:
        """检查路径是否豁免"""
        return path in self.tracker.config.exempt_paths

    async def __call__(self, request, call_next):
        """
        执行中间件逻辑

        Args:
            request: Starlette Request
            call_next: 下一个中间件/路由处理器

        Returns:
            Response 或 JSONResponse（超时时）
        """
        path = request.url.path

        # 豁免路径直接放行
        if self.is_exempt(path):
            response = await call_next(request)
            return response

        start_time = time.perf_counter()

        try:
            # 带超时执行
            import asyncio
            timeout_sec = self.tracker.config.timeout_ms / 1000.0

            if self.tracker.config.enable_timeout:
                response = await asyncio.wait_for(
                    call_next(request),
                    timeout=timeout_sec,
                )
            else:
                response = await call_next(request)

            elapsed_ms = (time.perf_counter() - start_time) * 1000
            self.tracker.record(path, elapsed_ms)

            # 添加响应时间头
            response.headers["X-Response-Time"] = f"{elapsed_ms:.1f}ms"

            return response

        except TimeoutError:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            self.tracker.record(path, elapsed_ms, is_timeout=True)

            logger.error(
                "请求超时: path=%s, elapsed=%.1fms, timeout=%.0fms",
                path, elapsed_ms, self.tracker.config.timeout_ms,
            )

            from starlette.responses import JSONResponse
            return JSONResponse(
                status_code=504,
                content={
                    "error": "GatewayTimeout",
                    "message": f"请求处理超时（{self.tracker.config.timeout_ms:.0f}ms）",
                    "path": path,
                    "elapsed_ms": round(elapsed_ms, 1),
                },
            )
