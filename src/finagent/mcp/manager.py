"""
MCP 服务器管理器

管理多个 MCP 服务器的生命周期，包括启动、停止、健康监控。
"""

import asyncio
import subprocess
from dataclasses import dataclass, field
from datetime import datetime

from pydantic import BaseModel, Field

from .._compat import StrEnum


class MCPServerStatus(StrEnum):
    """MCP服务器状态"""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    UNHEALTHY = "unhealthy"
    STOPPING = "stopping"
    ERROR = "error"


class MCPServerConfig(BaseModel):
    """MCP服务器配置"""

    name: str = Field(..., description="服务器名称")
    command: str = Field(..., description="启动命令")
    args: list[str] = Field(default_factory=list, description="命令参数")
    env: dict[str, str] = Field(default_factory=dict, description="环境变量")
    working_dir: str | None = Field(None, description="工作目录")

    # 健康检查配置
    health_check_url: str | None = Field(None, description="健康检查URL")
    health_check_interval: int = Field(default=30, description="健康检查间隔(秒)")
    health_check_timeout: int = Field(default=10, description="健康检查超时(秒)")

    # 重启配置
    max_restart_attempts: int = Field(default=3, description="最大重启次数")
    restart_delay: int = Field(default=5, description="重启延迟(秒)")

    # 工具列表
    tools: list[str] = Field(default_factory=list, description="提供的工具列表")


@dataclass
class MCPServerInstance:
    """MCP服务器实例"""

    config: MCPServerConfig
    status: MCPServerStatus = MCPServerStatus.STOPPED
    process: subprocess.Popen | None = None
    started_at: datetime | None = None
    pid: int | None = None
    restart_count: int = 0
    last_health_check: datetime | None = None
    last_error: str | None = None
    metadata: dict = field(default_factory=dict)


class MCPServerManager:
    """
    MCP 服务器管理器

    管理评测系统中所有 MCP 服务器的生命周期。
    支持全量 7 个服务器的配置和管理。
    """

    # 预定义的 MCP 服务器配置
    PREDEFINED_SERVERS = {
        "sec_edgar": MCPServerConfig(
            name="sec_edgar",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-sec-edgar"],
            working_dir=None,
            health_check_url=None,
            tools=["search_filings", "get_filing", "get_company_facts"],
        ),
        "yahoo_finance": MCPServerConfig(
            name="yahoo_finance",
            command="npx",
            args=["-y", "@anthropic/mcp-yahoo-finance"],
            working_dir=None,
            health_check_url=None,
            tools=["get_stock_price", "get_stock_info", "search_stocks"],
        ),
        "akshare": MCPServerConfig(
            name="akshare",
            command="python",
            args=["-m", "mcp_server_akshare"],
            working_dir=None,
            health_check_url=None,
            tools=["get_a_stock_price", "get_a_stock_info", "get_index_data"],
        ),
        "tushare": MCPServerConfig(
            name="tushare",
            command="python",
            args=["-m", "mcp_server_tushare"],
            working_dir=None,
            health_check_url=None,
            tools=["get_daily", "get_adj_factor", "get_stock_basic"],
        ),
        "calculator": MCPServerConfig(
            name="calculator",
            command="npx",
            args=["-y", "@anthropic/mcp-calculator"],
            working_dir=None,
            health_check_url=None,
            tools=["calculate"],
        ),
        "web_search": MCPServerConfig(
            name="web_search",
            command="npx",
            args=["-y", "@anthropic/mcp-web-search"],
            working_dir=None,
            health_check_url=None,
            tools=["search", "fetch"],
        ),
        "filesystem": MCPServerConfig(
            name="filesystem",
            command="npx",
            args=["-y", "@anthropic/mcp-filesystem", "/data"],
            working_dir=None,
            health_check_url=None,
            tools=["read_file", "write_file", "list_directory"],
        ),
    }

    def __init__(self):
        self._servers: dict[str, MCPServerInstance] = {}
        self._health_task: asyncio.Task | None = None

    def register_server(self, config: MCPServerConfig):
        """注册 MCP 服务器"""
        self._servers[config.name] = MCPServerInstance(config=config)

    def register_predefined(self, server_names: list[str] | None = None):
        """注册预定义服务器"""
        names = server_names or list(self.PREDEFINED_SERVERS.keys())
        for name in names:
            if name in self.PREDEFINED_SERVERS:
                self.register_server(self.PREDEFINED_SERVERS[name])

    async def start_server(self, server_name: str) -> bool:
        """启动 MCP 服务器"""
        instance = self._servers.get(server_name)
        if instance is None:
            raise ValueError(f"服务器未注册: {server_name}")

        if instance.status == MCPServerStatus.RUNNING:
            return True

        instance.status = MCPServerStatus.STARTING

        try:
            env = {**dict(instance.config.env)}
            cwd = instance.config.working_dir

            process = subprocess.Popen(
                [instance.config.command] + instance.config.args,
                env=env,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            instance.process = process
            instance.pid = process.pid
            instance.status = MCPServerStatus.RUNNING
            instance.started_at = datetime.now()
            instance.last_error = None

            return True

        except Exception as e:
            instance.status = MCPServerStatus.ERROR
            instance.last_error = str(e)
            return False

    async def stop_server(self, server_name: str) -> bool:
        """停止 MCP 服务器"""
        instance = self._servers.get(server_name)
        if instance is None:
            return False

        instance.status = MCPServerStatus.STOPPING

        if instance.process:
            try:
                instance.process.terminate()
                instance.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                instance.process.kill()
            except Exception:
                pass

            instance.process = None
            instance.pid = None

        instance.status = MCPServerStatus.STOPPED
        instance.started_at = None
        return True

    async def restart_server(self, server_name: str) -> bool:
        """重启 MCP 服务器"""
        await self.stop_server(server_name)
        await asyncio.sleep(1)
        return await self.start_server(server_name)

    async def start_all(self) -> dict[str, bool]:
        """启动所有服务器"""
        results = {}
        for name in self._servers:
            results[name] = await self.start_server(name)
        return results

    async def stop_all(self) -> dict[str, bool]:
        """停止所有服务器"""
        results = {}
        for name in self._servers:
            results[name] = await self.stop_server(name)
        return results

    def get_server_status(self, server_name: str) -> dict | None:
        """获取服务器状态"""
        instance = self._servers.get(server_name)
        if instance is None:
            return None

        return {
            "name": instance.config.name,
            "status": instance.status.value,
            "pid": instance.pid,
            "started_at": instance.started_at.isoformat() if instance.started_at else None,
            "restart_count": instance.restart_count,
            "last_error": instance.last_error,
            "tools": instance.config.tools,
        }

    def list_servers(self) -> list[dict]:
        """列出所有服务器"""
        return [status for name in self._servers if (status := self.get_server_status(name)) is not None]

    def get_available_tools(self) -> dict[str, list[str]]:
        """获取所有可用工具"""
        tools = {}
        for name, instance in self._servers.items():
            if instance.status == MCPServerStatus.RUNNING:
                tools[name] = instance.config.tools
        return tools

    async def cleanup(self):
        """清理所有服务器"""
        await self.stop_all()
