# 接口规范文档

> FinAgent-Eval 金融 AI Agent 评测系统 -- 接口定义与数据模型

## 1. FinancialAgentInterface 协议

`FinancialAgentInterface` 是所有接入评测系统的金融 AI Agent 必须实现的抽象基类（ABC），定义于 `finagent.interface.base` 模块。

### 1.1 核心方法（必须实现）

| 方法 | 签名 | 说明 |
|------|------|------|
| `get_config` | `() -> AgentConfig` | 返回 Agent 配置信息 |
| `ainvoke` | `(task: EvalTask) -> EvalResponse` | 异步执行单个评测任务 |
| `abatch` | `(tasks: list[EvalTask]) -> list[EvalResponse]` | 批量异步执行评测任务 |
| `astream` | `(task: EvalTask) -> AsyncIterator[dict]` | 流式执行，返回中间步骤事件 |
| `get_state` | `() -> AgentState` | 获取 Agent 当前状态 |
| `reset` | `(scope: str = "all") -> None` | 重置状态（all/memory/portfolio） |
| `serialize_state` | `(state: AgentState) -> bytes` | 状态序列化 |
| `deserialize_state` | `(data: bytes) -> AgentState` | 状态反序列化 |
| `get_trace` | `(task_id: str) -> Optional[dict]` | 获取任务执行追踪 |

### 1.2 可选方法（已提供默认实现）

| 方法 | 说明 |
|------|------|
| `invoke(task)` | 同步执行，默认包装 `ainvoke` |
| `batch(tasks)` | 同步批量执行，默认包装 `abatch` |
| `health_check()` | 健康检查，返回状态字典 |

## 2. 数据模型

### 2.1 AgentConfig -- Agent 配置

```python
class AgentConfig(BaseModel):
    agent_name: str           # Agent 名称
    agent_type: AgentType     # Agent 类型枚举
    version: str              # 版本号
    framework: str            # 开发框架（langgraph/autogen/crewai/custom）
    llm_backend: str          # 底层 LLM（gpt-4o/claude-sonnet/deepseek/qwen 等）
    description: str = ""     # 功能描述
    supported_tools: list[str] = []  # 支持的工具列表
    mcp_servers: list[str] = []      # MCP 服务器列表
```

### 2.2 EvalTask -- 评测任务

```python
class EvalTask(BaseModel):
    task_id: str              # 任务唯一标识
    task_type: TaskType       # 任务类型枚举
    dimension: str            # 评测维度（对应 11 个维度之一）
    input_data: dict          # 输入数据（问题、市场数据等）
    context: dict = {}        # 上下文信息
    time_limit_seconds: int = 300  # 超时时间
    metadata: dict = {}       # 元数据（难度、数据集来源等）
```

### 2.3 EvalResponse -- 评测响应

```python
class EvalResponse(BaseModel):
    task_id: str                          # 对应任务 ID
    output: str                           # Agent 文本输出
    tool_calls: list[dict] = []           # 工具调用记录
    intermediate_steps: list[dict] = []   # 中间推理步骤
    metadata: dict = {}                   # 元数据（Token、耗时等）
```

### 2.4 AgentState -- Agent 状态

```python
class AgentState(BaseModel):
    memory: dict = {}       # 对话历史/记忆
    context: dict = {}      # 当前上下文
    portfolio: dict = {}    # 持仓状态
    metadata: dict = {}     # 元数据
    version: str = "1.0"    # 状态格式版本
```

## 3. 枚举定义

### 3.1 EvalDimension -- 4+7 双层评测体系

**能力维度（60%权重）：**

| 维度 | 枚举值 | 权重 | 说明 |
|------|--------|------|------|
| 准确性 | `accuracy` | 0.15 | 事实准确性和数据正确性 |
| 完整性 | `completeness` | 0.10 | 覆盖问题所有方面 |
| 推理能力 | `reasoning` | 0.15 | 逻辑推理和分析能力 |
| 工具使用 | `tool_usage` | 0.10 | 工具调用正确性和效率 |
| 专业性 | `professionalism` | 0.10 | 专业程度和术语使用 |

**可信度维度（40%权重）：**

| 维度 | 枚举值 | 权重 | 说明 |
|------|--------|------|------|
| 合规性 | `compliance` | 0.10 | 金融监管合规性 |
| 风险意识 | `risk_awareness` | 0.08 | 风险识别和提示能力 |
| 鲁棒性 | `robustness` | 0.07 | 异常输入处理能力 |
| 安全性 | `security` | 0.05 | 安全威胁防护能力 |
| 透明度 | `transparency` | 0.05 | 可解释性和透明度 |
| 一致性 | `consistency` | 0.05 | 内部一致性和逻辑自洽性 |

### 3.2 其他枚举

**AgentType：** `investment_decision` | `quant_research` | `trade_execution` | `financial_analysis`

**TaskType：** `knowledge_qa` | `analysis` | `tool_use` | `trading` | `adversarial` | `trustworthiness`

**EvalMode：** `quick`（5 维度快速评测）| `full`（11 维度完整评测）

**EvalStatus：** `pending` | `running` | `completed` | `failed`

**DifficultyLevel：** `easy` | `medium` | `hard` | `expert`

## 三阶段评估流水线类型 (FR-007-02)

### EvalPhase 枚举

| 值 | 说明 |
|---|------|
| STATIC | 静态评估阶段 — 知识问答、规则评分、工具使用准确性 |
| DYNAMIC | 动态评估阶段 — 交易模拟、金融数据对抗性测试 |
| TRUST | 可信度评估阶段 — 合规性、安全性、PII、幻觉检测 |

### 阶段-维度映射 (PHASE_DIMENSIONS)

| 阶段 | 评测维度 |
|------|---------|
| STATIC | accuracy, completeness, reasoning, professionalism, tool_usage |
| DYNAMIC | robustness, reasoning (交易绩效) |
| TRUST | compliance, security, risk_awareness, transparency, consistency |

### 阶段-任务类型映射 (PHASE_TASK_TYPES)

| 阶段 | 任务类型 |
|------|---------|
| STATIC | knowledge_qa, analysis, tool_use, single_turn, multi_turn |
| DYNAMIC | trading, adversarial |
| TRUST | trustworthiness |

### PhaseResult 数据类

| 字段 | 类型 | 说明 |
|------|------|------|
| phase | EvalPhase | 阶段标识 |
| tasks | list[EvalTask] | 该阶段的评测任务 |
| responses | list[EvalResponse] | 该阶段的 Agent 响应 |
| task_scores | list[TaskScore] | 该阶段的任务评分 |
| evaluation_score | EvaluationScore \| None | 该阶段的聚合评分 |
| started_at | datetime \| None | 开始时间 |
| completed_at | datetime \| None | 完成时间 |

### PipelineState 新增字段

| 字段 | 类型 | 说明 |
|------|------|------|
| current_phase | str | 当前执行阶段 (static/dynamic/trust) |
| phase_results | dict | 各阶段结果 {phase: PhaseResult} |

### PipelineConfig 新增字段

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| enable_three_stage | bool | True | 是否启用三阶段流水线 |

### ThreeStagePipeline 类

三阶段评估流水线，FULL 模式执行 STATIC → DYNAMIC → TRUST，QUICK 模式仅执行 STATIC。

主要方法：
- `run(agent_config, tasks)` — 运行三阶段评测
- `resume(state, checkpointer, evaluation_id)` — 从检查点恢复
- `get_phase_results()` — 获取各阶段结果

### Quick vs Full 模式对比

| 特性 | Quick 模式 | Full 模式 |
|------|-----------|----------|
| 执行阶段 | 仅 STATIC | STATIC → DYNAMIC → TRUST |
| 任务数量 | 50 | 100 |
| 评测维度 | 5 个核心维度 | 全部 11 个维度 |
| 对抗性测试 | 跳过 | 执行 |
| 交易绩效 | 跳过 | 执行 |
| 一票否决 | 跳过 | 执行 |

## 4. 异常体系

所有异常继承自 `EvaluationException`，定义于 `finagent.interface.exceptions`。

```
EvaluationException (基类, error_code: "EVAL_UNKNOWN")
  |-- TaskTimeoutException        # 任务超时 (EVAL_TIMEOUT)
  |-- AgentExecutionException     # Agent 执行错误 (AGENT_ERROR)
  |-- ToolCallException           # 工具调用失败 (TOOL_ERROR)
  |-- EnvironmentException        # 环境错误 (ENV_ERROR)
  |     |-- MCPConnectionException # MCP 连接错误 (MCP_CONNECTION_ERROR)
  |     |-- DatabaseException      # 数据库错误 (DB_ERROR)
  |-- ValidationException         # 数据验证错误 (VALIDATION_ERROR)
  |-- ScoringException            # 评分错误 (SCORING_ERROR)
        |-- LLMJudgeException      # LLM Judge 错误 (LLM_JUDGE_ERROR)
```

每个异常均提供 `to_dict()` 方法，返回结构化错误信息用于 API 响应。

## 5. 适配器注册模式

通过 `AdapterRegistry`（`finagent.adapter.registry`）实现运行时注册：

```python
from finagent.adapter.registry import AdapterRegistry

# 注册适配器类
AdapterRegistry.register("my_framework", MyAdapter)

# 注册工厂函数
AdapterRegistry.register("my_framework", factory=create_adapter)

# 通过 entry points 自动加载
AdapterRegistry.load_from_entry_points("finagent.adapters")
```

内置适配器：`langgraph`（LangGraphAdapter）、`http`（HTTPAdapter）。
