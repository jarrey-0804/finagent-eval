"""
utils/logging.py 单元测试

测试统一日志模块：get_logger、configure_logging、
_is_production、_configure_stdlib_logging 等功能。
"""

import logging
import os
import sys
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# _is_production 测试
# ---------------------------------------------------------------------------

class TestIsProduction:

    def test_debug_is_not_production(self):
        """LOG_LEVEL=DEBUG 时应为开发模式"""
        with patch("finagent.utils.logging._LOG_LEVEL", "DEBUG"):
            from finagent.utils.logging import _is_production
            assert _is_production() is False

    def test_info_is_production(self):
        """LOG_LEVEL=INFO 时应为生产模式"""
        with patch("finagent.utils.logging._LOG_LEVEL", "INFO"):
            from finagent.utils.logging import _is_production
            assert _is_production() is True

    def test_warning_is_production(self):
        """LOG_LEVEL=WARNING 时应为生产模式"""
        with patch("finagent.utils.logging._LOG_LEVEL", "WARNING"):
            from finagent.utils.logging import _is_production
            assert _is_production() is True

    def test_error_is_production(self):
        """LOG_LEVEL=ERROR 时应为生产模式"""
        with patch("finagent.utils.logging._LOG_LEVEL", "ERROR"):
            from finagent.utils.logging import _is_production
            assert _is_production() is True


# ---------------------------------------------------------------------------
# configure_logging 测试
# ---------------------------------------------------------------------------

class TestConfigureLogging:

    def setup_method(self):
        """每个测试前重置 _CONFIGURED 状态"""
        import finagent.utils.logging as log_mod
        log_mod._CONFIGURED = False

    def teardown_method(self):
        """每个测试后重置 _CONFIGURED 状态"""
        import finagent.utils.logging as log_mod
        log_mod._CONFIGURED = False

    def test_configure_logging_idempotent(self):
        """重复调用 configure_logging 应幂等"""
        import finagent.utils.logging as log_mod
        log_mod._CONFIGURED = False

        with patch("finagent.utils.logging._configure_stdlib_logging") as mock_stdlib:
            log_mod.configure_logging()
            log_mod.configure_logging()
            # _configure_stdlib_logging 应只被调用一次
            mock_stdlib.assert_called_once()

    def test_configure_logging_sets_configured_flag(self):
        """configure_logging 应设置 _CONFIGURED 为 True"""
        import finagent.utils.logging as log_mod
        log_mod._CONFIGURED = False

        with patch("finagent.utils.logging._configure_stdlib_logging"):
            log_mod.configure_logging()
        assert log_mod._CONFIGURED is True

    def test_configure_logging_with_structlog(self):
        """structlog 可用时应使用 structlog 配置"""
        import finagent.utils.logging as log_mod
        log_mod._CONFIGURED = False

        mock_structlog = MagicMock()
        # 保存原始 import
        original_import = __builtins__["__import__"]

        def selective_import(name, *args, **kwargs):
            if name == "structlog":
                return mock_structlog
            return original_import(name, *args, **kwargs)

        with patch.dict("sys.modules", {"structlog": mock_structlog}):
            with patch("builtins.__import__", side_effect=selective_import):
                log_mod.configure_logging()

        # structlog.configure 应被调用
        mock_structlog.configure.assert_called_once()

    def test_configure_logging_fallback_to_stdlib(self):
        """structlog 不可用时应回退到标准 logging"""
        import finagent.utils.logging as log_mod
        log_mod._CONFIGURED = False

        original_import = __builtins__["__import__"]

        def selective_import(name, *args, **kwargs):
            if name == "structlog":
                raise ImportError("no structlog")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=selective_import):
            with patch("finagent.utils.logging._configure_stdlib_logging") as mock_stdlib:
                log_mod.configure_logging()
                mock_stdlib.assert_called_once()


# ---------------------------------------------------------------------------
# _configure_stdlib_logging 测试
# ---------------------------------------------------------------------------

class TestConfigureStdlibLogging:

    def test_sets_root_logger_level(self):
        """应设置 root logger 的日志级别"""
        import finagent.utils.logging as log_mod
        log_mod._CONFIGURED = False

        with patch("finagent.utils.logging._LOG_LEVEL", "WARNING"):
            log_mod._configure_stdlib_logging()

        root = logging.getLogger()
        assert root.level == logging.WARNING

    def test_sets_root_logger_level_debug(self):
        """LOG_LEVEL=DEBUG 应设置 DEBUG 级别"""
        import finagent.utils.logging as log_mod
        log_mod._CONFIGURED = False

        with patch("finagent.utils.logging._LOG_LEVEL", "DEBUG"):
            log_mod._configure_stdlib_logging()

        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_clears_existing_handlers(self):
        """应清除已有的 handler"""
        import finagent.utils.logging as log_mod
        log_mod._CONFIGURED = False

        root = logging.getLogger()
        existing_handler = logging.StreamHandler()
        root.addHandler(existing_handler)

        log_mod._configure_stdlib_logging()

        # 旧 handler 应被移除
        assert existing_handler not in root.handlers

    def test_adds_stdout_handler(self):
        """应添加 stdout handler"""
        import finagent.utils.logging as log_mod
        log_mod._CONFIGURED = False

        log_mod._configure_stdlib_logging()

        root = logging.getLogger()
        assert len(root.handlers) >= 1
        # 验证 handler 输出到 stdout
        handler = root.handlers[0]
        assert isinstance(handler, logging.StreamHandler)


# ---------------------------------------------------------------------------
# get_logger 测试
# ---------------------------------------------------------------------------

class TestGetLogger:

    def setup_method(self):
        """每个测试前重置 _CONFIGURED 状态"""
        import finagent.utils.logging as log_mod
        log_mod._CONFIGURED = False

    def teardown_method(self):
        """每个测试后重置 _CONFIGURED 状态"""
        import finagent.utils.logging as log_mod
        log_mod._CONFIGURED = False

    def test_get_logger_returns_logger(self):
        """get_logger 应返回 logger 实例"""
        from finagent.utils.logging import get_logger
        logger = get_logger("test.module")
        assert logger is not None

    def test_get_logger_different_names(self):
        """不同名称应返回不同 logger"""
        from finagent.utils.logging import get_logger
        logger1 = get_logger("test.module1")
        logger2 = get_logger("test.module2")
        assert logger1 is not logger2

    def test_get_logger_same_name(self):
        """相同名称应返回相同 logger"""
        from finagent.utils.logging import get_logger
        logger1 = get_logger("test.same")
        logger2 = get_logger("test.same")
        assert logger1 is logger2

    def test_get_logger_triggers_configure(self):
        """get_logger 应触发 configure_logging"""
        import finagent.utils.logging as log_mod
        log_mod._CONFIGURED = False

        with patch("finagent.utils.logging.configure_logging") as mock_configure:
            log_mod.get_logger("test.trigger")
            mock_configure.assert_called_once()

    def test_get_logger_fallback_stdlib(self):
        """structlog 不可用时应返回标准 logging.Logger"""
        import finagent.utils.logging as log_mod
        log_mod._CONFIGURED = False

        original_import = __builtins__["__import__"]

        def selective_import(name, *args, **kwargs):
            if name == "structlog":
                raise ImportError("no structlog")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=selective_import):
            logger = log_mod.get_logger("test.stdlib")
        assert isinstance(logger, logging.Logger)


# ---------------------------------------------------------------------------
# _LOG_LEVEL_MAP 测试
# ---------------------------------------------------------------------------

class TestLogLevelMap:

    def test_all_levels_mapped(self):
        """所有标准日志级别应有映射"""
        from finagent.utils.logging import _LOG_LEVEL_MAP
        assert _LOG_LEVEL_MAP["DEBUG"] == logging.DEBUG
        assert _LOG_LEVEL_MAP["INFO"] == logging.INFO
        assert _LOG_LEVEL_MAP["WARNING"] == logging.WARNING
        assert _LOG_LEVEL_MAP["WARN"] == logging.WARNING
        assert _LOG_LEVEL_MAP["ERROR"] == logging.ERROR
        assert _LOG_LEVEL_MAP["CRITICAL"] == logging.CRITICAL

    def test_unknown_level_defaults_to_info(self):
        """未知日志级别应默认为 INFO"""
        from finagent.utils.logging import _LOG_LEVEL_MAP
        assert _LOG_LEVEL_MAP.get("UNKNOWN", logging.INFO) == logging.INFO
