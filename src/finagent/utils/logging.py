"""
finagent-eval 统一日志模块

基于 structlog 的日志配置，支持 JSON（生产）和 Console（开发）两种输出模式。
若 structlog 未安装，自动回退到标准 logging。
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

__all__ = ["get_logger", "configure_logging"]

_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
_LOG_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "WARN": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

_CONFIGURED = False


def _is_production() -> bool:
    """根据 LOG_LEVEL 判断是否为生产环境。DEBUG/开发模式使用 console 输出。"""
    return _LOG_LEVEL not in ("DEBUG",)


def configure_logging() -> None:
    """配置全局日志。重复调用幂等。"""
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True

    try:
        import structlog  # type: ignore[import-untyped]
    except ImportError:
        _configure_stdlib_logging()
        return

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if _is_production():
        # 生产环境: JSON 输出
        renderer = structlog.processors.JSONRenderer(ensure_ascii=False)
    else:
        # 开发环境: 彩色 console 输出
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(_LOG_LEVEL_MAP.get(_LOG_LEVEL, logging.INFO))


def _configure_stdlib_logging() -> None:
    """structlog 不可用时的回退方案，使用标准 logging。"""
    level = _LOG_LEVEL_MAP.get(_LOG_LEVEL, logging.INFO)
    fmt = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt, datefmt="%Y-%m-%dT%H:%M:%S"))

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)


def get_logger(name: str) -> Any:
    """
    获取指定名称的 logger 实例。

    Args:
        name: logger 名称，通常使用模块名 (e.g. __name__)

    Returns:
        structlog BoundLogger 或标准 logging.Logger 实例
    """
    configure_logging()

    try:
        import structlog

        return structlog.get_logger(name)
    except ImportError:
        return logging.getLogger(name)
