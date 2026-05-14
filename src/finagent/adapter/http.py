"""
HTTP 适配器

对应需求: FR-002-02
支持通过 HTTP API 接入任意 Agent。
"""

import asyncio
import time
from collections.abc import AsyncIterator

import aiohttp

from ..interface import (
    AgentConfig,
    AgentExecutionException,
    AgentState,
    EvalResponse,
    EvalTask,
    FinancialAgentInterface,
    TaskTimeoutException,
)


class HTTPAdapter(FinancialAgentInterface):
    """
    HTTP 适配器。

    支持通过 HTTP API 接入任意框架开发的 Agent。
    适用于无法直接集成的第三方 Agent 或远程 Agent 服务。

    对应需求: FR-002-02

    使用示例:
    ```python
    adapter = HTTPAdapter(
        agent_name="远程金融Agent",
        agent_type="investment_decision",
        api_endpoint="https://api.example.com/agent",
        api_key="your-api-key",
        llm_backend="proprietary",
    )

    eval_system = SOPEvaluationSystem(agent=adapter, mode=EvalMode.QUICK)
    report = await eval_system.run_full_evaluation()
    ```

    HTTP API 协议要求:

    POST /evaluate
    Request:
    ```json
    {
        "task_id": "task-001",
        "task_type": "knowledge_qa",
        "dimension": "金融知识与推理",
        "input_data": {"question": "..."},
        "context": {},
        "time_limit_seconds": 300
    }
    ```

    Response:
    ```json
    {
        "task_id": "task-001",
        "output": "Agent 的回答...",
        "tool_calls": [
            {"name": "get_stock_price", "args": {"symbol": "AAPL"}, "id": "tc-001"}
        ],
        "intermediate_steps": [],
        "metadata": {"elapsed_time": 1.5}
    }
    ```
    """

    def __init__(
        self,
        agent_name: str,
        agent_type: str,
        api_endpoint: str,
        api_key: str = None,
        llm_backend: str = "unknown",
        version: str = "1.0.0",
        description: str = "",
        timeout_seconds: int = 300,
        headers: dict = None,
    ):
        """
        初始化 HTTP 适配器。

        Args:
            agent_name: Agent 名称。
            agent_type: Agent 类型。
            api_endpoint: Agent API 端点 URL。
            api_key: API 密钥（可选）。
            llm_backend: 底层 LLM 名称。
            version: Agent 版本号。
            description: Agent 功能描述。
            timeout_seconds: 默认超时时间（秒）。
            headers: 自定义请求头。
        """
        self._agent_name = agent_name
        self._agent_type = agent_type
        self._api_endpoint = api_endpoint.rstrip("/")
        self._api_key = api_key
        self._llm_backend = llm_backend
        self._version = version
        self._description = description
        self._timeout_seconds = timeout_seconds
        self._custom_headers = headers or {}

        # 当前状态
        self._current_state = AgentState()

        # 存储执行追踪
        self._traces: dict[str, dict] = {}

    def get_config(self) -> AgentConfig:
        """返回 Agent 配置信息。"""
        return AgentConfig(
            agent_name=self._agent_name,
            agent_type=self._agent_type,
            version=self._version,
            framework="http",
            llm_backend=self._llm_backend,
            description=self._description,
        )

    async def ainvoke(self, task: EvalTask) -> EvalResponse:
        """
        异步执行评测任务。

        通过 HTTP API 调用远程 Agent。

        Args:
            task: 评测任务。

        Returns:
            EvalResponse: 评测响应。

        Raises:
            TaskTimeoutException: 任务执行超时。
            AgentExecutionException: Agent 执行出错。
        """
        start_time = time.time()
        timeout = task.time_limit_seconds or self._timeout_seconds

        # 构建请求
        headers = self._build_headers()
        request_body = self._build_request_body(task)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self._api_endpoint}/evaluate",
                    headers=headers,
                    json=request_body,
                    timeout=aiohttp.ClientTimeout(total=timeout),
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        elapsed_time = time.time() - start_time

                        # 记录追踪
                        self._traces[task.task_id] = {
                            "elapsed_time": elapsed_time,
                            "request": request_body,
                            "response": data,
                            "timestamp": start_time,
                        }

                        return EvalResponse(
                            task_id=task.task_id,
                            output=data.get("output", ""),
                            tool_calls=data.get("tool_calls", []),
                            intermediate_steps=data.get("intermediate_steps", []),
                            metadata={
                                "elapsed_time": elapsed_time,
                                "status_code": response.status,
                                **data.get("metadata", {}),
                            },
                        )
                    else:
                        error_text = await response.text()
                        raise AgentExecutionException(
                            message=f"HTTP {response.status}: {error_text}",
                            error_code="HTTP_ERROR",
                            recoverable=response.status >= 500,
                            task_id=task.task_id,
                        )

        except TimeoutError as err:
            raise TaskTimeoutException(task.task_id, timeout) from err

        except aiohttp.ClientError as e:
            raise AgentExecutionException(
                message=f"HTTP client error: {str(e)}",
                error_code="HTTP_CLIENT_ERROR",
                recoverable=True,
                task_id=task.task_id,
            ) from e

    async def abatch(self, tasks: list[EvalTask]) -> list[EvalResponse]:
        """批量异步执行评测任务。"""
        return await asyncio.gather(*[self.ainvoke(task) for task in tasks])

    async def astream(self, task: EvalTask) -> AsyncIterator[dict]:
        """
        流式执行评测任务。

        如果 Agent API 支持 SSE（Server-Sent Events），则返回流式响应。
        """
        # 简单实现：先执行完整请求，然后分块返回
        try:
            response = await self.ainvoke(task)
            yield {
                "event": "start",
                "data": {"task_id": task.task_id},
                "timestamp": time.time(),
            }
            yield {
                "event": "output",
                "data": {"output": response.output},
                "timestamp": time.time(),
            }
            yield {
                "event": "end",
                "data": {"task_id": task.task_id, "metadata": response.metadata},
                "timestamp": time.time(),
            }
        except Exception as e:
            yield {
                "event": "error",
                "data": {"error": str(e)},
                "timestamp": time.time(),
            }

    def get_state(self) -> AgentState:
        """获取 Agent 当前状态。"""
        return self._current_state

    def reset(self, scope: str = "all") -> None:
        """重置 Agent 状态。"""
        if scope == "all":
            self._current_state = AgentState()
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

    def _build_headers(self) -> dict:
        """构建请求头。"""
        headers = {
            "Content-Type": "application/json",
            **self._custom_headers,
        }
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _build_request_body(self, task: EvalTask) -> dict:
        """构建请求体。"""
        return {
            "task_id": task.task_id,
            "task_type": task.task_type,
            "dimension": task.dimension,
            "input_data": task.input_data,
            "context": task.context,
            "time_limit_seconds": task.time_limit_seconds,
            "metadata": task.metadata,
        }

    async def health_check(self) -> dict:
        """
        健康检查。

        调用 Agent 的健康检查端点。
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self._api_endpoint}/health",
                    headers=self._build_headers(),
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status == 200:
                        return {
                            "status": "healthy",
                            "agent_name": self._agent_name,
                            "endpoint": self._api_endpoint,
                        }
                    else:
                        return {
                            "status": "unhealthy",
                            "status_code": response.status,
                        }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
            }
