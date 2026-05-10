"""
状态隔离管理模块

基于 LangGraph Checkpointer 实现评测任务间的状态隔离，
确保并发评测时各任务状态互不干扰。
"""

from .manager import IsolationConfig, StateIsolationManager
from .production import ProductionCheckpointer

__all__ = [
    "StateIsolationManager",
    "IsolationConfig",
    "ProductionCheckpointer",
]
