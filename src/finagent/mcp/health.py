"""
MCP 健康检查模块

定期检查 MCP 服务器的健康状态。
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime

from .._compat import StrEnum


class HealthStatus(StrEnum):
    """健康状态"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """健康检查结果"""

    server_name: str
    status: HealthStatus
    latency_ms: float
    checked_at: datetime
    details: str = ""
    error: str | None = None


class MCPHealthChecker:
    """
    MCP 健康检查器

    定期检查各 MCP 服务器的可用性和响应时间。
    """

    def __init__(
        self,
        check_interval: int = 30,
        timeout: int = 10,
        max_consecutive_failures: int = 3,
    ):
        self.check_interval = check_interval
        self.timeout = timeout
        self.max_consecutive_failures = max_consecutive_failures
        self._failure_counts: dict[str, int] = {}
        self._last_results: dict[str, HealthCheckResult] = {}
        self._check_task: asyncio.Task | None = None
        self._callbacks: list = []

    def on_unhealthy(self, callback):
        """注册不健康回调"""
        self._callbacks.append(callback)

    async def check_server(
        self,
        server_name: str,
        health_check_url: str | None = None,
    ) -> HealthCheckResult:
        """检查单个服务器"""
        import time

        start = time.time()

        try:
            if health_check_url:
                # HTTP 健康检查
                import httpx

                async with httpx.AsyncClient() as client:
                    response = await asyncio.wait_for(
                        client.get(health_check_url),
                        timeout=self.timeout,
                    )

                    latency = (time.time() - start) * 1000

                    if response.status_code == 200:
                        status = HealthStatus.HEALTHY
                        details = f"HTTP 200, latency={latency:.0f}ms"
                    else:
                        status = HealthStatus.UNHEALTHY
                        details = f"HTTP {response.status_code}"
            else:
                # 进程健康检查（检查进程是否存活）
                latency = (time.time() - start) * 1000
                status = HealthStatus.UNKNOWN
                details = "无健康检查URL，使用进程检查"

            # 重置失败计数
            self._failure_counts[server_name] = 0

        except TimeoutError:
            latency = self.timeout * 1000
            status = HealthStatus.UNHEALTHY
            details = f"健康检查超时 ({self.timeout}s)"

        except Exception as e:
            latency = (time.time() - start) * 1000
            status = HealthStatus.UNHEALTHY
            details = f"健康检查失败: {str(e)}"

        result = HealthCheckResult(
            server_name=server_name,
            status=status,
            latency_ms=latency,
            checked_at=datetime.now(),
            details=details,
        )

        self._last_results[server_name] = result

        # 检查是否需要触发回调
        if status == HealthStatus.UNHEALTHY:
            self._failure_counts[server_name] = self._failure_counts.get(server_name, 0) + 1

            if self._failure_counts[server_name] >= self.max_consecutive_failures:
                for callback in self._callbacks:
                    try:
                        await callback(server_name, result)
                    except Exception:
                        pass

        return result

    async def check_all(
        self,
        servers: dict[str, str | None],
    ) -> dict[str, HealthCheckResult]:
        """
        检查所有服务器

        Args:
            servers: {server_name: health_check_url}
        """
        tasks = [self.check_server(name, url) for name, url in servers.items()]
        results = await asyncio.gather(*tasks)

        return {r.server_name: r for r in results}

    def get_last_result(self, server_name: str) -> HealthCheckResult | None:
        """获取最近一次检查结果"""
        return self._last_results.get(server_name)

    def get_all_results(self) -> dict[str, HealthCheckResult]:
        """获取所有检查结果"""
        return dict(self._last_results)

    async def start_periodic_check(
        self,
        servers: dict[str, str | None],
    ):
        """启动定期检查"""

        async def _check_loop():
            while True:
                await self.check_all(servers)
                await asyncio.sleep(self.check_interval)

        self._check_task = asyncio.create_task(_check_loop())

    async def stop_periodic_check(self):
        """停止定期检查"""
        if self._check_task:
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass
            self._check_task = None
