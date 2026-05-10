# 系统架构设计

> 本文档详细介绍 FinAgent-Eval 的系统架构设计，帮助开发者深入理解系统原理。

---

## 1. 整体架构

### 1.1 分层设计

```
┌─────────────────────────────────────────────────────────────────┐
│                        表现层 (Presentation)                      │
│  ┌──────────────────────────┐  ┌──────────────────────────────┐  │
│  │   React 管理端 (:3000)    │  │  Streamlit 界面 (:8501)      │  │
│  └──────────────────────────┘  └──────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        API 层 (API Gateway)                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              FastAPI REST API + JWT 认证 + 限流中间件      │   │
│  │         /api/v1/evaluation  /api/v1/agents  /api/v1/tasks │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              WebSocket 实时进度推送                        │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        业务层 (Business Logic)                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    评测流水线引擎                          │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐   │   │
│  │  │ 任务生成  │ │ 执行引擎  │ │ 评分引擎  │ │ 报告生成  │   │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └───────────┘   │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    三阶段流水线                            │   │
│  │  STATIC (静态评估) → DYNAMIC (动态评估) → TRUST (可信度)   │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌────────────────┐ ┌────────────────┐ ┌────────────────────┐   │
│  │  LLM-as-Judge  │ │  对抗性测试     │ │   分布式调度器      │   │
│  └────────────────┘ └────────────────┘ └────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        适配器层 (Adapter)                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │ LangGraph│ │  AutoGen │ │  CrewAI  │ │   HTTP   │          │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              FinancialAgentInterface 统一接口              │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        基础设施层 (Infrastructure)               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │PostgreSQL│ │  Redis   │ │Prometheus│ │  Grafana │          │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │ MCP 服务  │ │ 隔离管理  │ │ 审计日志  │ │ 链路追踪  │          │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 模块划分

| 层级 | 模块 | 职责 |
|------|------|------|
| 表现层 | React/Streamlit | 用户界面交互 |
| API 层 | FastAPI | REST API、认证、限流、WebSocket |
| 业务层 | Pipeline | 评测流程编排、任务调度 |
| 业务层 | Scoring | 评分计算、评级判定 |
| 业务层 | Judge | LLM-as-Judge 多模型评判 |
| 适配器层 | Adapter | Agent 框架适配、统一接口 |
| 基础设施层 | Storage | 数据持久化、缓存 |
| 基础设施层 | Monitor | 监控指标、告警 |

---

## 2. 核心模块

### 2.1 评测流水线引擎

```
┌─────────────────────────────────────────────────────────────────┐
│                     评测流水线引擎 (Pipeline Engine)              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │   任务队列   │ →  │   执行引擎   │ →  │   结果收集   │         │
│  │ TaskQueue   │    │ Executor    │    │ Collector   │         │
│  └─────────────┘    └─────────────┘    └─────────────┘         │
│         │                  │                  │                 │
│         │                  ▼                  │                 │
│         │          ┌─────────────┐           │                 │
│         │          │   检查点     │           │                 │
│         │          │ Checkpointer│           │                 │
│         │          └─────────────┘           │                 │
│         │                  │                  │                 │
│         ▼                  ▼                  ▼                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    调度器 (Scheduler)                     │   │
│  │  - 优先级队列: URGENT > HIGH > NORMAL > LOW              │   │
│  │  - 并发控制: max_concurrent_tasks                         │   │
│  │  - 超时管理: task_timeout                                 │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**核心组件：**

- **TaskQueue**: 任务队列管理，支持优先级
- **Executor**: 任务执行器，调用 Agent 适配器
- **Collector**: 结果收集器，聚合评测结果
- **Checkpointer**: 检查点管理，支持断点续跑
- **Scheduler**: 调度器，控制任务执行顺序和并发

### 2.2 LLM-as-Judge 评判模块

```
┌─────────────────────────────────────────────────────────────────┐
│                   LLM-as-Judge 评判模块                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    多模型评判器                            │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐    │   │
│  │  │ GPT-4o  │  │ Claude  │  │DeepSeek │  │  Qwen   │    │   │
│  │  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘    │   │
│  │       │            │            │            │          │   │
│  │       └────────────┴────────────┴────────────┘          │   │
│  │                          │                               │   │
│  │                          ▼                               │   │
│  │              ┌─────────────────────┐                    │   │
│  │              │    共识机制          │                    │   │
│  │              │  - 加权平均          │                    │   │
│  │              │  - Fleiss' Kappa    │                    │   │
│  │              │  - 异常值检测        │                    │   │
│  │              └─────────────────────┘                    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**评判流程：**

1. 将评测任务和 Agent 响应发送给多个 LLM
2. 各 LLM 独立评分（0-100）
3. 收集评分结果
4. 通过共识机制计算最终分数

**共识机制：**

```python
def calculate_consensus(scores: list[float]) -> float:
    """计算多模型共识分数"""
    # 1. 移除异常值（超过 1.5 IQR）
    q1, q3 = np.percentile(scores, [25, 75])
    iqr = q3 - q1
    filtered = [s for s in scores if q1 - 1.5*iqr <= s <= q3 + 1.5*iqr]
    
    # 2. 加权平均（可根据模型能力设置权重）
    weights = get_model_weights()
    weighted_sum = sum(s * w for s, w in zip(filtered, weights))
    total_weight = sum(weights)
    
    return weighted_sum / total_weight
```

### 2.3 评分引擎

```
┌─────────────────────────────────────────────────────────────────┐
│                       评分引擎 (Scoring Engine)                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    维度评分器                             │   │
│  │  accuracy │ completeness │ reasoning │ tool_usage │ ... │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    分数聚合器                             │   │
│  │  加权平均 = Σ(维度分数 × 维度权重)                        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    一票否决检查                           │   │
│  │  if compliance < 30 or security < 30:                    │   │
│  │      rating = "D"  # 直接不合格                           │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    评级判定器                             │   │
│  │  S: 95-100 │ A: 85-94 │ B: 70-84 │ C: 60-69 │ D: <60    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2.4 任务调度器

```
┌─────────────────────────────────────────────────────────────────┐
│                    分布式任务调度器                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Redis 任务队列                         │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐       │   │
│  │  │ URGENT  │ │  HIGH   │ │ NORMAL  │ │   LOW   │       │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘       │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Worker 实例池                          │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐                    │   │
│  │  │Worker 1 │ │Worker 2 │ │Worker 3 │  ...               │   │
│  │  └─────────┘ └─────────┘ └─────────┘                    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    心跳与故障转移                          │   │
│  │  - 心跳间隔: 10s                                         │   │
│  │  - TTL: 30s                                              │   │
│  │  - 自动任务接管                                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. 适配器层

### 3.1 接口设计

```python
class FinancialAgentInterface(ABC):
    """金融 Agent 统一接口"""
    
    @abstractmethod
    def get_config(self) -> AgentConfig:
        """获取 Agent 配置"""
        pass
    
    @abstractmethod
    async def ainvoke(self, task: EvalTask) -> EvalResponse:
        """异步执行单个任务"""
        pass
    
    @abstractmethod
    async def abatch(self, tasks: list[EvalTask]) -> list[EvalResponse]:
        """批量异步执行"""
        pass
    
    @abstractmethod
    async def astream(self, task: EvalTask) -> AsyncIterator[dict]:
        """流式执行"""
        pass
    
    @abstractmethod
    def get_state(self) -> AgentState:
        """获取当前状态"""
        pass
    
    @abstractmethod
    def reset(self, scope: str = "all") -> None:
        """重置状态"""
        pass
    
    @abstractmethod
    def serialize_state(self, state: AgentState) -> bytes:
        """序列化状态"""
        pass
    
    @abstractmethod
    def deserialize_state(self, data: bytes) -> AgentState:
        """反序列化状态"""
        pass
    
    @abstractmethod
    def get_trace(self, task_id: str) -> Optional[dict]:
        """获取执行追踪"""
        pass
```

### 3.2 框架适配

| 适配器 | 实现方式 | 特点 |
|--------|----------|------|
| LangGraphAdapter | `graph.ainvoke()` | 支持 Checkpointer |
| AutoGenAdapter | `agent.initiate_chat()` | 多 Agent 对话 |
| CrewAIAdapter | `crew.kickoff()` | 多角色协作 |
| HTTPAdapter | `httpx.post()` | 通用 REST API |

### 3.3 扩展机制

```python
# 注册自定义适配器
from finagent.adapter.registry import AdapterRegistry

AdapterRegistry.register("my_framework", MyAdapter)

# 通过 Entry Points 自动加载
# pyproject.toml
[project.entry-points."finagent.adapters"]
my_framework = "my_package.adapter:MyAdapter"
```

---

## 4. 数据模型

### 4.1 核心实体

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│     Agent       │     │   Evaluation    │     │     Task        │
├─────────────────┤     ├─────────────────┤     ├─────────────────┤
│ agent_id        │────<│ evaluation_id   │────<│ task_id         │
│ agent_name      │     │ agent_id        │     │ evaluation_id   │
│ agent_type      │     │ eval_mode       │     │ task_type       │
│ status          │     │ status          │     │ dimension       │
│ config          │     │ overall_score   │     │ input_data      │
│ registered_at   │     │ overall_rating  │     │ output          │
│ last_evaluated  │     │ started_at      │     │ score           │
└─────────────────┘     │ completed_at    │     │ status          │
                        └─────────────────┘     └─────────────────┘
                                │
                                │
                                ▼
                        ┌─────────────────┐
                        │     Report      │
                        ├─────────────────┤
                        │ report_id       │
                        │ evaluation_id   │
                        │ format          │
                        │ content         │
                        │ generated_at    │
                        └─────────────────┘
```

### 4.2 状态管理

```
PipelineState:
  - evaluation_id: str
  - current_phase: STATIC | DYNAMIC | TRUST
  - phase_results: dict[Phase, PhaseResult]
  - tasks: list[EvalTask]
  - responses: list[EvalResponse]
  - scores: list[TaskScore]
  - started_at: datetime
  - completed_at: datetime
  - error: Optional[str]
```

---

## 5. 基础设施

### 5.1 数据库设计

**PostgreSQL 表结构：**

```sql
-- Agent 表
CREATE TABLE agents (
    agent_id VARCHAR(64) PRIMARY KEY,
    agent_name VARCHAR(256) NOT NULL,
    agent_type VARCHAR(32) NOT NULL,
    status VARCHAR(16) DEFAULT 'active',
    config JSONB,
    registered_at TIMESTAMP DEFAULT NOW(),
    last_evaluated TIMESTAMP
);

-- Evaluation 表
CREATE TABLE evaluations (
    evaluation_id UUID PRIMARY KEY,
    agent_id VARCHAR(64) REFERENCES agents(agent_id),
    eval_mode VARCHAR(16),
    status VARCHAR(16),
    overall_score FLOAT,
    overall_rating CHAR(1),
    phase_results JSONB,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error TEXT
);

-- Task 表
CREATE TABLE tasks (
    task_id UUID PRIMARY KEY,
    evaluation_id UUID REFERENCES evaluations(evaluation_id),
    task_type VARCHAR(32),
    dimension VARCHAR(32),
    input_data JSONB,
    output TEXT,
    score FLOAT,
    status VARCHAR(16),
    executed_at TIMESTAMP
);
```

### 5.2 缓存策略

**Redis 使用场景：**

| 场景 | Key 格式 | TTL | 说明 |
|------|----------|-----|------|
| 任务队列 | `task:queue:{priority}` | - | 分布式任务队列 |
| 任务锁 | `task:lock:{task_id}` | 300s | 防止重复执行 |
| 心跳 | `worker:heartbeat:{worker_id}` | 30s | Worker 存活检测 |
| 缓存 | `cache:agent:{agent_id}` | 3600s | Agent 配置缓存 |

### 5.3 监控告警

**Prometheus 指标：**

```yaml
# 评测相关
finagent_evaluations_total: 总评测数
finagent_evaluations_active: 活跃评测数
finagent_evaluation_duration_seconds: 评测耗时
finagent_evaluation_score: 评测得分

# API 相关
finagent_api_requests_total: API 请求总数
finagent_api_response_time_seconds: API 响应时间
finagent_api_errors_total: API 错误数

# 系统相关
finagent_workers_active: 活跃 Worker 数
finagent_tasks_pending: 待处理任务数
finagent_tasks_completed: 已完成任务数
```

---

## 6. 扩展性设计

### 6.1 自定义维度

```python
# 添加自定义评测维度
from finagent.scoring import DimensionRegistry

@DimensionRegistry.register("custom_dimension")
class CustomDimension:
    name = "自定义维度"
    weight = 0.05
    description = "自定义评测维度"
    
    def evaluate(self, response: EvalResponse) -> float:
        # 实现评分逻辑
        return score
```

### 6.2 自定义数据集

```python
# 添加自定义数据集
from finagent.taskgen import DatasetRegistry

@DatasetRegistry.register("custom_dataset")
class CustomDataset:
    name = "自定义数据集"
    task_types = ["knowledge_qa", "analysis"]
    
    def load(self) -> list[EvalTask]:
        # 加载任务数据
        return tasks
```

### 6.3 插件机制

```python
# 插件接口
class PluginInterface(ABC):
    @abstractmethod
    def on_evaluation_start(self, evaluation: Evaluation) -> None:
        pass
    
    @abstractmethod
    def on_task_complete(self, task: Task, result: EvalResponse) -> None:
        pass
    
    @abstractmethod
    def on_evaluation_complete(self, evaluation: Evaluation) -> None:
        pass

# 注册插件
PluginRegistry.register("my_plugin", MyPlugin())
```
