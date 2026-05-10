"""
MCP 模块单元测试

覆盖 mcp/health.py、mcp/manager.py、mcp/restart_policy.py 三个模块。
"""

import asyncio
import subprocess
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from finagent.mcp.health import HealthCheckResult, HealthStatus, MCPHealthChecker
from finagent.mcp.manager import (
    MCPServerConfig,
    MCPServerInstance,
    MCPServerManager,
    MCPServerStatus,
)
from finagent.mcp.restart_policy import (
    RestartPolicy,
    RestartRecord,
    RestartStrategy,
)


# ===========================================================================
# mcp/health.py 测试
# ===========================================================================


class TestMCPHealthCheckerInit:
    """测试 MCPHealthChecker 初始化"""

    def test_init_defaults(self):
        checker = MCPHealthChecker()
        assert checker.check_interval == 30
        assert checker.timeout == 10
        assert checker.max_consecutive_failures == 3
        assert checker._failure_counts == {}
        assert checker._last_results == {}

    def test_init_custom_params(self):
        checker = MCPHealthChecker(
            check_interval=60,
            timeout=20,
            max_consecutive_failures=5,
        )
        assert checker.check_interval == 60
        assert checker.timeout == 20
        assert checker.max_consecutive_failures == 5


class TestMCPHealthCheckerCallbacks:
    """测试回调注册"""

    def test_on_unhealthy_register_callback(self):
        checker = MCPHealthChecker()
        callback = MagicMock()
        checker.on_unhealthy(callback)
        assert callback in checker._callbacks

    def test_on_unhealthy_multiple_callbacks(self):
        checker = MCPHealthChecker()
        cb1 = MagicMock()
        cb2 = MagicMock()
        checker.on_unhealthy(cb1)
        checker.on_unhealthy(cb2)
        assert len(checker._callbacks) == 2


class TestMCPHealthCheckerCheckServer:
    """测试单服务器健康检查"""

    @pytest.mark.asyncio
    async def test_check_server_no_url(self):
        """无健康检查 URL 时返回 UNKNOWN"""
        checker = MCPHealthChecker()
        result = await checker.check_server("test_server", health_check_url=None)
        assert result.server_name == "test_server"
        assert result.status == HealthStatus.UNKNOWN
        assert result.latency_ms >= 0
        assert result.error is None

    @pytest.mark.asyncio
    async def test_check_server_http_200(self):
        """HTTP 200 返回 HEALTHY"""
        checker = MCPHealthChecker()
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await checker.check_server("test_server", health_check_url="http://localhost:8080/health")

        assert result.status == HealthStatus.HEALTHY
        assert "HTTP 200" in result.details

    @pytest.mark.asyncio
    async def test_check_server_http_500(self):
        """HTTP 500 返回 UNHEALTHY"""
        checker = MCPHealthChecker()
        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await checker.check_server("test_server", health_check_url="http://localhost:8080/health")

        assert result.status == HealthStatus.UNHEALTHY
        assert "HTTP 500" in result.details

    @pytest.mark.asyncio
    async def test_check_server_timeout(self):
        """超时返回 UNHEALTHY"""
        checker = MCPHealthChecker(timeout=1)

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=TimeoutError("timeout"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await checker.check_server("test_server", health_check_url="http://localhost:8080/health")

        assert result.status == HealthStatus.UNHEALTHY
        assert "超时" in result.details

    @pytest.mark.asyncio
    async def test_check_server_exception(self):
        """异常返回 UNHEALTHY"""
        checker = MCPHealthChecker()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=Exception("connection refused"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await checker.check_server("test_server", health_check_url="http://localhost:8080/health")

        assert result.status == HealthStatus.UNHEALTHY
        assert "connection refused" in result.details

    @pytest.mark.asyncio
    async def test_check_server_stores_last_result(self):
        """检查结果被存储"""
        checker = MCPHealthChecker()
        await checker.check_server("test_server")
        assert checker.get_last_result("test_server") is not None

    @pytest.mark.asyncio
    async def test_check_server_resets_failure_on_success(self):
        """成功检查重置失败计数"""
        checker = MCPHealthChecker()
        checker._failure_counts["test_server"] = 2
        await checker.check_server("test_server")
        assert checker._failure_counts["test_server"] == 0


class TestMCPHealthCheckerCallbacksTrigger:
    """测试不健康回调触发"""

    @pytest.mark.asyncio
    async def test_callback_triggered_on_max_failures(self):
        """连续失败达到阈值时触发回调"""
        checker = MCPHealthChecker(max_consecutive_failures=2)
        callback = AsyncMock()
        checker.on_unhealthy(callback)

        # 使用 mock httpx 让 HTTP 检查失败
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=Exception("connection refused"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            # 第一次失败
            await checker.check_server("test_server", health_check_url="http://fail/health")
            assert callback.call_count == 0

            # 第二次失败 -> 触发回调
            await checker.check_server("test_server", health_check_url="http://fail/health")
            assert callback.call_count == 1

    @pytest.mark.asyncio
    async def test_callback_exception_ignored(self):
        """回调异常不影响主流程"""
        checker = MCPHealthChecker(max_consecutive_failures=1)

        async def bad_callback(name, result):
            raise RuntimeError("callback error")

        checker.on_unhealthy(bad_callback)
        # 不应抛出异常
        result = await checker.check_server("test_server", health_check_url="http://fail/health")
        assert result.status == HealthStatus.UNHEALTHY


class TestMCPHealthCheckerCheckAll:
    """测试批量检查"""

    @pytest.mark.asyncio
    async def test_check_all_servers(self):
        checker = MCPHealthChecker()
        servers = {"srv1": None, "srv2": None}
        results = await checker.check_all(servers)
        assert len(results) == 2
        assert "srv1" in results
        assert "srv2" in results


class TestMCPHealthCheckerGetResults:
    """测试获取检查结果"""

    @pytest.mark.asyncio
    async def test_get_last_result_none(self):
        checker = MCPHealthChecker()
        assert checker.get_last_result("nonexistent") is None

    @pytest.mark.asyncio
    async def test_get_all_results_empty(self):
        checker = MCPHealthChecker()
        assert checker.get_all_results() == {}

    @pytest.mark.asyncio
    async def test_get_all_results_populated(self):
        checker = MCPHealthChecker()
        await checker.check_server("srv1")
        await checker.check_server("srv2")
        results = checker.get_all_results()
        assert len(results) == 2


class TestMCPHealthCheckerPeriodic:
    """测试定期检查"""

    @pytest.mark.asyncio
    async def test_start_and_stop_periodic_check(self):
        checker = MCPHealthChecker(check_interval=1)
        servers = {"srv1": None}

        await checker.start_periodic_check(servers)
        assert checker._check_task is not None

        # 让它运行一小段时间
        await asyncio.sleep(0.1)

        await checker.stop_periodic_check()
        assert checker._check_task is None

    @pytest.mark.asyncio
    async def test_stop_periodic_check_no_task(self):
        """没有任务时停止不报错"""
        checker = MCPHealthChecker()
        await checker.stop_periodic_check()  # 不应抛出异常


class TestHealthCheckResult:
    """测试 HealthCheckResult 数据类"""

    def test_result_creation(self):
        result = HealthCheckResult(
            server_name="test",
            status=HealthStatus.HEALTHY,
            latency_ms=50.0,
            checked_at=datetime.now(timezone.utc),
            details="OK",
        )
        assert result.server_name == "test"
        assert result.status == "healthy"
        assert result.error is None


# ===========================================================================
# mcp/manager.py 测试
# ===========================================================================


class TestMCPServerManagerInit:
    """测试 MCPServerManager 初始化"""

    def test_init_empty(self):
        manager = MCPServerManager()
        assert manager._servers == {}

    def test_predefined_servers_exist(self):
        assert "sec_edgar" in MCPServerManager.PREDEFINED_SERVERS
        assert "yahoo_finance" in MCPServerManager.PREDEFINED_SERVERS
        assert len(MCPServerManager.PREDEFINED_SERVERS) == 7


class TestMCPServerManagerRegister:
    """测试服务器注册"""

    def test_register_server(self):
        manager = MCPServerManager()
        config = MCPServerConfig(name="test_server", command="python")
        manager.register_server(config)
        assert "test_server" in manager._servers
        assert manager._servers["test_server"].config.name == "test_server"
        assert manager._servers["test_server"].status == MCPServerStatus.STOPPED

    def test_register_predefined_all(self):
        manager = MCPServerManager()
        manager.register_predefined()
        assert len(manager._servers) == 7

    def test_register_predefined_selected(self):
        manager = MCPServerManager()
        manager.register_predefined(["sec_edgar", "calculator"])
        assert len(manager._servers) == 2
        assert "sec_edgar" in manager._servers
        assert "calculator" in manager._servers

    def test_register_predefined_invalid_name(self):
        manager = MCPServerManager()
        manager.register_predefined(["nonexistent"])
        assert len(manager._servers) == 0


class TestMCPServerManagerStartStop:
    """测试服务器启停"""

    @pytest.mark.asyncio
    async def test_start_server_not_registered(self):
        manager = MCPServerManager()
        with pytest.raises(ValueError, match="服务器未注册"):
            await manager.start_server("nonexistent")

    @pytest.mark.asyncio
    async def test_start_server_success(self):
        manager = MCPServerManager()
        config = MCPServerConfig(name="test", command="echo", args=["hello"])
        manager.register_server(config)

        mock_process = MagicMock(spec=subprocess.Popen)
        mock_process.pid = 12345
        mock_process.stdout = MagicMock()
        mock_process.stderr = MagicMock()

        with patch("subprocess.Popen", return_value=mock_process):
            result = await manager.start_server("test")

        assert result is True
        instance = manager._servers["test"]
        assert instance.status == MCPServerStatus.RUNNING
        assert instance.pid == 12345
        assert instance.started_at is not None

    @pytest.mark.asyncio
    async def test_start_server_already_running(self):
        manager = MCPServerManager()
        config = MCPServerConfig(name="test", command="echo")
        manager.register_server(config)
        manager._servers["test"].status = MCPServerStatus.RUNNING

        result = await manager.start_server("test")
        assert result is True

    @pytest.mark.asyncio
    async def test_start_server_failure(self):
        manager = MCPServerManager()
        config = MCPServerConfig(name="test", command="nonexistent_cmd")
        manager.register_server(config)

        with patch("subprocess.Popen", side_effect=OSError("command not found")):
            result = await manager.start_server("test")

        assert result is False
        assert manager._servers["test"].status == MCPServerStatus.ERROR
        assert "command not found" in manager._servers["test"].last_error

    @pytest.mark.asyncio
    async def test_stop_server_not_registered(self):
        manager = MCPServerManager()
        result = await manager.stop_server("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_stop_server_success(self):
        manager = MCPServerManager()
        config = MCPServerConfig(name="test", command="echo")
        manager.register_server(config)

        mock_process = MagicMock(spec=subprocess.Popen)
        mock_process.pid = 12345
        mock_process.terminate = MagicMock()
        mock_process.kill = MagicMock()
        mock_process.wait = MagicMock()
        manager._servers["test"].process = mock_process
        manager._servers["test"].status = MCPServerStatus.RUNNING

        result = await manager.stop_server("test")
        assert result is True
        assert manager._servers["test"].status == MCPServerStatus.STOPPED
        assert manager._servers["test"].process is None

    @pytest.mark.asyncio
    async def test_stop_server_timeout_kills(self):
        """超时时强制 kill"""
        manager = MCPServerManager()
        config = MCPServerConfig(name="test", command="echo")
        manager.register_server(config)

        mock_process = MagicMock(spec=subprocess.Popen)
        mock_process.terminate = MagicMock()
        mock_process.kill = MagicMock()
        mock_process.wait = MagicMock(side_effect=subprocess.TimeoutExpired(cmd="echo", timeout=10))
        manager._servers["test"].process = mock_process
        manager._servers["test"].status = MCPServerStatus.RUNNING

        result = await manager.stop_server("test")
        assert result is True
        mock_process.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_restart_server(self):
        manager = MCPServerManager()
        config = MCPServerConfig(name="test", command="echo")
        manager.register_server(config)

        mock_process = MagicMock(spec=subprocess.Popen)
        mock_process.pid = 12345
        mock_process.terminate = MagicMock()
        mock_process.wait = MagicMock()
        mock_process.stdout = MagicMock()
        mock_process.stderr = MagicMock()

        with patch("subprocess.Popen", return_value=mock_process):
            result = await manager.restart_server("test")

        assert result is True


class TestMCPServerManagerStatus:
    """测试服务器状态查询"""

    def test_get_server_status_none(self):
        manager = MCPServerManager()
        assert manager.get_server_status("nonexistent") is None

    def test_get_server_status_stopped(self):
        manager = MCPServerManager()
        config = MCPServerConfig(name="test", command="echo", tools=["tool1"])
        manager.register_server(config)
        status = manager.get_server_status("test")
        assert status["name"] == "test"
        assert status["status"] == "stopped"
        assert status["tools"] == ["tool1"]
        assert status["pid"] is None

    def test_list_servers_empty(self):
        manager = MCPServerManager()
        assert manager.list_servers() == []

    def test_list_servers(self):
        manager = MCPServerManager()
        config1 = MCPServerConfig(name="srv1", command="echo")
        config2 = MCPServerConfig(name="srv2", command="echo")
        manager.register_server(config1)
        manager.register_server(config2)
        servers = manager.list_servers()
        assert len(servers) == 2

    def test_get_available_tools_empty(self):
        manager = MCPServerManager()
        assert manager.get_available_tools() == {}

    def test_get_available_tools_only_running(self):
        manager = MCPServerManager()
        config1 = MCPServerConfig(name="running", command="echo", tools=["t1"])
        config2 = MCPServerConfig(name="stopped", command="echo", tools=["t2"])
        manager.register_server(config1)
        manager.register_server(config2)
        manager._servers["running"].status = MCPServerStatus.RUNNING
        tools = manager.get_available_tools()
        assert "running" in tools
        assert "stopped" not in tools


class TestMCPServerManagerBatchOps:
    """测试批量操作"""

    @pytest.mark.asyncio
    async def test_start_all(self):
        manager = MCPServerManager()
        config1 = MCPServerConfig(name="srv1", command="echo")
        config2 = MCPServerConfig(name="srv2", command="echo")
        manager.register_server(config1)
        manager.register_server(config2)

        mock_process = MagicMock(spec=subprocess.Popen)
        mock_process.pid = 1
        mock_process.stdout = MagicMock()
        mock_process.stderr = MagicMock()

        with patch("subprocess.Popen", return_value=mock_process):
            results = await manager.start_all()

        assert len(results) == 2
        assert all(results.values())

    @pytest.mark.asyncio
    async def test_stop_all(self):
        manager = MCPServerManager()
        config = MCPServerConfig(name="srv1", command="echo")
        manager.register_server(config)
        manager._servers["srv1"].status = MCPServerStatus.RUNNING

        results = await manager.stop_all()
        assert len(results) == 1
        assert results["srv1"] is True

    @pytest.mark.asyncio
    async def test_cleanup(self):
        manager = MCPServerManager()
        config = MCPServerConfig(name="srv1", command="echo")
        manager.register_server(config)
        await manager.cleanup()
        assert manager._servers["srv1"].status == MCPServerStatus.STOPPED


# ===========================================================================
# mcp/restart_policy.py 测试
# ===========================================================================


class TestRestartPolicyInit:
    """测试 RestartPolicy 初始化"""

    def test_init_defaults(self):
        policy = RestartPolicy()
        assert policy.strategy == RestartStrategy.EXPONENTIAL_BACKOFF
        assert policy.max_attempts == 5
        assert policy.base_delay == 1.0
        assert policy.max_delay == 60.0

    def test_init_custom(self):
        policy = RestartPolicy(
            strategy=RestartStrategy.IMMEDIATE,
            max_attempts=10,
            base_delay=2.0,
        )
        assert policy.strategy == RestartStrategy.IMMEDIATE
        assert policy.max_attempts == 10
        assert policy.base_delay == 2.0


class TestRestartPolicyShouldRestart:
    """测试是否应该重启的判断"""

    def test_should_restart_fresh(self):
        policy = RestartPolicy()
        should, delay = policy.should_restart("srv1")
        assert should is True
        assert delay == pytest.approx(1.0)  # exponential backoff: 1 * 2^0 = 1

    def test_should_not_restart_max_attempts(self):
        policy = RestartPolicy(max_attempts=2)
        policy._attempt_counts["srv1"] = 2
        should, delay = policy.should_restart("srv1")
        assert should is False

    def test_should_not_restart_circuit_open(self):
        policy = RestartPolicy()
        policy._circuit_open["srv1"] = True
        policy._circuit_opened_at["srv1"] = datetime.now()
        should, delay = policy.should_restart("srv1")
        assert should is False

    def test_should_restart_circuit_expired(self):
        """熔断器超时后自动关闭"""
        policy = RestartPolicy(circuit_breaker_reset_time=0)
        policy._circuit_open["srv1"] = True
        policy._circuit_opened_at["srv1"] = datetime.now()
        should, delay = policy.should_restart("srv1")
        assert should is True


class TestRestartPolicyDelayCalculation:
    """测试延迟计算"""

    def test_delay_immediate(self):
        policy = RestartPolicy(strategy=RestartStrategy.IMMEDIATE)
        assert policy._calculate_delay(0) == 0.0
        assert policy._calculate_delay(5) == 0.0

    def test_delay_delayed(self):
        policy = RestartPolicy(strategy=RestartStrategy.DELAYED, base_delay=5.0)
        assert policy._calculate_delay(0) == 5.0
        assert policy._calculate_delay(3) == 5.0

    def test_delay_exponential_backoff(self):
        policy = RestartPolicy(
            strategy=RestartStrategy.EXPONENTIAL_BACKOFF,
            base_delay=1.0,
            max_delay=60.0,
        )
        assert policy._calculate_delay(0) == pytest.approx(1.0)
        assert policy._calculate_delay(1) == pytest.approx(2.0)
        assert policy._calculate_delay(2) == pytest.approx(4.0)
        assert policy._calculate_delay(10) == 60.0  # max delay cap

    def test_delay_circuit_breaker(self):
        policy = RestartPolicy(strategy=RestartStrategy.CIRCUIT_BREAKER, base_delay=3.0)
        assert policy._calculate_delay(0) == 3.0


class TestRestartPolicyExecuteRestart:
    """测试执行重启"""

    @pytest.mark.asyncio
    async def test_execute_restart_success(self):
        policy = RestartPolicy(strategy=RestartStrategy.IMMEDIATE)
        restart_func = AsyncMock(return_value=True)
        result = await policy.execute_restart("srv1", restart_func)
        assert result is True
        assert policy._attempt_counts["srv1"] == 0  # 成功后重置

    @pytest.mark.asyncio
    async def test_execute_restart_failure(self):
        policy = RestartPolicy(strategy=RestartStrategy.IMMEDIATE)
        restart_func = AsyncMock(return_value=False)
        result = await policy.execute_restart("srv1", restart_func)
        assert result is False
        assert policy._attempt_counts["srv1"] == 1

    @pytest.mark.asyncio
    async def test_execute_restart_exception(self):
        policy = RestartPolicy(strategy=RestartStrategy.IMMEDIATE)
        restart_func = AsyncMock(side_effect=RuntimeError("crash"))
        result = await policy.execute_restart("srv1", restart_func)
        assert result is False

    @pytest.mark.asyncio
    async def test_execute_restart_should_not(self):
        """不应重启时直接返回 False"""
        policy = RestartPolicy(max_attempts=0)
        restart_func = AsyncMock()
        result = await policy.execute_restart("srv1", restart_func)
        assert result is False
        restart_func.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_restart_opens_circuit(self):
        """连续失败达到阈值时打开熔断器"""
        policy = RestartPolicy(
            strategy=RestartStrategy.IMMEDIATE,
            circuit_breaker_threshold=2,
        )
        restart_func = AsyncMock(return_value=False)

        await policy.execute_restart("srv1", restart_func)
        await policy.execute_restart("srv1", restart_func)
        assert policy._is_circuit_open("srv1") is True

    @pytest.mark.asyncio
    async def test_execute_restart_records(self):
        """重启记录被保存"""
        policy = RestartPolicy(strategy=RestartStrategy.IMMEDIATE)
        restart_func = AsyncMock(return_value=True)
        await policy.execute_restart("srv1", restart_func)
        records = policy.get_records("srv1")
        assert len(records) == 1
        assert records[0]["success"] is True


class TestRestartPolicyReset:
    """测试重置"""

    def test_reset(self):
        policy = RestartPolicy()
        policy._attempt_counts["srv1"] = 5
        policy._circuit_open["srv1"] = True
        policy.reset("srv1")
        assert "srv1" not in policy._attempt_counts
        assert policy._is_circuit_open("srv1") is False


class TestRestartPolicyStats:
    """测试统计信息"""

    def test_get_stats_empty(self):
        policy = RestartPolicy()
        stats = policy.get_stats()
        assert stats["total_restarts"] == 0
        assert stats["successful_restarts"] == 0
        assert stats["servers"] == {}

    def test_get_stats_after_restarts(self):
        policy = RestartPolicy()
        policy._attempt_counts["srv1"] = 3
        policy._records.append(RestartRecord(
            server_name="srv1",
            attempt=1,
            strategy=RestartStrategy.IMMEDIATE,
            delay_seconds=0.0,
            success=True,
            timestamp=datetime.now(timezone.utc),
        ))
        stats = policy.get_stats()
        assert stats["total_restarts"] == 1
        assert stats["successful_restarts"] == 1
        assert "srv1" in stats["servers"]

    def test_get_records_filter_by_server(self):
        policy = RestartPolicy()
        policy._records.append(RestartRecord(
            server_name="srv1", attempt=1,
            strategy=RestartStrategy.IMMEDIATE, delay_seconds=0.0,
            success=True, timestamp=datetime.now(timezone.utc),
        ))
        policy._records.append(RestartRecord(
            server_name="srv2", attempt=1,
            strategy=RestartStrategy.IMMEDIATE, delay_seconds=0.0,
            success=False, timestamp=datetime.now(timezone.utc),
        ))
        assert len(policy.get_records("srv1")) == 1
        assert len(policy.get_records("srv2")) == 1
        assert len(policy.get_records()) == 2


class TestRestartRecord:
    """测试 RestartRecord"""

    def test_to_dict(self):
        record = RestartRecord(
            server_name="srv1",
            attempt=1,
            strategy=RestartStrategy.IMMEDIATE,
            delay_seconds=0.0,
            success=True,
            timestamp=datetime(2025, 1, 1, 12, 0, 0),
        )
        d = record.to_dict()
        assert d["server_name"] == "srv1"
        assert d["strategy"] == "immediate"
        assert d["success"] is True
        assert "timestamp" in d
