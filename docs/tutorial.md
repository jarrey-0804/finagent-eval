# 快速入门教程

> 本教程将帮助您在 5 分钟内体验 FinAgent-Eval 的核心功能，并在 30 分钟内完成完整的评测流程。

---

## 1. 5 分钟快速体验

### 1.1 Docker 一键启动

最快的方式是使用 Docker Compose 一键启动所有服务：

```bash
# 克隆仓库
git clone https://github.com/finagent/finagent-eval.git
cd finagent-eval

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入您的 API Key：
# OPENAI_API_KEY=sk-xxx
# ANTHROPIC_API_KEY=sk-ant-xxx
# DEEPSEEK_API_KEY=sk-xxx

# 启动所有服务
docker-compose up -d
```

等待约 1-2 分钟，所有服务启动完成后，您可以访问：

| 服务 | 地址 | 说明 |
|------|------|------|
| React 管理端 | http://localhost:3000 | 现代化 Web 界面 |
| API 文档 | http://localhost:8000/docs | Swagger UI |
| Streamlit 界面 | http://localhost:8501 | 轻量级操作界面 |
| Grafana 监控 | http://localhost:3000 (admin/admin) | 可视化面板 |

### 1.2 运行第一个评测

#### 方式一：使用 Web 界面

1. 打开浏览器访问 http://localhost:3000
2. 点击左侧菜单「新建评测」
3. 填写 Agent 信息：
   - Agent ID: `demo-agent`
   - Agent 名称: `演示 Agent`
   - Agent 类型: `HTTP`
   - 端点地址: `http://your-agent:8001/chat`（替换为您的 Agent 地址）
4. 选择评测模式：`快速评测`
5. 点击「开始评测」

#### 方式二：使用命令行

```bash
# 快速评测（约 4 小时）
finagent-eval eval --agent-id demo-agent --endpoint http://localhost:8001 --mode quick

# 或使用 API
curl -X POST "http://localhost:8000/api/v1/evaluation/start" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "demo-agent",
    "eval_mode": "quick"
  }'
```

### 1.3 查看评测结果

评测完成后，可以在以下位置查看结果：

- **Web 界面**：点击「评测列表」→ 选择评测记录 → 查看详情
- **API**：`GET /api/v1/evaluation/{evaluation_id}`
- **报告**：`GET /api/v1/reports/{report_id}`

---

## 2. 30 分钟完整流程

### 2.1 环境准备

#### 方式一：Docker 部署（推荐）

```bash
# 已在上节完成
docker-compose up -d
```

#### 方式二：本地安装

```bash
# 安装 Python 依赖
pip install "finagent-eval[all]"

# 安装 PostgreSQL 和 Redis
# macOS
brew install postgresql redis

# Ubuntu
sudo apt install postgresql redis-server

# 启动服务
brew services start postgresql
brew services start redis

# 创建数据库
createdb finagent_eval

# 初始化配置
finagent-eval config --init
```

### 2.2 Agent 注册

在开始评测前，需要先注册您的 Agent：

#### HTTP Agent（远程服务）

```bash
curl -X POST "http://localhost:8000/api/v1/agents/register" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "my-fund-agent",
    "agent_name": "我的基金分析 Agent",
    "agent_type": "http",
    "endpoint": "http://localhost:8001/chat",
    "description": "基于 GPT-4o 的基金投顾智能体",
    "config": {
      "max_tokens": 4096,
      "temperature": 0.7,
      "timeout": 30
    }
  }'
```

#### LangGraph Agent（Python SDK）

```python
from finagent import LangGraphAdapter, AgentConfig, EvalPipeline, PipelineConfig
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI

# 创建 LangGraph Agent
model = ChatOpenAI(model="gpt-4o")
graph = create_react_agent(model=model, tools=[])

# 创建适配器
config = AgentConfig(
    agent_id="my-langgraph-agent",
    agent_name="我的 LangGraph Agent",
    agent_type="langgraph",
)
adapter = LangGraphAdapter(graph=graph, config=config)

# 运行评测
pipeline = EvalPipeline(agent=adapter, config=PipelineConfig(eval_mode="quick"))
result = await pipeline.run()
print(f"总体分数: {result.evaluation_score.overall_score}")
print(f"评级: {result.evaluation_score.overall_rating}")
```

### 2.3 配置评测参数

#### 评测模式选择

| 模式 | 维度数 | 任务数 | 耗时 | 适用场景 |
|------|--------|--------|------|----------|
| 快速评测 (quick) | 5 | ~20 | ~4 小时 | 日常迭代、快速验证 |
| 完整评测 (full) | 11 | ~60-100 | ~12 小时 | 发布前、全面评估 |

#### 评测维度说明

**能力维度（权重 60%）：**
- 准确性 (accuracy) - 事实准确性和数据正确性
- 完整性 (completeness) - 回答覆盖度
- 推理能力 (reasoning) - 逻辑推理和分析
- 工具使用 (tool_usage) - 工具调用正确性
- 专业性 (professionalism) - 专业术语和规范

**可信度维度（权重 40%）：**
- 合规性 (compliance) - 监管合规要求
- 风险意识 (risk_awareness) - 风险识别和提示
- 鲁棒性 (robustness) - 异常处理能力
- 安全性 (security) - 安全防护能力
- 透明度 (transparency) - 可解释性
- 一致性 (consistency) - 逻辑自洽性

### 2.4 运行完整评测

```bash
# 启动完整评测（启用三阶段流水线）
curl -X POST "http://localhost:8000/api/v1/evaluation/start" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "my-fund-agent",
    "eval_mode": "full",
    "enable_three_stage": true,
    "datasets": ["bizfinbench", "fintrust"],
    "judge_models": ["gpt-4o", "claude-3-opus"]
  }'
```

### 2.5 监控评测进度

#### 使用 WebSocket 实时监控

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/evaluation/{eval_id}?token={token}');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'progress') {
    console.log(`进度: ${data.progress}% | 阶段: ${data.current_phase}`);
  }
};
```

#### 使用 API 轮询

```python
import time

eval_id = "eval-20250601-abc123"
while True:
    resp = client.get(f"/api/v1/evaluation/{eval_id}")
    data = resp.json()
    print(f"状态: {data['status']} | 进度: {data['progress']}%")
    if data["status"] in ("completed", "failed"):
        break
    time.sleep(60)
```

### 2.6 生成评测报告

```bash
# 生成 JSON 格式报告
curl -X POST "http://localhost:8000/api/v1/reports/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "eval_id": "eval-20250601-abc123",
    "format": "json",
    "include_adversarial": true,
    "include_recommendations": true
  }'
```

### 2.7 解读评测结果

评测报告包含以下关键信息：

```json
{
  "overall_score": 87.5,
  "overall_rating": "A",
  "capability_scores": {
    "accuracy": 88.5,
    "completeness": 82.0,
    "reasoning": 85.3,
    "tool_usage": 90.1
  },
  "trustworthiness_scores": {
    "compliance": 92.5,
    "security": 90.0,
    "risk_awareness": 84.0
  },
  "recommendations": [
    "建议加强完整性维度，当前回答在部分场景下信息覆盖不足"
  ]
}
```

**评级标准：**

| 评级 | 分数范围 | 说明 |
|------|----------|------|
| S | 95-100 | 卓越 — 可直接投入生产环境 |
| A | 85-94 | 优秀 — 满足大部分生产要求 |
| B | 70-84 | 良好 — 基本满足要求，部分维度需改进 |
| C | 60-69 | 合格 — 存在明显短板，需针对性优化 |
| D | <60 | 不合格 — 不建议上线 |

> **一票否决机制：** 当合规性或安全性维度得分低于 30 分时，无论总分如何，均直接评为 D 级。

---

## 3. 常见使用场景

### 场景一：日常迭代验证

适用于开发过程中的快速验证：

```bash
# 使用快速评测模式
finagent-eval eval --agent-id my-agent --endpoint http://localhost:8001 --mode quick

# 仅评测特定维度
curl -X POST "http://localhost:8000/api/v1/evaluation/start" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "my-agent",
    "eval_mode": "quick",
    "dimensions": ["accuracy", "compliance"]
  }'
```

### 场景二：发布前全面评估

适用于正式发布前的全面评估：

```bash
# 使用完整评测 + 三阶段流水线
finagent-eval eval --agent-id my-agent --endpoint http://localhost:8001 --mode full --three-stage

# 生成合规认证报告
curl -X POST "http://localhost:8000/api/v1/compliance/report" \
  -H "Content-Type: application/json" \
  -d '{
    "evaluation_id": "eval-xxx",
    "compliance_framework": "china_fund_regulation"
  }'
```

### 场景三：多 Agent 对比选型

适用于选择最佳 Agent 方案：

```bash
# 启动对比评测
curl -X POST "http://localhost:8000/api/v1/evaluation/compare" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_ids": ["agent-v1", "agent-v2", "agent-v3"],
    "eval_mode": "quick"
  }'

# 与行业基准对比
curl -X POST "http://localhost:8000/api/v1/benchmark" \
  -H "Content-Type: application/json" \
  -d '{
    "evaluation_id": "eval-xxx",
    "benchmark_type": "industry_average"
  }'
```

---

## 4. 下一步学习

### 深入了解评测维度

- [评测维度说明](../README.md#评测维度说明) - 了解 4+7 双层评测体系
- [三阶段流水线](three_stage_pipeline.md) - 深入理解 STATIC/DYNAMIC/TRUST 阶段
- [评分机制](../README.md#评级标准) - 了解评分算法和一票否决机制

### 自定义评测任务

- [任务生成指南](api_reference.md#4-任务管理apiv1tasks) - 自定义评测数据集
- [适配器开发](adapter_guide.md) - 接入自定义 Agent 框架
- [接口规范](interface_spec.md) - 了解 FinancialAgentInterface

### 集成到 CI/CD

```yaml
# .github/workflows/eval.yml
name: Agent Evaluation

on:
  push:
    branches: [main]

jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Start services
        run: docker-compose up -d
        
      - name: Run evaluation
        run: |
          finagent-eval eval \
            --agent-id ${{ vars.AGENT_ID }} \
            --endpoint ${{ secrets.AGENT_ENDPOINT }} \
            --mode quick \
            -o result.json
            
      - name: Check score
        run: |
          score=$(jq '.overall_score' result.json)
          if [ "$score" -lt 80 ]; then
            echo "Score $score is below threshold 80"
            exit 1
          fi
```

### 更多文档

| 文档 | 说明 |
|------|------|
| [用户手册](user_manual.md) | 完整使用指南 |
| [API 参考](api_reference.md) | REST API 详细文档 |
| [部署指南](deployment.md) | 生产环境部署 |
| [常见问题](faq.md) | FAQ |

---

## 5. 获取帮助

- **文档**：https://finagent-eval.readthedocs.io
- **GitHub Issues**：https://github.com/finagent/finagent-eval/issues
- **社区讨论**：https://github.com/finagent/finagent-eval/discussions
