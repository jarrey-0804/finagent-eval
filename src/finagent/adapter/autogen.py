"""
AutoGen 适配器

将 AutoGen 框架的 Agent 适配为 FinancialAgentInterface。
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


class AutoGenAdapter(FinancialAgentInterface):
    """
    AutoGen 框架适配器

    将 AutoGen 的 AgentGroupChat 或 ConversableAgent 适配为标准接口。
    """

    def __init__(
        self,
        agent,
        config: AgentConfig | None = None,
    ):
        self._agent = agent
        self._config = config or AgentConfig(
            agent_name="autogen-agent",
            agent_type="autogen",
            version="0.1.0",
            framework="autogen",
            llm_backend="unknown",
        )
        # 存储执行追踪
        self._traces: dict[str, dict] = {}

    def get_config(self) -> AgentConfig:
        return self._config

    async def ainvoke(self, task: EvalTask) -> EvalResponse:
        """调用 AutoGen Agent"""
        try:
            # 从 task.input_data 中提取输入消息
            message = self._build_input_content(task)

            # AutoGen 同步调用
            result = self._agent.initiate_chat(
                message=message,
                max_turns=10,
                summary_method="last_msg",
            )

            # 提取最后的回复
            if isinstance(result, dict):
                output = result.get("chat_history", "")[-1].get("content", "") if result.get("chat_history") else str(result)
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
                error=f"AutoGen执行失败: {str(e)}",
            )

    async def abatch(self, tasks: list[EvalTask]) -> list[EvalResponse]:
        """批量调用"""
        return await asyncio.gather(*[self.ainvoke(task) for task in tasks])

    async def astream(self, task: EvalTask) -> AsyncIterator[dict]:
        """流式调用（AutoGen暂不支持原生流式）"""
        response = await self.ainvoke(task)
        yield {
            "event": "message",
            "data": {"content": response.output or ""},
            "task_id": task.task_id,
        }

    def get_state(self) -> AgentState:
        """获取Agent状态"""
        return AgentState(
            status="idle",
            metadata={"framework": "autogen"},
        )

    def reset(self, scope: str = "all") -> None:
        """重置Agent状态"""
        logger.info("AutoGenAdapter: 重置适配器状态 (scope=%s)", scope)
        self._traces.clear()
        if hasattr(self._agent, "clear_history"):
            self._agent.clear_history()
        if hasattr(self._agent, "reset"):
            self._agent.reset()

    def serialize_state(self, state: AgentState) -> bytes:
        """序列化状态"""
        import json
        return json.dumps(state.model_dump()).encode('utf-8')

    def deserialize_state(self, data: bytes) -> AgentState:
        """反序列化状态"""
        import json
        return AgentState(**json.loads(data.decode('utf-8')))

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
        """从AutoGen结果中提取工具调用"""
        tool_calls = []
        if isinstance(result, dict):
            for msg in result.get("chat_history", []):
                if msg.get("tool_calls"):
                    for tc in msg["tool_calls"]:
                        tool_calls.append({
                            "name": tc.get("function", {}).get("name", ""),
                            "args": tc.get("function", {}).get("arguments", {}),
                            "success": True,
                        })
        return tool_calls
