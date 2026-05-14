"""
LangGraph 适配器

对应需求: FR-002-01
支持 LangGraph 框架的 Agent 接入评测系统。
"""

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Any

from ..interface import (
    AgentConfig,
    AgentExecutionException,
    AgentState,
    EvalResponse,
    EvalTask,
    FinancialAgentInterface,
    TaskTimeoutException,
)


class LangGraphAdapter(FinancialAgentInterface):
    """
    LangGraph 框架适配器。

    将 LangGraph Agent 适配为 FinancialAgentInterface，
    使其可以接入 SOP 评测系统。

    对应需求: FR-002-01

    使用示例:
    ```python
    from langgraph.prebuilt import create_react_agent
    from langchain_openai import ChatOpenAI

    # 创建 LangGraph Agent
    model = ChatOpenAI(model="gpt-4o")
    graph = create_react_agent(model=model, tools=[])

    # 创建适配器
    adapter = LangGraphAdapter(
        agent_name="我的金融Agent",
        agent_type="financial_analysis",
        graph=graph,
        model_name="gpt-4o",
        tools=[],
    )

    # 接入评测系统
    eval_system = SOPEvaluationSystem(agent=adapter, mode=EvalMode.QUICK)
    report = await eval_system.run_full_evaluation()
    ```
    """

    def __init__(
        self,
        agent_name: str,
        agent_type: str,
        graph: Any,
        model_name: str = "gpt-4o",
        tools: list = None,
        checkpointer: Any = None,
        description: str = "",
    ):
        """
        初始化 LangGraph 适配器。

        Args:
            agent_name: Agent 名称。
            agent_type: Agent 类型（investment_decision/quant_research/trade_execution/financial_analysis）。
            graph: LangGraph StateGraph 实例。
            model_name: 使用的 LLM 模型名称。
            tools: 工具列表。
            checkpointer: LangGraph Checkpointer 实例（用于状态持久化）。
            description: Agent 功能描述。
        """
        self._agent_name = agent_name
        self._agent_type = agent_type
        self._graph = graph
        self._model_name = model_name
        self._tools = tools or []
        self._checkpointer = checkpointer
        self._description = description

        # 存储执行追踪
        self._traces: dict[str, dict] = {}

        # 当前状态
        self._current_state = AgentState()

    def get_config(self) -> AgentConfig:
        """返回 Agent 配置信息。"""
        return AgentConfig(
            agent_name=self._agent_name,
            agent_type=self._agent_type,
            version="1.0.0",
            framework="langgraph",
            llm_backend=self._model_name,
            description=self._description,
            supported_tools=[t.name if hasattr(t, "name") else str(t) for t in self._tools],
        )

    async def ainvoke(self, task: EvalTask) -> EvalResponse:
        """
        异步执行评测任务。

        Args:
            task: 评测任务。

        Returns:
            EvalResponse: 评测响应。

        Raises:
            TaskTimeoutException: 任务执行超时。
            AgentExecutionException: Agent 执行出错。
        """
        start_time = time.time()
        thread_id = f"eval_{task.task_id}"
        config = {"configurable": {"thread_id": thread_id}}

        try:
            # 构建输入消息
            input_content = self._build_input_content(task)

            # 执行 Agent（带超时）
            result = await asyncio.wait_for(
                self._graph.ainvoke(
                    {"messages": [{"role": "user", "content": input_content}]},
                    config,
                ),
                timeout=task.time_limit_seconds,
            )

            # 提取输出
            output = self._extract_output(result)

            # 提取工具调用记录
            tool_calls = self._extract_tool_calls(result)

            # 记录追踪
            elapsed_time = time.time() - start_time
            self._traces[task.task_id] = {
                "thread_id": thread_id,
                "elapsed_time": elapsed_time,
                "input": input_content,
                "output": output,
                "tool_calls": tool_calls,
                "timestamp": start_time,
            }

            return EvalResponse(
                task_id=task.task_id,
                output=output,
                tool_calls=tool_calls,
                metadata={
                    "elapsed_time": elapsed_time,
                    "model": self._model_name,
                },
            )

        except TimeoutError as err:
            raise TaskTimeoutException(task.task_id, task.time_limit_seconds) from err

        except Exception as e:
            raise AgentExecutionException(
                message=str(e),
                error_code="LANGGRAPH_ERROR",
                recoverable=False,
                task_id=task.task_id,
            ) from e

    async def abatch(self, tasks: list[EvalTask]) -> list[EvalResponse]:
        """批量异步执行评测任务。"""
        return await asyncio.gather(*[self.ainvoke(task) for task in tasks])

    async def astream(self, task: EvalTask) -> AsyncIterator[dict]:
        """
        流式执行评测任务。

        Yields:
            dict: 中间步骤事件。
        """
        thread_id = f"eval_{task.task_id}"
        config = {"configurable": {"thread_id": thread_id}}
        input_content = self._build_input_content(task)

        try:
            async for event in self._graph.astream_events(
                {"messages": [{"role": "user", "content": input_content}]},
                config,
                version="v2",
            ):
                yield {
                    "event": event.get("event"),
                    "data": event.get("data", {}),
                    "timestamp": time.time(),
                    "task_id": task.task_id,
                }
        except Exception as e:
            yield {
                "event": "error",
                "data": {"error": str(e)},
                "timestamp": time.time(),
                "task_id": task.task_id,
            }

    def get_state(self) -> AgentState:
        """获取 Agent 当前状态。"""
        return self._current_state

    def reset(self, scope: str = "all") -> None:
        """
        重置 Agent 状态。

        Args:
            scope: 重置范围（all/memory/portfolio）。
        """
        if scope == "all":
            self._current_state = AgentState()
            # 重置 Checkpointer
            if self._checkpointer is not None:
                # LangGraph Checkpointer 重置逻辑
                pass
        elif scope == "memory":
            self._current_state.memory = {}
        elif scope == "portfolio":
            self._current_state.portfolio = {}

    def serialize_state(self, state: AgentState) -> bytes:
        """序列化状态。"""
        import json

        return json.dumps(state.model_dump()).encode("utf-8")

    def deserialize_state(self, data: bytes) -> AgentState:
        """反序列化状态。"""
        import json

        return AgentState(**json.loads(data.decode("utf-8")))

    def get_trace(self, task_id: str) -> dict | None:
        """获取指定任务的执行追踪。"""
        return self._traces.get(task_id)

    # ==================== 私有方法 ====================

    def _build_input_content(self, task: EvalTask) -> str:
        """构建输入内容。"""
        if "question" in task.input_data:
            return task.input_data["question"]
        elif "instruction" in task.input_data:
            return task.input_data["instruction"]
        else:
            return str(task.input_data)

    def _extract_output(self, result: dict) -> str:
        """从执行结果中提取输出。"""
        if "messages" in result and result["messages"]:
            last_message = result["messages"][-1]
            if hasattr(last_message, "content"):
                return last_message.content
            elif isinstance(last_message, dict):
                return last_message.get("content", str(last_message))
        return str(result)

    def _extract_tool_calls(self, result: dict) -> list[dict]:
        """从执行结果中提取工具调用记录。"""
        tool_calls = []
        if "messages" in result:
            for msg in result["messages"]:
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        tool_calls.append(
                            {
                                "name": tc.get("name", "unknown"),
                                "args": tc.get("args", {}),
                                "id": tc.get("id", ""),
                            }
                        )
        return tool_calls
