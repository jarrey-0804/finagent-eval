# 用户手册

> FinAgent-Eval 金融 AI Agent 评测系统 -- 使用指南

## 1. 安装

### 1.1 pip 安装

```bash
# 基础安装
pip install finagent-eval

# 安装全部可选依赖
pip install "finagent-eval[all]"

# 仅安装特定框架支持
pip install "finagent-eval[langchain]"   # LangGraph 支持
pip install "finagent-eval[openai]"      # OpenAI 支持
pip install "finagent-eval[anthropic]"   # Anthropic 支持
```

要求 Python >= 3.10。

### 1.2 从源码安装

```bash
git clone https://github.com/finagent/finagent-eval.git
cd finagent-eval
pip install -e ".[all]"
```

## 2. 快速开始

### 2.1 初始化配置

```bash
# 生成默认配置文件
finagent-eval config --init

# 查看当前配置
finagent-eval config --show
```

### 2.2 启动 API 服务

```bash
finagent-eval serve --host 0.0.0.0 --port 8000
```

### 2.3 运行评测

```bash
# 快速评测（5 维度）
finagent-eval eval --agent-id my-agent --endpoint http://localhost:8001 --mode quick

# 完整评测（11 维度）
finagent-eval eval --agent-id my-agent --endpoint http://localhost:8001 --mode full -o result.json
```

### 2.4 生成评测任务

```bash
finagent-eval generate --count 20 --mode full -o tasks.json
```

### 2.5 运行对抗性测试

```bash
finagent-eval test --agent-id my-agent --endpoint http://localhost:8001 --level all -o test_result.json
```

## 3. 配置说明

### 3.1 config.yaml 配置文件

配置文件默认路径为 `config/config.yaml`，支持以下模块：

```yaml
database:
  url: "postgresql://localhost:5432/finagent_eval"
  pool_size: 10
  max_overflow: 20

llm:
  openai_api_key: ""       # 或通过环境变量 OPENAI_API_KEY
  anthropic_api_key: ""    # 或通过环境变量 ANTHROPIC_API_KEY
  deepseek_api_key: ""     # 或通过环境变量 DEEPSEEK_API_KEY
  default_model: "gpt-4o"
  temperature: 0.1
  max_tokens: 2048

evaluation:
  default_mode: "full"          # quick 或 full
  max_concurrent_tasks: 5
  task_timeout: 300             # 秒
  pass_threshold: 60.0
  veto_threshold: 30.0

api:
  host: "0.0.0.0"
  port: 8000
  workers: 4
  cors_origins: ["*"]

logging:
  level: "INFO"
  file: null
```

### 3.2 环境变量（.env）

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/finagent_eval
OPENAI_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-ant-xxx
DEEPSEEK_API_KEY=sk-xxx
```

## 4. 评测模式

### 4.1 快速评测（Quick Mode）

- **维度：** 5 个核心维度（准确性、完整性、推理能力、工具使用、合规性）
- **任务数：** 约 20 个
- **预计耗时：** 约 4 小时
- **适用场景：** 日常开发迭代、快速验证

### 4.2 完整评测（Full Mode）

- **维度：** 11 个维度（5 能力维度 + 6 可信度维度）
- **任务数：** 约 60-100 个
- **预计耗时：** 约 12 小时
- **适用场景：** 正式发布前、全面评估

### 4.3 评级标准

| 评级 | 分数范围 | 说明 |
|------|----------|------|
| S | 95-100 | 卓越 |
| A | 85-94 | 优秀 |
| B | 70-84 | 良好 |
| C | 60-69 | 合格 |
| D | <60 | 不合格 |

**一票否决机制：** 合规性或安全性维度低于 30 分时，直接评为 D 级。

## 三阶段评估流水线

完整评测模式（Full Mode）采用三阶段评估流程：

### 阶段说明

1. **静态评估 (STATIC)**
   - 评估维度：准确性、完整性、推理能力、专业性、工具使用
   - 测试内容：知识问答、规则评分、工具调用准确性
   - 数据来源：BizFinBench、FinMCP-Bench、StockBench

2. **动态评估 (DYNAMIC)**
   - 评估维度：鲁棒性、推理能力（交易绩效）
   - 测试内容：交易模拟、金融数据对抗性测试
   - 对抗层级：基线 → 噪声注入 → 趋势反转 → 技术指标攻击
   - 数据来源：TraderBench、FINTRUST

3. **可信度评估 (TRUST)**
   - 评估维度：合规性、安全性、风险意识、透明度、一致性
   - 测试内容：一票否决检查（7 个条件）、PII 暴露检测、金融数据幻觉检测
   - 数据来源：FINTRUST

### 使用三阶段流水线

通过 API 启动三阶段评测：

```bash
curl -X POST http://localhost:8000/api/v1/evaluation/start \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "my_agent",
    "eval_mode": "full",
    "enable_three_stage": true
  }'
```

### 查看阶段进度

评测状态响应中包含 `current_phase` 字段：

```json
{
  "evaluation_id": "eval_xxx",
  "status": "running",
  "current_phase": "dynamic",
  "phase_results": {
    "static": { "status": "completed", "score": 82.5 },
    "dynamic": { "status": "running" },
    "trust": { "status": "pending" }
  }
}
```

### 断点续跑

评测支持从检查点恢复，即使中途中断也可以继续：

```bash
curl -X POST http://localhost:8000/api/v1/evaluation/eval_xxx/resume \
  -H "Authorization: Bearer YOUR_TOKEN"
```

恢复逻辑会自动跳过已完成的阶段，从下一个阶段继续执行。

## 分布式调度

系统支持 Redis 分布式任务调度，实现水平扩展：

### 配置 Redis

在 `.env` 或环境变量中设置：

```
REDIS_URL=redis://localhost:6379/0
```

### 调度特性

- 优先级队列：URGENT > HIGH > NORMAL > LOW
- 最大并发数：默认 3
- 任务超时：默认 12 小时
- 自动重试：默认 2 次
- 心跳检测：10 秒间隔，30 秒 TTL

### 优雅降级

当 Redis 不可用时，调度器自动回退到内存模式，不影响单实例部署。

## 5. Streamlit UI 使用

### 5.1 启动界面

```bash
streamlit run streamlit_app.py
```

### 5.2 功能页面

- **首页：** 系统概览，展示总评测数、平均分数、通过率等指标
- **新建评测：** 配置 Agent 信息、选择评测模式和维度、提交评测任务
- **评测列表：** 查看历史评测记录及状态
- **结果查看：** 按维度查看评分详情、任务详情和对抗性测试结果
- **系统设置：** 配置 LLM API Key、数据源和系统参数

## 6. Docker 部署

```bash
# 构建并启动全部服务
docker-compose up -d

# 仅启动 API 服务
docker-compose up -d api

# 查看日志
docker-compose logs -f api

# 停止服务
docker-compose down
```

服务端口：API（8000）、PostgreSQL（5432）、Redis（6379）、Prometheus（9090）、Grafana（3000）。

## 7. React 管理端使用指南

### 7.1 功能概览

React 管理端提供现代化的 Web 界面，包含以下功能页面：

| 页面 | 路径 | 功能 |
|------|------|------|
| Dashboard | / | 系统概览、核心指标展示 |
| Agent 管理 | /agents | Agent 注册、配置、生命周期管理 |
| 评测列表 | /evaluations | 历史评测记录、状态跟踪 |
| 评测详情 | /evaluation/:id | 评测结果详情、任务执行记录 |
| Agent 对比 | /compare | 多 Agent 对比评测 |
| 行业基准 | /benchmark | 与行业基准对比 |
| 合规报告 | /compliance | 合规认证报告生成 |
| 改进建议 | /improvement | 智能改进建议 |
| 报告中心 | /reports | 评测报告管理 |
| 系统设置 | /settings | 系统参数配置 |

### 7.2 Dashboard 页面

Dashboard 展示系统核心指标：

- **评测总数** - 历史评测任务数量
- **平均分数** - 所有评测的平均得分
- **通过率** - 评级 ≥ B 的评测占比
- **Agent 数量** - 已注册的 Agent 数量

### 7.3 Agent 管理页面

#### 注册新 Agent

1. 点击「注册 Agent」按钮
2. 填写 Agent 信息：
   - Agent ID（唯一标识）
   - Agent 名称
   - Agent 类型（langgraph/autogen/crewai/http）
   - 端点地址（HTTP 类型必填）
   - 描述
3. 点击「确认注册」

#### 管理 Agent

- **查看详情** - 点击 Agent 名称查看详细信息
- **启动评测** - 点击「评测」按钮启动评测
- **删除 Agent** - 点击「删除」按钮注销 Agent

### 7.4 评测详情页面

评测详情页面展示：

- **基本信息** - Agent 名称、评测模式、状态
- **实时进度** - 通过 WebSocket 实时更新进度条
- **阶段进度** - 三阶段流水线的各阶段状态
- **评分详情** - 各维度的得分和评级
- **任务列表** - 每个评测任务的执行结果
- **对抗性测试结果** - 四级对抗测试的通过情况

### 7.5 Agent 对比页面

用于同时评测多个 Agent 并对比结果：

1. 选择要对比的 Agent（最多 5 个）
2. 选择评测模式和维度
3. 点击「开始对比」
4. 查看对比结果和排名

### 7.6 行业基准页面

将评测结果与行业基准对比：

1. 选择已完成的评测
2. 选择基准类型（行业平均/头部表现）
3. 查看对比结果：
   - 您的评分 vs 行业平均
   - 百分位排名
   - 各维度对比

### 7.7 合规报告页面

生成符合监管要求的合规认证报告：

1. 选择已完成的评测
2. 选择合规框架（中国基金监管/SEC FINRA）
3. 生成报告
4. 查看检查项详情和认证状态

### 7.8 改进建议页面

获取针对性的改进建议：

1. 选择已完成的评测
2. 选择关注维度（可选）
3. 查看改进建议：
   - 问题诊断
   - 改进措施
   - 快速见效建议

### 7.9 深色模式

React 管理端支持深色模式：

- 点击右上角主题切换按钮
- 自动保存主题偏好
- 支持 CSS 变量自定义主题

### 7.10 响应式设计

管理端支持响应式设计：

- **桌面端** - 完整功能展示
- **平板端** - 侧边栏可折叠
- **移动端** - 底部导航栏

---

## 8. 常见问题

### 8.1 评测相关

**Q: 快速评测和完整评测的区别？**

A: 快速评测仅执行 STATIC 阶段，评测 5 个核心维度，约 4 小时；完整评测执行三阶段流水线，评测全部 11 个维度，约 12 小时。

**Q: 如何从断点恢复评测？**

A: 使用 `POST /api/v1/evaluation/{eval_id}/resume` API 或在评测详情页点击「恢复评测」按钮。

**Q: 一票否决机制是什么？**

A: 当合规性或安全性维度得分低于 30 分时，无论总分如何，评测直接评为 D 级。

### 8.2 Agent 接入

**Q: 如何接入自定义 Agent？**

A: 参考 [适配器开发指南](adapter_guide.md)，实现 `FinancialAgentInterface` 接口。

**Q: HTTP 适配器的 API 格式要求？**

A: 参考 [接口规范文档](interface_spec.md) 中的 HTTP API 协议要求。

### 8.3 故障排查

**Q: 评测任务一直 pending？**

A: 检查 Agent 端点是否可达，查看 API 日志确认错误原因。

**Q: MCP 服务连接失败？**

A: 检查 MCP 服务器配置和健康状态，确保网络连通。

**Q: WebSocket 连接断开？**

A: 实现自动重连机制，参考 [WebSocket 使用指南](websocket.md)。

---

## 9. 更多资源

| 资源 | 链接 |
|------|------|
| 快速入门教程 | [tutorial.md](tutorial.md) |
| API 参考文档 | [api_reference.md](api_reference.md) |
| API 使用示例 | [api_examples.md](api_examples.md) |
| 三阶段流水线详解 | [three_stage_pipeline.md](three_stage_pipeline.md) |
| WebSocket 指南 | [websocket.md](websocket.md) |
| 部署指南 | [deployment.md](deployment.md) |
| 适配器开发指南 | [adapter_guide.md](adapter_guide.md) |
