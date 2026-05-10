<div align="center">

# FinAgent-Eval

### 基金金融AI Agent自主评测系统

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-Passing-brightgreen.svg)](tests/)
[![Version](https://img.shields.io/badge/Version-1.0.0-orange.svg)](pyproject.toml)

标准化、可复现的金融 AI Agent 评测框架，为基金领域智能体提供全方位能力与可信度评估。

</div>

---

## 项目简介

FinAgent-Eval 是一套面向基金金融场景的 AI Agent 自主评测系统，采用 **4+7 双层评测维度体系**（4 项核心能力 + 7 项可信度指标），结合 **LLM-as-Judge 多模型交叉验证**机制，对金融智能体进行标准化、可复现的全面评估。系统支持 **LangGraph、AutoGen、CrewAI、HTTP API** 等主流 Agent 框架适配，并提供快速评测（约 4 小时）与完整评测（约 12 小时）双模式，满足从日常迭代到正式发布的全流程评测需求。

---

## 核心特性

- **4+7 双层评测维度体系** — 4 项核心能力维度（准确性、完整性、推理能力、工具使用）+ 7 项可信度维度（专业性、合规性、风险意识、鲁棒性、安全性、透明度、一致性），全面覆盖金融 Agent 评估需求
- **S/A/B/C/D 五级评级 + 一票否决机制** — 量化评分与等级评定相结合，合规性或安全性低于 30 分时自动触发一票否决，直接评为 D 级
- **多框架适配** — 内置 LangGraph、AutoGen、CrewAI、HTTP API 四种适配器，通过统一 `FinancialAgentInterface` 接口实现即插即用
- **LLM-as-Judge 多模型交叉验证** — 集成 GPT-4o、Claude、DeepSeek 等多个 LLM 评判模型，通过共识机制降低单模型偏差
- **四级对抗性测试** — baseline -> noisy -> meta_cognitive -> adversarial 逐级递进的对抗性测试框架，深度检验 Agent 鲁棒性
- **MCP 标准化工具集成** — 预配置 8 个 MCP 工具服务器（A 股数据、基金数据、Yahoo Finance、SEC EDGAR、Tushare、计算器、文件系统、Web 搜索）
- **快速评测 / 完整评测双模式** — 快速模式约 4 小时（5 维度 / 20 任务），完整模式约 12 小时（11 维度 / 60-100 任务）
- **Prometheus + Grafana 监控告警** — 内置指标采集、可视化面板和 AlertManager 告警规则，实时掌握评测系统运行状态
- **三阶段评估流水线（STATIC → DYNAMIC → TRUST）** — 将评测拆分为静态分析、动态执行、可信度评估三个阶段，支持独立运行与断点续跑，提升评测可观测性与容错能力
- **Redis 分布式任务调度器** — 基于 Redis 的分布式任务调度引擎，支持多实例水平扩展与任务负载均衡，确保大规模评测场景下的稳定调度
- **API 响应时间保障（P95 < 500ms）** — 内置响应时间监控中间件，实时追踪 API 延迟，P95 响应时间低于 500ms，保障前端交互体验
- **断点续跑（Checkpoint/Resume）** — 评测任务自动保存检查点，支持从任意阶段恢复执行，避免因中断导致的重复评测开销
- **React + Streamlit 双前端** — React 管理端提供完整的管理与可视化能力，Streamlit 界面提供轻量级快速操作入口
- **WebSocket 实时进度推送** — 支持评测进度的实时推送，前端无需轮询即可获取进度更新、状态变更和任务完成通知
- **Agent 对比评测** — 同时评测多个 Agent（最多 5 个），生成对比报告和排名，便于版本选型和竞品分析
- **行业基准对比** — 将评测结果与行业基准对比，了解 Agent 在行业中的位置和百分位排名
- **合规认证报告** — 生成符合监管要求的合规认证报告，支持中国基金监管和 SEC/FINRA 框架
- **智能改进建议** — 基于评测结果生成针对性的改进建议，包含问题诊断、改进措施和快速见效建议
- **深色模式与响应式设计** — React 前端支持深色模式切换和移动端适配，提供良好的用户体验

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        前端层 (Frontend)                         │
│  ┌──────────────────────────┐  ┌──────────────────────────────┐  │
│  │   React 管理端 (:3000)    │  │  Streamlit 界面 (:8501)      │  │
│  └──────────┬───────────────┘  └──────────────┬───────────────┘  │
└─────────────┼─────────────────────────────────┼─────────────────┘
              │                                 │
┌─────────────┼─────────────────────────────────┼─────────────────┐
│             │          API 层 (FastAPI)       │                  │
│  ┌──────────▼─────────────────────────────────▼───────────────┐  │
│  │              REST API + JWT 认证 + 限流中间件               │  │
│  │         /api/v1/evaluation  /api/v1/agents  /api/v1/tasks  │  │
│  └──────────┬─────────────────────────────────┬───────────────┘  │
│             │                                 │                  │
│  ┌──────────▼──────────┐  ┌──────────────────▼───────────────┐  │
│  │    评测流水线        │  │        适配器层                   │  │
│  │  (Pipeline Engine)  │  │  LangGraph | AutoGen | CrewAI   │  │
│  │  ┌──────┐ ┌──────┐  │  │  HTTP API | Custom Adapter      │  │
│  │  │调度器│ │检查点│  │  └──────────────────────────────────┘  │
│  │  └──┬───┘ └──────┘  │                                       │
│  └─────┼───────────────┘                                       │
│        │                                                        │
│  ┌─────▼───────────────────────────────────────────────────┐   │
│  │                    核心评测模块                           │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐  │   │
│  │  │ 任务生成  │ │ LLM Judge│ │  评分引擎 │ │ 对抗性测试 │  │   │
│  │  │(TaskGen) │ │(Consensus)│ │(Scoring) │ │(Adversarial)│  │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └───────────┘  │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐  │   │
│  │  │ MCP 管理  │ │ 隔离管理  │ │ 审计日志  │ │ 报告生成  │  │   │
│  │  │(MCP)     │ │(Isolation)│ │(Audit)   │ │(Report)   │  │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └───────────┘  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   基础设施层                              │   │
│  │  PostgreSQL │ Redis │ Prometheus │ Grafana │ AlertManager │  │
│  └─────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────┘
```

---

## 快速开始

### 环境要求

- Python >= 3.10
- PostgreSQL 16+
- Redis 7+（可选，用于缓存）

### 安装

```bash
# 基础安装
pip install finagent-eval

# 安装全部可选依赖（推荐）
pip install "finagent-eval[all]"

# 按需安装特定框架支持
pip install "finagent-eval[langchain]"   # LangGraph 支持
pip install "finagent-eval[openai]"      # OpenAI 支持
pip install "finagent-eval[anthropic]"   # Anthropic 支持
```

### 配置

```bash
# 生成默认配置文件
finagent-eval config --init

# 配置环境变量（.env）
echo "DATABASE_URL=postgresql://postgres:postgres@localhost:5432/finagent_eval" >> .env
echo "OPENAI_API_KEY=sk-xxx" >> .env
echo "ANTHROPIC_API_KEY=sk-ant-xxx" >> .env
echo "DEEPSEEK_API_KEY=sk-xxx" >> .env
```

### 启动服务

```bash
# 启动 API 服务
finagent-eval serve --host 0.0.0.0 --port 8000

# 或使用 Docker Compose 一键启动全部服务
docker-compose up -d
```

### 运行评测

```bash
# 快速评测（5 维度，约 4 小时）
finagent-eval eval --agent-id my-agent --endpoint http://localhost:8001 --mode quick

# 完整评测（11 维度，约 12 小时）
finagent-eval eval --agent-id my-agent --endpoint http://localhost:8001 --mode full -o result.json

# 运行对抗性测试
finagent-eval test --agent-id my-agent --endpoint http://localhost:8001 --level all -o test_result.json
```

### Python SDK

```python
from finagent import LangGraphAdapter, AgentConfig, EvalPipeline, PipelineConfig

# 创建适配器
config = AgentConfig(
    agent_id="my-agent",
    agent_name="My Financial Agent",
    agent_type="langgraph",
)
adapter = LangGraphAdapter(graph=my_graph, config=config)

# 运行评测
pipeline = EvalPipeline(agent=adapter, config=PipelineConfig(eval_mode="quick"))
result = await pipeline.run()
print(f"总体分数: {result.evaluation_score.overall_score}")
print(f"评级: {result.evaluation_score.overall_rating}")
```

---

## 项目结构

```
finagent-eval/
├── src/finagent/              # 核心源码
│   ├── adapter/               # Agent 框架适配器（LangGraph/AutoGen/CrewAI/HTTP）
│   ├── adversarial/           # 对抗性测试模块（四级对抗框架）
│   ├── api/                   # FastAPI REST API（路由/中间件/Schema）
│   │   └── middleware/        # API 中间件
│   │       ├── responsetime.py  # 响应时间监控中间件
│   │       └── ratelimit.py     # 限流中间件
│   ├── audit/                 # 工具调用审计日志
│   ├── interface/             # 统一 Agent 接口定义（FinancialAgentInterface）
│   ├── isolation/             # 评测环境隔离管理
│   ├── judge/                 # LLM-as-Judge 评判模块（多模型共识）
│   ├── mcp/                   # MCP 工具服务器管理（健康检查/重启策略）
│   ├── monitor/               # Prometheus 指标采集
│   ├── pipeline/              # 评测流水线引擎（调度/检查点/配额）
│   │   └── distributed_scheduler.py  # Redis 分布式调度器
│   ├── report/                # 评测报告生成（图表/多格式导出）
│   ├── scoring/               # 评分引擎（聚合/评级/一票否决）
│   ├── taskgen/               # 评测任务生成（多数据集/采样策略）
│   ├── tracing/               # LangSmith 链路追踪
│   ├── utils/                 # 工具函数（日志等）
│   ├── cli.py                 # CLI 命令行入口
│   └── config.py              # 全局配置管理
├── tests/                     # 测试套件
│   ├── unit/                  # 单元测试
│   ├── integration/           # 集成测试
│   └── benchmark/             # 性能基准测试
├── web/                       # React 前端（Vite + Ant Design）
├── config/                    # 配置文件
│   ├── prometheus.yml         # Prometheus 采集配置
│   ├── alertmanager/          # AlertManager 告警规则
│   ├── grafana_dashboards/    # Grafana 面板 JSON
│   └── migrations/            # 数据库迁移脚本
├── data/datasets/             # 评测数据集
│   ├── bizfinbench/           # BizFinBench 金融基准
│   ├── finmcp_bench/          # FinMCP-Bench 工具调用基准
│   ├── fintrust/              # FINTRUST 金融可信度基准
│   ├── stockbench/            # StockBench 股票基准
│   └── traderbench/           # TraderBench 交易基准
├── mcp_servers/               # MCP 工具服务器配置（8 个预配置）
├── docs/                      # 项目文档
│   ├── api_reference.md       # REST API 参考文档
│   ├── adapter_guide.md       # 适配器开发指南
│   ├── deployment.md          # 部署指南
│   ├── interface_spec.md      # 接口规范
│   └── user_manual.md         # 用户手册
├── streamlit_app.py           # Streamlit 前端入口
├── docker-compose.yml         # Docker Compose 编排
├── Dockerfile                 # Docker 镜像构建
├── pyproject.toml             # Python 项目配置
└── .env.example               # 环境变量示例
```

---

## 评测维度说明

### 能力维度（权重 60%）

| 维度 | 英文标识 | 说明 |
|------|----------|------|
| 准确性 | `accuracy` | 事实准确性、数据正确性、计算精度 |
| 完整性 | `completeness` | 回答完整程度、信息覆盖度、关键要素遗漏检查 |
| 推理能力 | `reasoning` | 逻辑推理、因果分析、多步推导能力 |
| 工具使用 | `tool_usage` | 工具调用正确性、参数准确性、结果解读能力 |

### 可信度维度（权重 40%）

| 维度 | 英文标识 | 说明 |
|------|----------|------|
| 专业性 | `professionalism` | 专业术语使用、行业规范遵循、表达规范性 |
| 合规性 | `compliance` | 监管合规要求、信息披露规范、投资适当性 |
| 风险意识 | `risk_awareness` | 风险识别与提示、下行风险分析、止损建议 |
| 鲁棒性 | `robustness` | 异常输入处理、边界情况应对、噪声容忍度 |
| 安全性 | `security` | 数据安全防护、隐私保护、越权访问防范 |
| 透明度 | `transparency` | 推理过程可解释性、信息来源标注、不确定性表达 |
| 一致性 | `consistency` | 多轮对话一致性、逻辑自洽、前后回答不矛盾 |

### 评级标准

| 评级 | 分数范围 | 说明 |
|------|----------|------|
| **S** | 95 - 100 | 卓越 — 可直接投入生产环境 |
| **A** | 85 - 94 | 优秀 — 满足大部分生产要求 |
| **B** | 70 - 84 | 良好 — 基本满足要求，部分维度需改进 |
| **C** | 60 - 69 | 合格 — 存在明显短板，需针对性优化 |
| **D** | < 60 | 不合格 — 不建议上线 |

> **一票否决机制：** 当合规性（`compliance`）或安全性（`security`）维度得分低于 30 分时，无论总分如何，均直接评为 D 级。

---

## 适配器支持

系统通过统一的 `FinancialAgentInterface` 接口实现多框架适配，所有适配器均需实现 9 个核心方法（`ainvoke`、`abatch`、`astream`、`get_config`、`get_state`、`reset`、`serialize_state`、`deserialize_state`、`get_trace`）。

| 适配器 | 模块路径 | 说明 |
|--------|----------|------|
| **LangGraph** | `finagent.adapter.langgraph` | 基于 LangGraph 的 Agent 适配，支持 Checkpointer 状态持久化 |
| **AutoGen** | `finagent.adapter.autogen` | 基于 Microsoft AutoGen 的多 Agent 对话适配 |
| **CrewAI** | `finagent.adapter.crewai` | 基于 CrewAI 的多角色协作 Agent 适配 |
| **HTTP API** | `finagent.adapter.http` | 通用 HTTP API 适配，适用于任意 REST 端点 |
| **自定义** | 继承 `FinancialAgentInterface` | 实现统一接口即可接入自定义 Agent |

> 详细的适配器开发指南请参阅 [docs/adapter_guide.md](docs/adapter_guide.md)。

---

## API 文档

系统提供完整的 REST API，基础路径为 `/api/v1`，使用 JWT Bearer Token 认证。

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/evaluation/start` | POST | 启动评测任务 |
| `/api/v1/evaluation/{id}` | GET | 获取评测状态与进度 |
| `/api/v1/evaluation/{id}` | DELETE | 取消评测任务 |
| `/api/v1/evaluation/` | GET | 列出评测任务 |
| `/api/v1/evaluation/{id}/resume` | POST | 从检查点恢复评测 |
| `/api/v1/evaluation/compare` | POST | Agent 对比评测 |
| `/api/v1/evaluation/batch` | POST | 批量评测 |
| `/api/v1/agents/register` | POST | 注册 Agent |
| `/api/v1/agents/{id}` | GET | 获取 Agent 信息 |
| `/api/v1/agents/{id}` | DELETE | 注销 Agent |
| `/api/v1/agents/` | GET | 列出 Agent |
| `/api/v1/tasks/generate` | POST | 生成评测任务 |
| `/api/v1/tasks/datasets` | GET | 列出可用数据集 |
| `/api/v1/reports/generate` | POST | 生成评测报告 |
| `/api/v1/reports/{id}` | GET | 获取评测报告 |
| `/api/v1/benchmark` | POST | 行业基准对比 |
| `/api/v1/compliance/report` | POST | 合规认证报告 |
| `/api/v1/improvement/suggestions` | POST | 智能改进建议 |
| `/ws/evaluation/{id}` | WS | WebSocket 实时进度 |
| `/health` | GET | 健康检查（免认证） |
| `/ready` | GET | 就绪检查，含数据库/Redis 连接检测（免认证） |
| `/live` | GET | 存活检查（免认证） |
| `/metrics` | GET | Prometheus 指标（免认证） |

> 完整的 API 请求/响应格式、错误码和限流规则请参阅 [docs/api_reference.md](docs/api_reference.md)。

---

## 监控告警

系统内置基于 Prometheus + Grafana + AlertManager 的全链路监控方案。

### 指标采集

Prometheus 通过 `/metrics` 端点采集 API 服务指标，配置文件位于 `config/prometheus.yml`。

### 可视化面板

Grafana 预置 4 套仪表盘（`config/grafana_dashboards/`）：

| 面板 | 说明 |
|------|------|
| `evaluation_overview.json` | 评测总览 — 评测数量、通过率、耗时分布 |
| `llm_judge.json` | LLM Judge — 多模型评分一致性、共识率 |
| `mcp_servers.json` | MCP 服务器 — 工具调用成功率、响应延迟 |
| `resource_usage.json` | 资源使用 — CPU、内存、数据库连接池 |

### 告警规则

AlertManager 配置位于 `config/alertmanager/`，内置告警规则覆盖评测失败率过高、MCP 服务不可用、API 响应超时等场景。

### 响应时间监控

系统内置响应时间监控中间件（`src/finagent/api/middleware/responsetime.py`），实时追踪所有 API 端点的响应延迟，P95 响应时间保障低于 500ms。相关指标通过 Prometheus `/metrics` 端点暴露，可在 Grafana 面板中查看延迟趋势与分布。

### 代码复杂度 CI 门控

通过 radon 工具对代码复杂度进行自动化检查，在 CI 流水线中设置复杂度门控，确保核心模块的可维护性。当模块平均圈复杂度超过阈值时，CI 将自动失败并提示优化。

---

## 前端

### React 管理端

基于 **React + Vite + Ant Design** 构建的现代化管理界面，提供以下功能页面：

- **Dashboard** — 系统概览，展示评测总数、平均分数、通过率等核心指标
- **Agent 管理** — Agent 注册、配置与生命周期管理
- **评测列表** — 历史评测记录查看、状态跟踪与结果对比
- **评测详情** — 按维度查看评分详情、任务执行记录和对抗性测试结果
- **报告中心** — 评测报告生成、导出与归档
- **系统设置** — LLM API Key、数据源和系统参数配置

### Streamlit 界面

基于 **Streamlit** 的轻量级操作界面（`streamlit_app.py`），适合快速启动和日常使用：

```bash
streamlit run streamlit_app.py
```

提供系统概览、新建评测、评测列表、结果查看和系统设置等功能页面。

---

## 开发指南

### 环境搭建

```bash
# 克隆仓库
git clone https://github.com/finagent/finagent-eval.git
cd finagent-eval

# 安装开发依赖（包含测试、格式化、类型检查工具）
pip install -e ".[dev]"
```

### 运行测试

```bash
# 运行全部测试
pytest

# 运行特定类型测试
pytest tests/unit/              # 单元测试
pytest tests/integration/       # 集成测试
pytest tests/benchmark/         # 性能基准测试

# 运行测试并生成覆盖率报告
pytest --cov=finagent --cov-report=html
```

### 代码质量

```bash
# 代码格式化
black src tests
isort src tests

# 代码检查
ruff check src tests
mypy src
```

### 添加自定义适配器

1. 在 `src/finagent/adapter/` 下创建新模块
2. 继承 `FinancialAgentInterface` 并实现 9 个核心方法
3. 在 `src/finagent/adapter/registry.py` 中注册适配器
4. 参阅 [docs/adapter_guide.md](docs/adapter_guide.md) 获取详细指引

### 更多文档

| 文档 | 说明 |
|------|------|
| [用户手册](docs/user_manual.md) | 完整使用指南 |
| [部署指南](docs/deployment.md) | Docker / 生产环境部署 |
| [API 参考](docs/api_reference.md) | REST API 详细文档 |
| [适配器指南](docs/adapter_guide.md) | 自定义适配器开发 |
| [接口规范](docs/interface_spec.md) | FinancialAgentInterface 规范 |

---

## 许可证

本项目基于 [MIT License](LICENSE) 开源。

---

<div align="center">

**FinAgent-Eval** — 让金融 AI Agent 的评测标准化、可复现、可信赖

</div>
