"""
Financial Agent Interface - 核心接口定义

对应需求: FR-001 Agent 接口规范

任何需要接入 SOP 评测系统的金融 AI Agent 都必须实现此接口。
接口设计基于 LangChain Runnable 协议，同时兼容非 LangChain 框架。

核心方法：
- get_config：返回 Agent 配置信息
- ainvoke：异步执行单个评测任务
- abatch：批量异步执行多个评测任务
- astream：流式执行评测任务
- get_state：获取 Agent 当前状态
- reset：重置 Agent 状态
- serialize_state / deserialize_state：状态序列化/反序列化
- get_trace：获取执行追踪
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from .models import AgentConfig, AgentState, EvalResponse, EvalTask


class FinancialAgentInterface(ABC):
    """
    金融 AI Agent 评测接口规范。

    任何需要接入 SOP 评测系统的金融 AI Agent 都必须实现此接口。
    接口设计基于 LangChain Runnable 协议，同时兼容非 LangChain 框架。

    对应需求:
    - FR-001-01: 提供 FinancialAgentInterface 抽象基类
    - FR-001-02: get_config() 方法
    - FR-001-03: ainvoke() 方法
    - FR-001-04: abatch() 方法
    - FR-001-05: astream() 方法
    - FR-001-06: get_state() 方法
    - FR-001-07: reset() 方法
    - FR-001-08: serialize_state() / deserialize_state() 方法
    - FR-001-09: get_trace() 方法
    """

    @abstractmethod
    def get_config(self) -> AgentConfig:
        """
        返回 Agent 的配置信息。

        Returns:
            AgentConfig: Agent 配置信息，包含名称、类型、版本、框架、LLM 后端等。

        对应需求: FR-001-02
        """
        ...

    @abstractmethod
    async def ainvoke(self, task: EvalTask) -> EvalResponse:
        """
        异步执行单个评测任务。

        Args:
            task: 评测任务，包含任务 ID、类型、维度、输入数据等。

        Returns:
            EvalResponse: 评测响应，包含输出、工具调用记录、中间步骤等。

        Raises:
            TaskTimeoutException: 任务执行超时。
            AgentExecutionException: Agent 执行出错。

        对应需求: FR-001-03
        """
        ...

    @abstractmethod
    async def abatch(self, tasks: list[EvalTask]) -> list[EvalResponse]:
        """
        批量异步执行多个评测任务。

        默认实现使用 asyncio.gather 并行执行。
        子类可以覆盖此方法以优化批量执行策略。

        Args:
            tasks: 评测任务列表。

        Returns:
            list[EvalResponse]: 评测响应列表，顺序与输入任务列表一致。

        对应需求: FR-001-04
        """
        ...

    @abstractmethod
    async def astream(self, task: EvalTask) -> AsyncIterator[dict]:
        """
        流式执行评测任务，返回中间步骤。

        用于长任务监控和实时进度展示。

        Args:
            task: 评测任务。

        Yields:
            dict: 中间步骤事件，包含事件类型、数据、时间戳等。

        对应需求: FR-001-05
        """
        ...

    @abstractmethod
    def get_state(self) -> AgentState:
        """
        获取 Agent 当前状态。

        用于状态类评测和评测间状态检查。

        Returns:
            AgentState: Agent 当前状态，包含记忆、上下文、持仓等。

        对应需求: FR-001-06
        """
        ...

    @abstractmethod
    def reset(self, scope: str = "all") -> None:
        """
        重置 Agent 状态。

        确保评测间隔离，防止状态泄漏。

        Args:
            scope: 重置范围。
                - "all": 重置所有状态
                - "memory": 仅重置记忆
                - "portfolio": 仅重置持仓

        对应需求: FR-001-07
        """
        ...

    @abstractmethod
    def serialize_state(self, state: AgentState) -> bytes:
        """
        序列化状态。

        用于状态持久化和跨进程传输。

        Args:
            state: Agent 状态。

        Returns:
            bytes: 序列化后的状态数据。

        对应需求: FR-001-08
        """
        ...

    @abstractmethod
    def deserialize_state(self, data: bytes) -> AgentState:
        """
        反序列化状态。

        用于从持久化存储恢复状态。

        Args:
            data: 序列化的状态数据。

        Returns:
            AgentState: 反序列化后的 Agent 状态。

        对应需求: FR-001-08
        """
        ...

    @abstractmethod
    def get_trace(self, task_id: str) -> dict | None:
        """
        获取指定任务的执行追踪。

        用于透明度评测和调试。

        Args:
            task_id: 任务 ID。

        Returns:
            Optional[dict]: 执行追踪数据，如果任务不存在则返回 None。

        对应需求: FR-001-09
        """
        ...

    # ==================== 可选方法 ====================

    def invoke(self, task: EvalTask) -> EvalResponse:
        """
        同步执行评测任务。

        默认实现使用 asyncio.run 包装 ainvoke。
        注意：在异步上下文中不应使用此方法。

        Args:
            task: 评测任务。

        Returns:
            EvalResponse: 评测响应。
        """
        import asyncio
        return asyncio.run(self.ainvoke(task))

    def batch(self, tasks: list[EvalTask]) -> list[EvalResponse]:
        """
        同步批量执行评测任务。

        默认实现使用 asyncio.run 包装 abatch。
        注意：在异步上下文中不应使用此方法。

        Args:
            tasks: 评测任务列表。

        Returns:
            list[EvalResponse]: 评测响应列表。
        """
        import asyncio
        return asyncio.run(self.abatch(tasks))

    async def health_check(self) -> dict:
        """
        健康检查。

        检查 Agent 是否正常运行。

        Returns:
            dict: 健康状态信息。
        """
        try:
            config = self.get_config()
            return {
                "status": "healthy",
                "agent_name": config.agent_name,
                "agent_type": config.agent_type,
                "framework": config.framework,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
            }
