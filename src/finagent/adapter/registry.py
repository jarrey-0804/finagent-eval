"""
适配器注册表

对应需求: FR-002-05
支持运行时注册新框架适配器。
"""

from collections.abc import Callable
from typing import Any

from ..interface import FinancialAgentInterface
from .autogen import AutoGenAdapter
from .crewai import CrewAIAdapter
from .http import HTTPAdapter
from .langgraph import LangGraphAdapter


class AdapterRegistry:
    """
    框架适配器注册表。

    支持运行时注册新框架适配器，使评测系统能够接入各种框架开发的 Agent。

    对应需求: FR-002-05

    使用示例:
    ```python
    # 获取注册表实例
    registry = AdapterRegistry()

    # 注册自定义适配器
    registry.register("my_framework", MyAdapter)

    # 根据 Agent 配置创建适配器
    adapter = registry.create_adapter(agent_config, agent_instance)

    # 通过 entry points 自动加载适配器
    registry.load_from_entry_points()
    ```
    """

    # 内置适配器
    _adapters: dict[str, type[FinancialAgentInterface]] = {
        "langgraph": LangGraphAdapter,
        "http": HTTPAdapter,
        "autogen": AutoGenAdapter,
        "crewai": CrewAIAdapter,
    }

    # 适配器工厂函数
    _factories: dict[str, Callable] = {}

    @classmethod
    def register(
        cls,
        framework: str,
        adapter_class: type[FinancialAgentInterface] = None,
        factory: Callable = None,
    ) -> None:
        """
        注册框架适配器。

        Args:
            framework: 框架名称（如 "langgraph", "autogen", "crewai"）。
            adapter_class: 适配器类。
            factory: 适配器工厂函数（可选，用于复杂创建逻辑）。

        Raises:
            ValueError: 如果 framework 为空或 adapter_class 无效。
        """
        if not framework:
            raise ValueError("Framework name cannot be empty")

        framework = framework.lower()

        if factory is not None:
            cls._factories[framework] = factory
        elif adapter_class is not None:
            if not issubclass(adapter_class, FinancialAgentInterface):
                raise ValueError(
                    "Adapter class must be a subclass of FinancialAgentInterface"
                )
            cls._adapters[framework] = adapter_class
        else:
            raise ValueError("Either adapter_class or factory must be provided")

    @classmethod
    def unregister(cls, framework: str) -> bool:
        """
        注销框架适配器。

        Args:
            framework: 框架名称。

        Returns:
            bool: 是否成功注销。
        """
        framework = framework.lower()
        removed = False

        if framework in cls._adapters:
            del cls._adapters[framework]
            removed = True

        if framework in cls._factories:
            del cls._factories[framework]
            removed = True

        return removed

    @classmethod
    def get_adapter_class(cls, framework: str) -> type[FinancialAgentInterface] | None:
        """
        获取适配器类。

        Args:
            framework: 框架名称。

        Returns:
            Optional[Type[FinancialAgentInterface]]: 适配器类，如果不存在则返回 None。
        """
        return cls._adapters.get(framework.lower())

    @classmethod
    def get_factory(cls, framework: str) -> Callable | None:
        """
        获取适配器工厂函数。

        Args:
            framework: 框架名称。

        Returns:
            Optional[Callable]: 工厂函数，如果不存在则返回 None。
        """
        return cls._factories.get(framework.lower())

    @classmethod
    def list_frameworks(cls) -> list[str]:
        """
        列出所有已注册的框架。

        Returns:
            list[str]: 框架名称列表。
        """
        return list(set(cls._adapters.keys()) | set(cls._factories.keys()))

    @classmethod
    def is_registered(cls, framework: str) -> bool:
        """
        检查框架是否已注册。

        Args:
            framework: 框架名称。

        Returns:
            bool: 是否已注册。
        """
        framework = framework.lower()
        return framework in cls._adapters or framework in cls._factories

    @classmethod
    def create_adapter(
        cls,
        framework: str,
        agent_instance: Any = None,
        **kwargs,
    ) -> FinancialAgentInterface:
        """
        创建适配器实例。

        Args:
            framework: 框架名称。
            agent_instance: Agent 实例（可选）。
            **kwargs: 传递给适配器构造函数的参数。

        Returns:
            FinancialAgentInterface: 适配器实例。

        Raises:
            ValueError: 如果框架未注册。
        """
        framework = framework.lower()

        # 优先使用工厂函数
        if framework in cls._factories:
            factory = cls._factories[framework]
            return factory(agent_instance=agent_instance, **kwargs)

        # 使用适配器类
        if framework in cls._adapters:
            adapter_class = cls._adapters[framework]
            return adapter_class(**kwargs)

        raise ValueError(
            f"Framework '{framework}' is not registered. "
            f"Available frameworks: {cls.list_frameworks()}"
        )

    @classmethod
    def load_from_entry_points(cls, group: str = "finagent.adapters") -> int:
        """
        从 Python entry points 加载适配器插件。

        Args:
            group: Entry point 组名。

        Returns:
            int: 加载的适配器数量。
        """
        loaded_count = 0

        try:
            import importlib.metadata

            entry_points = importlib.metadata.entry_points(group=group)

            for ep in entry_points:
                try:
                    adapter_class = ep.load()
                    cls.register(ep.name, adapter_class=adapter_class)
                    loaded_count += 1
                except Exception as e:
                    # 记录错误但不中断加载
                    print(f"Warning: Failed to load adapter '{ep.name}': {e}")

        except Exception as e:
            print(f"Warning: Failed to load entry points: {e}")

        return loaded_count

    @classmethod
    def clear(cls) -> None:
        """清空所有注册的适配器（仅用于测试）。"""
        cls._adapters.clear()
        cls._factories.clear()

        # 重新注册内置适配器
        cls._adapters["langgraph"] = LangGraphAdapter
        cls._adapters["http"] = HTTPAdapter
        cls._adapters["autogen"] = AutoGenAdapter
        cls._adapters["crewai"] = CrewAIAdapter


# 全局注册表实例
registry = AdapterRegistry()
