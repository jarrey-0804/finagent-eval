"""
框架适配器模块

对应需求: FR-002 框架适配器

支持多种 Agent 框架接入评测系统：
- LangGraphAdapter: 支持 LangGraph 框架
- HTTPAdapter: 支持通过 HTTP API 接入任意 Agent
- AutoGenAdapter: 支持 AutoGen 框架
- CrewAIAdapter: 支持 CrewAI 框架
- AdapterRegistry: 运行时注册新框架适配器
"""

from .autogen import AutoGenAdapter
from .crewai import CrewAIAdapter
from .http import HTTPAdapter
from .langgraph import LangGraphAdapter
from .registry import AdapterRegistry, registry

__all__ = [
    "LangGraphAdapter",
    "HTTPAdapter",
    "AutoGenAdapter",
    "CrewAIAdapter",
    "AdapterRegistry",
    "registry",
]
