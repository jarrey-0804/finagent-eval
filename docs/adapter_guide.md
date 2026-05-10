# 适配器开发指南

> FinAgent-Eval 适配器开发 -- 接入自定义金融 AI Agent

## 1. 接口实现要求

所有适配器必须继承 `FinancialAgentInterface` 并实现 9 个核心方法：

```python
from finagent.interface.base import FinancialAgentInterface
from finagent.interface.models import AgentConfig, AgentState, EvalTask, EvalResponse

class MyAdapter(FinancialAgentInterface):
    def get_config(self) -> AgentConfig: ...
    async def ainvoke(self, task: EvalTask) -> EvalResponse: ...
    async def abatch(self, tasks: list[EvalTask]) -> list[EvalResponse]: ...
    async def astream(self, task: EvalTask) -> AsyncIterator[dict]: ...
    def get_state(self) -> AgentState: ...
    def reset(self, scope: str = "all") -> None: ...
    def serialize_state(self, state: AgentState) -> bytes: ...
    def deserialize_state(self, data: bytes) -> AgentState: ...
    def get_trace(self, task_id: str) -> Optional[dict]: ...
```

关键注意事项：
- `ainvoke` 超时时应抛出 `TaskTimeoutException`
- 执行错误时应抛出 `AgentExecutionException`
- `abatch` 默认可用 `asyncio.gather` 并行执行
- `reset` 的 `scope` 支持 `"all"` / `"memory"` / `"portfolio"`

## 2. LangGraph 适配器

内置适配器，位于 `finagent.adapter.langgraph`。

```python
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from finagent.adapter.langgraph import LangGraphAdapter

model = ChatOpenAI(model="gpt-4o")
graph = create_react_agent(model=model, tools=[])

adapter = LangGraphAdapter(
    agent_name="我的金融Agent",
    agent_type="financial_analysis",
    graph=graph,
    model_name="gpt-4o",
    tools=[],
)
```

适配器内部通过 `graph.ainvoke()` 执行任务，自动提取消息输出和工具调用记录，支持 Checkpointer 状态持久化。

## 3. AutoGen 适配器

内置适配器，位于 `finagent.adapter.autogen`。

```python
from finagent.adapter.autogen import AutoGenAdapter
from finagent.interface.models import AgentConfig

adapter = AutoGenAdapter(
    agent=your_autogen_agent,
    config=AgentConfig(
        agent_name="autogen-agent",
        agent_type="financial_analysis",
    ),
)
```

适配器通过 `agent.initiate_chat()` 调用 AutoGen Agent，从 `chat_history` 中提取输出和工具调用。流式模式暂不支持原生流式，采用完整执行后分块返回。

## 4. CrewAI 适配器

内置适配器，位于 `finagent.adapter.crewai`。

```python
from finagent.adapter.crewai import CrewAIAdapter
from finagent.interface.models import AgentConfig

adapter = CrewAIAdapter(
    crew=your_crew_instance,
    config=AgentConfig(
        agent_name="crewai-agent",
        agent_type="financial_analysis",
    ),
)
```

适配器通过 `crew.kickoff(inputs={"query": message})` 调用 Crew，从 `tasks_output` 中提取工具调用记录。

## 5. HTTP 适配器（远程 Agent）

内置适配器，位于 `finagent.adapter.http`。适用于无法直接集成的第三方 Agent 或远程服务。

```python
from finagent.adapter.http import HTTPAdapter

adapter = HTTPAdapter(
    agent_name="远程金融Agent",
    agent_type="investment_decision",
    api_endpoint="https://api.example.com/agent",
    api_key="your-api-key",
    llm_backend="proprietary",
)
```

### 5.1 HTTP API 协议要求

Agent 需实现以下端点：

**POST /evaluate** -- 执行评测任务

请求体：
```json
{
    "task_id": "task-001",
    "task_type": "knowledge_qa",
    "dimension": "accuracy",
    "input_data": {"question": "..."},
    "context": {},
    "time_limit_seconds": 300,
    "metadata": {}
}
```

响应体：
```json
{
    "task_id": "task-001",
    "output": "Agent 的回答...",
    "tool_calls": [{"name": "get_stock_price", "args": {"symbol": "AAPL"}, "id": "tc-001"}],
    "intermediate_steps": [],
    "metadata": {"elapsed_time": 1.5}
}
```

**GET /health** -- 健康检查（可选）

## 6. 适配器注册

### 6.1 代码注册

```python
from finagent.adapter.registry import AdapterRegistry

# 注册适配器类
AdapterRegistry.register("my_framework", MyAdapter)

# 注册工厂函数（适用于需要复杂初始化的场景）
AdapterRegistry.register("my_framework", factory=lambda **kwargs: MyAdapter(**kwargs))

# 创建适配器实例
adapter = AdapterRegistry.create_adapter("my_framework", agent_instance=agent, **kwargs)
```

### 6.2 Entry Points 自动注册

在 `pyproject.toml` 中添加：

```toml
[project.entry-points."finagent.adapters"]
my_framework = "my_package.adapter:MyAdapter"
```

系统启动时调用 `AdapterRegistry.load_from_entry_points()` 即可自动加载。

### 6.3 查询已注册适配器

```python
AdapterRegistry.list_frameworks()       # 列出所有框架
AdapterRegistry.is_registered("autogen") # 检查是否已注册
AdapterRegistry.get_adapter_class("langgraph")  # 获取适配器类
```
