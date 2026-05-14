"""
CrewAI 适配器

将 CrewAI 框架的 Agent 适配为 FinancialAgentInterface。
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from ..interface.base import FinancialAgentInterface
from ..interface.models import (
    AgentConfig,
    AgentState,
    EvalResponse,
    EvalTask,
)

logger = logging.getLogger(__name__)


class CrewAIAdapter(FinancialAgentInterface):
    """
    CrewAI 框架适配器

    将 CrewAI 的 Crew 适配为标准接口。
    """

    def __init__(
        self,
        crew,
        config: AgentConfig | None = None,
    ):
        self._crew = crew
        self._config = config or AgentConfig(
            agent_name="crewai-agent",
            agent_type="crewai",
            version="0.1.0",
            framework="crewai",
            llm_backend="unknown",
        )
        # 存储执行追踪
        self._traces: dict[str, dict] = {}

    def get_config(self) -> AgentConfig:
        return self._config

    async def ainvoke(self, task: EvalTask) -> EvalResponse:
        """调用 CrewAI Crew"""
        try:
            # 从 task.input_data 中提取输入消息
            message = self._build_input_content(task)

            result = self._crew.kickoff(inputs={"query": message})

            if isinstance(result, dict):
                output = result.get("result", str(result))
            elif isinstance(result, str):
                output = result
            else:
                output = str(result)

            return EvalResponse(
                task_id=task.task_id,
                output=output,
                tool_calls=self._extract_tool_calls(result),
            )
        except Exception as e:
            return EvalResponse(
                task_id=task.task_id,
                output="",
                error=f"CrewAI执行失败: {str(e)}",
            )

    async def abatch(self, tasks: list[EvalTask]) -> list[EvalResponse]:
        """批量调用"""
        return await asyncio.gather(*[self.ainvoke(task) for task in tasks])

    async def astream(self, task: EvalTask) -> AsyncIterator[dict]:
        """流式调用"""
        response = await self.ainvoke(task)
        yield {
            "event": "message",
            "data": {"content": response.output or ""},
            "task_id": task.task_id,
        }

    def get_state(self) -> AgentState:
        return AgentState(
            status="idle",
            metadata={"framework": "crewai"},
        )

    def reset(self, scope: str = "all") -> None:
        """重置Agent状态"""
        logger.info("CrewAIAdapter: 重置适配器状态 (scope=%s)", scope)
        self._traces.clear()
        if hasattr(self._crew, "reset_memory"):
            self._crew.reset_memory()
        if hasattr(self._crew, "agent"):
            crew_agent = (
                self._crew.agent if isinstance(self._crew.agent, list) else [self._crew.agent]
            )
            for agent in crew_agent:
                if hasattr(agent, "reset_memory"):
                    agent.reset_memory()

    def serialize_state(self, state: AgentState) -> bytes:
        """序列化状态"""
        import json

        return json.dumps(state.model_dump()).encode("utf-8")

    def deserialize_state(self, data: bytes) -> AgentState:
        """反序列化状态"""
        import json

        return AgentState(**json.loads(data.decode("utf-8")))

    def get_trace(self, task_id: str) -> dict | None:
        """获取指定任务的执行追踪"""
        return self._traces.get(task_id)

    def _build_input_content(self, task: EvalTask) -> str:
        """从 EvalTask 构建输入内容"""
        if "question" in task.input_data:
            return task.input_data["question"]
        elif "instruction" in task.input_data:
            return task.input_data["instruction"]
        else:
            return str(task.input_data)

    def _extract_tool_calls(self, result: Any) -> list[dict]:
        """从CrewAI结果中提取工具调用"""
        tool_calls = []
        if isinstance(result, dict):
            for agent_result in result.get("tasks_output", []):
                if hasattr(agent_result, "tools_output") and agent_result.tools_output:
                    for tool_out in agent_result.tools_output:
                        tool_calls.append(
                            {
                                "name": getattr(tool_out, "tool_name", ""),
                                "args": getattr(tool_out, "args", {}),
                                "success": True,
                            }
                        )
        return tool_calls
