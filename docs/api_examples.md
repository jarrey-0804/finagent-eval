# API 使用示例

> FinAgent-Eval REST API 实用调用示例，涵盖所有端点的 curl 与 Python httpx 用法。

---

## 目录

- [认证](#认证)
- [健康检查端点](#健康检查端点)
- [评测管理](#评测管理)
- [Agent 管理](#agent-管理)
- [报告管理](#报告管理)
- [WebSocket 实时进度](#websocket-实时进度)
- [Agent 对比评测](#agent-对比评测)
- [行业基准对比](#行业基准对比)
- [合规认证报告](#合规认证报告)
- [智能改进建议](#智能改进建议)
- [系统信息](#系统信息)

---

## 认证

系统使用 JWT Bearer Token 进行认证。所有 `/api/v1/*` 端点（除健康检查外）均需要在请求头中携带有效的 JWT Token。

### 获取 JWT Token

```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "your_password"
  }'
```

响应示例：

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbiIsImV4cCI6MTcxNjU2MTYwMH0.xxxxxxxxx",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### 在请求中使用 Bearer Token

获取 Token 后，在后续所有 API 请求的 `Authorization` 头中携带：

```bash
curl -X GET "http://localhost:8000/api/v1/info" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xxxxxxxxx"
```

### Python httpx 示例

```python
import httpx

BASE_URL = "http://localhost:8000"

# 登录获取 Token
def login(username: str, password: str) -> str:
    resp = httpx.post(f"{BASE_URL}/api/v1/auth/login", json={
        "username": username,
        "password": password,
    })
    resp.raise_for_status()
    data = resp.json()
    return data["access_token"]

# 创建带认证的客户端
def create_client(token: str) -> httpx.Client:
    return httpx.Client(
        base_url=BASE_URL,
        headers={"Authorization": f"Bearer {token}"}
    )

# 使用示例
token = login("admin", "your_password")
client = create_client(token)
```

> **提示：** 后续所有 Python 示例均假定已通过上述方式获取了 `client` 实例。

---

## 健康检查端点

健康检查端点无需认证，用于服务探活与就绪检测。

### GET /health — 基础健康检查

返回服务基本运行状态，不检查依赖服务。

```bash
curl -X GET "http://localhost:8000/health"
```

响应示例：

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2025-06-01T10:30:00Z"
}
```

Python 示例：

```python
resp = httpx.get(f"{BASE_URL}/health")
print(resp.json())
# {"status": "healthy", "version": "1.0.0", "timestamp": "..."}
```

### GET /ready — 就绪检查（含数据库连接检测）

检查服务及其依赖（如数据库）是否就绪，适用于 Kubernetes readinessProbe。

```bash
curl -X GET "http://localhost:8000/ready"
```

响应示例（就绪）：

```json
{
  "status": "ready",
  "checks": {
    "database": "ok",
    "redis": "ok"
  },
  "timestamp": "2025-06-01T10:30:00Z"
}
```

响应示例（未就绪）：

```json
{
  "status": "not_ready",
  "checks": {
    "database": "error: connection refused",
    "redis": "ok"
  },
  "timestamp": "2025-06-01T10:30:00Z"
}
```

Python 示例：

```python
resp = httpx.get(f"{BASE_URL}/ready")
data = resp.json()
if data["status"] == "ready":
    print("服务已就绪")
else:
    print(f"服务未就绪: {data['checks']}")
```

### GET /live — 存活检查

轻量级存活探针，仅确认进程是否存活，适用于 Kubernetes livenessProbe。

```bash
curl -X GET "http://localhost:8000/live"
```

响应示例：

```json
{
  "status": "alive"
}
```

Python 示例：

```python
resp = httpx.get(f"{BASE_URL}/live")
print(resp.json())
# {"status": "alive"}
```

---

## 评测管理

### POST /api/v1/evaluation/start — 启动评测

启动一个新的评测任务。支持快速评测（quick）和完整评测（full）两种模式，可通过 `enable_three_stage` 选项启用三阶段评估流水线（STATIC -> DYNAMIC -> TRUST）。

```bash
curl -X POST "http://localhost:8000/api/v1/evaluation/start" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "agent-001",
    "eval_mode": "full",
    "enable_three_stage": true,
    "datasets": ["bizfinbench", "fintrust"],
    "judge_models": ["gpt-4o", "claude-3-opus"],
    "adversarial_level": "meta_cognitive"
  }'
```

响应示例：

```json
{
  "eval_id": "eval-20250601-abc123",
  "agent_id": "agent-001",
  "status": "running",
  "eval_mode": "full",
  "enable_three_stage": true,
  "current_phase": "STATIC",
  "created_at": "2025-06-01T10:30:00Z",
  "estimated_duration": "12h"
}
```

请求参数说明：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `agent_id` | string | 是 | 已注册的 Agent ID |
| `eval_mode` | string | 否 | 评测模式：`quick`（默认）或 `full` |
| `enable_three_stage` | boolean | 否 | 是否启用三阶段流水线，默认 `false` |
| `datasets` | list[string] | 否 | 指定评测数据集，默认使用全部 |
| `judge_models` | list[string] | 否 | 指定 LLM Judge 模型，默认使用全部 |
| `adversarial_level` | string | 否 | 对抗性测试级别：`baseline`/`noisy`/`meta_cognitive`/`adversarial` |

Python 示例：

```python
resp = client.post("/api/v1/evaluation/start", json={
    "agent_id": "agent-001",
    "eval_mode": "full",
    "enable_three_stage": True,
    "datasets": ["bizfinbench", "fintrust"],
    "judge_models": ["gpt-4o", "claude-3-opus"],
    "adversarial_level": "meta_cognitive",
})
resp.raise_for_status()
eval_data = resp.json()
print(f"评测已启动: {eval_data['eval_id']}")
print(f"当前阶段: {eval_data['current_phase']}")
```

### GET /api/v1/evaluation/{eval_id} — 获取评测状态

查询指定评测任务的详细状态与进度，包括当前阶段（`current_phase`）。

```bash
curl -X GET "http://localhost:8000/api/v1/evaluation/eval-20250601-abc123" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xxxxxxxxx"
```

响应示例：

```json
{
  "eval_id": "eval-20250601-abc123",
  "agent_id": "agent-001",
  "status": "running",
  "eval_mode": "full",
  "enable_three_stage": true,
  "current_phase": "DYNAMIC",
  "phase_progress": {
    "STATIC": "completed",
    "DYNAMIC": "in_progress",
    "TRUST": "pending"
  },
  "progress": {
    "total_tasks": 80,
    "completed_tasks": 35,
    "failed_tasks": 1,
    "percentage": 43.75
  },
  "scores": {
    "accuracy": 88.5,
    "completeness": 82.0,
    "reasoning": 85.3,
    "tool_usage": 90.1
  },
  "started_at": "2025-06-01T10:30:00Z",
  "updated_at": "2025-06-01T14:20:00Z",
  "estimated_remaining": "6h 40m"
}
```

Python 示例：

```python
eval_id = "eval-20250601-abc123"
resp = client.get(f"/api/v1/evaluation/{eval_id}")
resp.raise_for_status()
data = resp.json()

print(f"评测状态: {data['status']}")
print(f"当前阶段: {data['current_phase']}")
print(f"进度: {data['progress']['percentage']}%")
print(f"阶段详情: {data['phase_progress']}")
```

### GET /api/v1/evaluations — 列出评测任务

列出所有评测任务，支持分页和状态过滤。此端点为 `/api/v1/evaluation/` 的别名。

```bash
curl -X GET "http://localhost:8000/api/v1/evaluations?status=running&limit=10&offset=0" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xxxxxxxxx"
```

响应示例：

```json
{
  "total": 25,
  "items": [
    {
      "eval_id": "eval-20250601-abc123",
      "agent_id": "agent-001",
      "status": "running",
      "eval_mode": "full",
      "current_phase": "DYNAMIC",
      "progress": 43.75,
      "started_at": "2025-06-01T10:30:00Z"
    },
    {
      "eval_id": "eval-20250530-def456",
      "agent_id": "agent-002",
      "status": "completed",
      "eval_mode": "quick",
      "current_phase": null,
      "progress": 100.0,
      "started_at": "2025-05-30T08:00:00Z"
    }
  ],
  "limit": 10,
  "offset": 0
}
```

查询参数说明：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `status` | string | 否 | 按状态过滤：`pending`/`running`/`completed`/`failed`/`cancelled` |
| `agent_id` | string | 否 | 按 Agent ID 过滤 |
| `limit` | int | 否 | 每页数量，默认 20 |
| `offset` | int | 否 | 偏移量，默认 0 |

Python 示例：

```python
resp = client.get("/api/v1/evaluations", params={
    "status": "running",
    "limit": 10,
    "offset": 0,
})
resp.raise_for_status()
data = resp.json()
print(f"共 {data['total']} 条评测记录")
for item in data["items"]:
    print(f"  {item['eval_id']} | {item['agent_id']} | {item['status']} | {item['progress']}%")
```

### POST /api/v1/evaluation/{eval_id}/cancel — 取消评测

取消正在运行或等待中的评测任务。

```bash
curl -X POST "http://localhost:8000/api/v1/evaluation/eval-20250601-abc123/cancel" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xxxxxxxxx"
```

响应示例：

```json
{
  "eval_id": "eval-20250601-abc123",
  "status": "cancelled",
  "message": "评测任务已取消",
  "cancelled_at": "2025-06-01T15:00:00Z",
  "checkpoint_saved": true
}
```

Python 示例：

```python
resp = client.post(f"/api/v1/evaluation/{eval_id}/cancel")
resp.raise_for_status()
data = resp.json()
print(f"评测 {data['eval_id']} 已取消")
print(f"检查点已保存: {data['checkpoint_saved']}")
```

### POST /api/v1/evaluation/{eval_id}/resume — 从检查点恢复评测

从上次保存的检查点恢复已取消或失败的评测任务，支持断点续跑。

```bash
curl -X POST "http://localhost:8000/api/v1/evaluation/eval-20250601-abc123/resume" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xxxxxxxxx"
```

响应示例：

```json
{
  "eval_id": "eval-20250601-abc123",
  "status": "running",
  "message": "评测已从检查点恢复",
  "resumed_from_phase": "DYNAMIC",
  "resumed_from_task": 36,
  "total_tasks": 80,
  "resumed_at": "2025-06-02T09:00:00Z"
}
```

Python 示例：

```python
resp = client.post(f"/api/v1/evaluation/{eval_id}/resume")
resp.raise_for_status()
data = resp.json()
print(f"评测已恢复，从阶段 {data['resumed_from_phase']} 的第 {data['resumed_from_task']} 个任务继续")
print(f"剩余任务: {data['total_tasks'] - data['resumed_from_task']}")
```

---

## Agent 管理

### POST /api/v1/agents/register — 注册 Agent

注册一个新的待评测 Agent。

```bash
curl -X POST "http://localhost:8000/api/v1/agents/register" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "agent-001",
    "agent_name": "智能投顾助手 v2.0",
    "agent_type": "http",
    "endpoint": "http://localhost:8001/chat",
    "description": "基于 GPT-4o 的基金投顾智能体，支持多轮对话与工具调用",
    "config": {
      "max_tokens": 4096,
      "temperature": 0.7,
      "timeout": 30
    }
  }'
```

响应示例：

```json
{
  "agent_id": "agent-001",
  "agent_name": "智能投顾助手 v2.0",
  "agent_type": "http",
  "status": "active",
  "registered_at": "2025-06-01T10:00:00Z",
  "last_evaluated": null
}
```

请求参数说明：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `agent_id` | string | 是 | Agent 唯一标识 |
| `agent_name` | string | 是 | Agent 显示名称 |
| `agent_type` | string | 是 | 适配器类型：`langgraph`/`autogen`/`crewai`/`http` |
| `endpoint` | string | 否 | Agent 服务端点（HTTP 类型必填） |
| `description` | string | 否 | Agent 描述 |
| `config` | object | 否 | Agent 配置参数 |

Python 示例：

```python
resp = client.post("/api/v1/agents/register", json={
    "agent_id": "agent-001",
    "agent_name": "智能投顾助手 v2.0",
    "agent_type": "http",
    "endpoint": "http://localhost:8001/chat",
    "description": "基于 GPT-4o 的基金投顾智能体",
    "config": {
        "max_tokens": 4096,
        "temperature": 0.7,
        "timeout": 30,
    },
})
resp.raise_for_status()
data = resp.json()
print(f"Agent {data['agent_id']} 注册成功")
```

### GET /api/v1/agents — 列出 Agent

列出所有已注册的 Agent。

```bash
curl -X GET "http://localhost:8000/api/v1/agents?limit=10&offset=0" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xxxxxxxxx"
```

响应示例：

```json
{
  "total": 3,
  "items": [
    {
      "agent_id": "agent-001",
      "agent_name": "智能投顾助手 v2.0",
      "agent_type": "http",
      "status": "active",
      "registered_at": "2025-06-01T10:00:00Z",
      "last_evaluated": "2025-06-01T10:30:00Z",
      "latest_score": 87.5,
      "latest_rating": "A"
    },
    {
      "agent_id": "agent-002",
      "agent_name": "基金分析 Agent",
      "agent_type": "langgraph",
      "status": "active",
      "registered_at": "2025-05-28T09:00:00Z",
      "last_evaluated": "2025-05-30T08:00:00Z",
      "latest_score": 72.3,
      "latest_rating": "B"
    }
  ],
  "limit": 10,
  "offset": 0
}
```

Python 示例：

```python
resp = client.get("/api/v1/agents", params={"limit": 10, "offset": 0})
resp.raise_for_status()
data = resp.json()
print(f"共 {data['total']} 个 Agent")
for agent in data["items"]:
    print(f"  {agent['agent_id']} | {agent['agent_name']} | 评分: {agent['latest_score']} | 评级: {agent['latest_rating']}")
```

### GET /api/v1/agents/{agent_id} — 获取 Agent 详情

获取指定 Agent 的详细信息，包括配置和历史评测摘要。

```bash
curl -X GET "http://localhost:8000/api/v1/agents/agent-001" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xxxxxxxxx"
```

响应示例：

```json
{
  "agent_id": "agent-001",
  "agent_name": "智能投顾助手 v2.0",
  "agent_type": "http",
  "endpoint": "http://localhost:8001/chat",
  "description": "基于 GPT-4o 的基金投顾智能体，支持多轮对话与工具调用",
  "status": "active",
  "config": {
    "max_tokens": 4096,
    "temperature": 0.7,
    "timeout": 30
  },
  "registered_at": "2025-06-01T10:00:00Z",
  "evaluation_summary": {
    "total_evaluations": 5,
    "latest_score": 87.5,
    "latest_rating": "A",
    "best_score": 91.2,
    "average_score": 84.6
  }
}
```

Python 示例：

```python
resp = client.get("/api/v1/agents/agent-001")
resp.raise_for_status()
data = resp.json()
print(f"Agent: {data['agent_name']}")
print(f"类型: {data['agent_type']}")
summary = data["evaluation_summary"]
print(f"评测次数: {summary['total_evaluations']}")
print(f"最新评分: {summary['latest_score']} ({summary['latest_rating']})")
print(f"最高评分: {summary['best_score']}")
```

### DELETE /api/v1/agents/{agent_id} — 删除 Agent

注销并删除指定的 Agent 及其相关数据。

```bash
curl -X DELETE "http://localhost:8000/api/v1/agents/agent-001" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xxxxxxxxx"
```

响应示例：

```json
{
  "agent_id": "agent-001",
  "message": "Agent 已成功删除",
  "deleted_at": "2025-06-01T16:00:00Z"
}
```

Python 示例：

```python
resp = client.delete("/api/v1/agents/agent-001")
resp.raise_for_status()
data = resp.json()
print(f"Agent {data['agent_id']} 已删除")
```

---

## 报告管理

### GET /api/v1/reports — 列出报告

列出所有已生成的评测报告。

```bash
curl -X GET "http://localhost:8000/api/v1/reports?agent_id=agent-001&limit=10" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xxxxxxxxx"
```

响应示例：

```json
{
  "total": 3,
  "items": [
    {
      "report_id": "rpt-20250601-xyz789",
      "eval_id": "eval-20250601-abc123",
      "agent_id": "agent-001",
      "status": "completed",
      "overall_score": 87.5,
      "overall_rating": "A",
      "generated_at": "2025-06-01T22:30:00Z",
      "format": "json"
    }
  ],
  "limit": 10,
  "offset": 0
}
```

Python 示例：

```python
resp = client.get("/api/v1/reports", params={
    "agent_id": "agent-001",
    "limit": 10,
})
resp.raise_for_status()
data = resp.json()
for report in data["items"]:
    print(f"  {report['report_id']} | 评分: {report['overall_score']} | 评级: {report['overall_rating']}")
```

### GET /api/v1/reports/{report_id} — 获取报告

获取指定评测报告的完整内容。

```bash
curl -X GET "http://localhost:8000/api/v1/reports/rpt-20250601-xyz789" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xxxxxxxxx"
```

响应示例：

```json
{
  "report_id": "rpt-20250601-xyz789",
  "eval_id": "eval-20250601-abc123",
  "agent_id": "agent-001",
  "agent_name": "智能投顾助手 v2.0",
  "generated_at": "2025-06-01T22:30:00Z",
  "overall_score": 87.5,
  "overall_rating": "A",
  "capability_scores": {
    "accuracy": 88.5,
    "completeness": 82.0,
    "reasoning": 85.3,
    "tool_usage": 90.1
  },
  "trustworthiness_scores": {
    "professionalism": 86.0,
    "compliance": 92.5,
    "risk_awareness": 84.0,
    "robustness": 88.0,
    "security": 90.0,
    "transparency": 85.5,
    "consistency": 87.0
  },
  "adversarial_results": {
    "baseline": {"score": 90.0, "passed": true},
    "noisy": {"score": 85.0, "passed": true},
    "meta_cognitive": {"score": 78.0, "passed": true}
  },
  "judge_consensus": {
    "models_used": ["gpt-4o", "claude-3-opus", "deepseek-v3"],
    "agreement_rate": 0.85,
    "fleiss_kappa": 0.72
  },
  "recommendations": [
    "建议加强完整性维度，当前回答在部分场景下信息覆盖不足",
    "风险意识维度可进一步优化，建议增加下行风险分析"
  ]
}
```

Python 示例：

```python
resp = client.get("/api/v1/reports/rpt-20250601-xyz789")
resp.raise_for_status()
report = resp.json()

print(f"=== 评测报告 ===")
print(f"Agent: {report['agent_name']}")
print(f"总评分: {report['overall_score']} ({report['overall_rating']})")
print(f"\n能力维度:")
for dim, score in report["capability_scores"].items():
    print(f"  {dim}: {score}")
print(f"\n可信度维度:")
for dim, score in report["trustworthiness_scores"].items():
    print(f"  {dim}: {score}")
print(f"\n建议:")
for rec in report["recommendations"]:
    print(f"  - {rec}")
```

### POST /api/v1/reports/generate — 生成报告

为已完成的评测生成报告。支持指定输出格式。

```bash
curl -X POST "http://localhost:8000/api/v1/reports/generate" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "eval_id": "eval-20250601-abc123",
    "format": "json",
    "include_adversarial": true,
    "include_recommendations": true
  }'
```

响应示例：

```json
{
  "report_id": "rpt-20250601-xyz789",
  "eval_id": "eval-20250601-abc123",
  "status": "generating",
  "message": "报告生成中，预计需要 1-2 分钟",
  "created_at": "2025-06-01T22:28:00Z"
}
```

请求参数说明：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `eval_id` | string | 是 | 已完成的评测 ID |
| `format` | string | 否 | 输出格式：`json`（默认）/ `pdf`/ `html` |
| `include_adversarial` | boolean | 否 | 是否包含对抗性测试结果，默认 `true` |
| `include_recommendations` | boolean | 否 | 是否包含改进建议，默认 `true` |

Python 示例：

```python
resp = client.post("/api/v1/reports/generate", json={
    "eval_id": "eval-20250601-abc123",
    "format": "json",
    "include_adversarial": True,
    "include_recommendations": True,
})
resp.raise_for_status()
data = resp.json()
print(f"报告生成中: {data['report_id']}")
print(data["message"])
```

---

## WebSocket 实时进度

通过 WebSocket 连接实时获取评测进度，无需轮询 API。

### 连接 WebSocket

```javascript
// JavaScript/TypeScript 前端示例
const evalId = 'eval-20250601-abc123';
const token = localStorage.getItem('token');
const ws = new WebSocket(`ws://localhost:8000/ws/evaluation/${evalId}?token=${token}`);

ws.onopen = () => {
  console.log('WebSocket 已连接');
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  handleMessage(data);
};

ws.onerror = (error) => {
  console.error('WebSocket 错误:', error);
};

ws.onclose = () => {
  console.log('WebSocket 已断开');
};
```

### 处理消息类型

```javascript
function handleMessage(data) {
  switch (data.type) {
    case 'progress':
      console.log(`进度: ${data.progress}% | 阶段: ${data.current_phase}`);
      console.log(`消息: ${data.message}`);
      updateProgressBar(data.progress);
      break;

    case 'status_change':
      console.log(`状态变更: ${data.status}`);
      if (data.status === 'completed') {
        showResult(data.result);
      }
      break;

    case 'task_completed':
      console.log(`任务 ${data.task_id} 完成，维度: ${data.dimension}，分数: ${data.score}`);
      updateTaskList(data);
      break;

    case 'error':
      console.error(`评测错误: ${data.error}`);
      showError(data.error);
      break;

    case 'ping':
      // 响应心跳
      ws.send(JSON.stringify({ type: 'pong' }));
      break;
  }
}
```

### React Hook 示例

```javascript
// useWebSocket.js
import { useEffect, useRef, useState } from 'react';

export function useWebSocket(evalId, token) {
  const [progress, setProgress] = useState(null);
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);
  const wsRef = useRef(null);

  useEffect(() => {
    if (!evalId || !token) return;

    const ws = new WebSocket(`ws://localhost:8000/ws/evaluation/${evalId}?token=${token}`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.type === 'progress') {
        setProgress(data);
      } else if (data.type === 'status_change') {
        setStatus(data);
      } else if (data.type === 'error') {
        setError(data.error);
      } else if (data.type === 'ping') {
        ws.send(JSON.stringify({ type: 'pong' }));
      }
    };

    return () => {
      ws.close();
    };
  }, [evalId, token]);

  return { progress, status, error };
}
```

### 自动重连处理

```javascript
class EvaluationWebSocket {
  constructor(evalId, token, onMessage) {
    this.evalId = evalId;
    this.token = token;
    this.onMessage = onMessage;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.connect();
  }

  connect() {
    const ws = new WebSocket(
      `ws://localhost:8000/ws/evaluation/${this.evalId}?token=${this.token}`
    );

    ws.onopen = () => {
      console.log('WebSocket 已连接');
      this.reconnectAttempts = 0;
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'ping') {
        ws.send(JSON.stringify({ type: 'pong' }));
      } else {
        this.onMessage(data);
      }
    };

    ws.onclose = () => {
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        this.reconnectAttempts++;
        const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
        console.log(`${delay}ms 后尝试重连...`);
        setTimeout(() => this.connect(), delay);
      }
    };

    this.ws = ws;
  }

  close() {
    if (this.ws) {
      this.ws.close();
    }
  }
}
```

---

## Agent 对比评测

同时评测多个 Agent 并生成对比报告，便于选型和性能比较。

### POST /api/v1/evaluation/compare — 启动对比评测

```bash
curl -X POST "http://localhost:8000/api/v1/evaluation/compare" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_ids": ["agent-001", "agent-002", "agent-003"],
    "eval_mode": "quick",
    "dimensions": ["accuracy", "completeness", "reasoning", "compliance"],
    "datasets": ["bizfinbench"]
  }'
```

响应示例：

```json
{
  "comparison_id": "comp-20250601-xyz",
  "status": "running",
  "agent_ids": ["agent-001", "agent-002", "agent-003"],
  "created_at": "2025-06-01T10:00:00Z",
  "estimated_duration": "4h"
}
```

Python 示例：

```python
resp = client.post("/api/v1/evaluation/compare", json={
    "agent_ids": ["agent-001", "agent-002", "agent-003"],
    "eval_mode": "quick",
    "dimensions": ["accuracy", "completeness", "reasoning", "compliance"],
    "datasets": ["bizfinbench"],
})
resp.raise_for_status()
data = resp.json()
print(f"对比评测已启动: {data['comparison_id']}")
print(f"参与 Agent: {', '.join(data['agent_ids'])}")
```

### GET /api/v1/evaluation/compare/{comparison_id} — 获取对比结果

```bash
curl -X GET "http://localhost:8000/api/v1/evaluation/compare/comp-20250601-xyz" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xxxxxxxxx"
```

响应示例：

```json
{
  "comparison_id": "comp-20250601-xyz",
  "status": "completed",
  "results": [
    {
      "agent_id": "agent-001",
      "agent_name": "智能投顾助手 v2.0",
      "overall_score": 87.5,
      "overall_rating": "A",
      "dimension_scores": {
        "accuracy": 88.5,
        "completeness": 82.0,
        "reasoning": 85.3,
        "compliance": 94.2
      }
    },
    {
      "agent_id": "agent-002",
      "agent_name": "基金分析 Agent",
      "overall_score": 82.3,
      "overall_rating": "B",
      "dimension_scores": {
        "accuracy": 85.0,
        "completeness": 78.5,
        "reasoning": 80.2,
        "compliance": 85.5
      }
    },
    {
      "agent_id": "agent-003",
      "agent_name": "投资顾问 Pro",
      "overall_score": 79.8,
      "overall_rating": "B",
      "dimension_scores": {
        "accuracy": 82.0,
        "completeness": 75.0,
        "reasoning": 78.5,
        "compliance": 83.7
      }
    }
  ],
  "ranking": ["agent-001", "agent-002", "agent-003"],
  "comparison_summary": {
    "best_in_accuracy": "agent-001",
    "best_in_compliance": "agent-001",
    "best_in_reasoning": "agent-001",
    "best_in_completeness": "agent-001"
  },
  "generated_at": "2025-06-01T14:00:00Z"
}
```

---

## 行业基准对比

将评测结果与行业基准进行对比，了解 Agent 在行业中的位置。

### POST /api/v1/benchmark — 启动基准对比

```bash
curl -X POST "http://localhost:8000/api/v1/benchmark" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "evaluation_id": "eval-20250601-abc123",
    "benchmark_type": "industry_average",
    "segments": ["fund_analysis", "investment_advice", "risk_assessment"]
  }'
```

请求参数说明：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `evaluation_id` | string | 是 | 已完成的评测 ID |
| `benchmark_type` | string | 否 | `industry_average`（行业平均）或 `top_performers`（头部表现） |
| `segments` | list | 否 | 按业务分段对比 |

Python 示例：

```python
resp = client.post("/api/v1/benchmark", json={
    "evaluation_id": "eval-20250601-abc123",
    "benchmark_type": "industry_average",
})
resp.raise_for_status()
data = resp.json()

print(f"=== 行业基准对比报告 ===")
print(f"您的评分: {data['comparison']['overall']['your_score']}")
print(f"行业平均: {data['comparison']['overall']['benchmark_score']}")
print(f"百分位排名: {data['comparison']['overall']['percentile']}%")

for rec in data['recommendations']:
    print(f"  - {rec}")
```

---

## 合规认证报告

生成符合监管要求的合规认证报告。

### POST /api/v1/compliance/report — 生成合规报告

```bash
curl -X POST "http://localhost:8000/api/v1/compliance/report" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "evaluation_id": "eval-20250601-abc123",
    "compliance_framework": "china_fund_regulation",
    "include_evidence": true
  }'
```

响应示例：

```json
{
  "report_id": "comp-20250601-xyz",
  "evaluation_id": "eval-20250601-abc123",
  "framework": "china_fund_regulation",
  "status": "passed",
  "overall_compliance_score": 92.5,
  "check_items": [
    {
      "item_id": "risk_disclosure",
      "name": "风险披露",
      "status": "passed",
      "score": 95.0,
      "evidence_count": 15
    },
    {
      "item_id": "suitability",
      "name": "投资者适当性",
      "status": "passed",
      "score": 90.0,
      "evidence_count": 12
    }
  ],
  "veto_triggered": false,
  "valid_until": "2025-09-01T16:00:00Z"
}
```

Python 示例：

```python
resp = client.post("/api/v1/compliance/report", json={
    "evaluation_id": "eval-20250601-abc123",
    "compliance_framework": "china_fund_regulation",
    "include_evidence": True,
})
resp.raise_for_status()
report = resp.json()

print(f"=== 合规认证报告 ===")
print(f"认证状态: {report['status']}")
print(f"合规评分: {report['overall_compliance_score']}")
print(f"有效期至: {report['valid_until']}")
print(f"\n检查项详情:")
for item in report['check_items']:
    print(f"  {item['name']}: {item['status']} ({item['score']}分)")
```

---

## 智能改进建议

基于评测结果生成针对性的改进建议。

### POST /api/v1/improvement/suggestions — 获取改进建议

```bash
curl -X POST "http://localhost:8000/api/v1/improvement/suggestions" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "evaluation_id": "eval-20250601-abc123",
    "focus_areas": ["completeness", "risk_awareness"],
    "detail_level": "comprehensive"
  }'
```

Python 示例：

```python
resp = client.post("/api/v1/improvement/suggestions", json={
    "evaluation_id": "eval-20250601-abc123",
    "focus_areas": ["completeness", "risk_awareness"],
    "detail_level": "comprehensive",
})
resp.raise_for_status()
suggestions = resp.json()

print(f"=== 改进建议 ===")
print(f"总体评估: {suggestions['overall_assessment']}")
print(f"\n快速见效:")
for win in suggestions['quick_wins']:
    print(f"  - {win}")

for sug in suggestions['suggestions']:
    print(f"\n【{sug['dimension']}】当前: {sug['current_score']} → 目标: {sug['target_score']}")
    print(f"优先级: {sug['priority']}")
    print(f"问题:")
    for issue in sug['issues']:
        print(f"  - {issue}")
    print(f"建议:")
    for rec in sug['recommendations']:
        print(f"  - {rec['action']}: {rec['description']}")
        print(f"    实施方法: {rec['implementation']}")
```

---

## 系统信息

### GET /api/v1/info — 获取 API 信息

获取系统版本、支持的功能列表等元信息。

```bash
curl -X GET "http://localhost:8000/api/v1/info" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xxxxxxxxx"
```

响应示例：

```json
{
  "name": "FinAgent-Eval",
  "version": "1.0.0",
  "description": "基金金融AI Agent自主评测系统",
  "api_version": "v1",
  "features": {
    "three_stage_pipeline": true,
    "distributed_scheduler": true,
    "checkpoint_resume": true,
    "response_time_monitoring": true,
    "adversarial_testing": true,
    "llm_judge_consensus": true
  },
  "supported_adapters": ["langgraph", "autogen", "crewai", "http"],
  "supported_datasets": [
    "bizfinbench",
    "finmcp_bench",
    "fintrust",
    "stockbench",
    "traderbench"
  ],
  "judge_models": [
    "gpt-4o",
    "claude-3-opus",
    "deepseek-v3"
  ]
}
```

Python 示例：

```python
resp = client.get("/api/v1/info")
resp.raise_for_status()
info = resp.json()

print(f"系统: {info['name']} v{info['version']}")
print(f"API 版本: {info['api_version']}")
print(f"支持适配器: {', '.join(info['supported_adapters'])}")
print(f"功能特性:")
for feature, enabled in info["features"].items():
    status = "已启用" if enabled else "未启用"
    print(f"  {feature}: {status}")
```

---

## 错误处理

所有 API 端点在发生错误时返回统一的错误格式：

```json
{
  "error": {
    "code": "EVAL_NOT_FOUND",
    "message": "评测任务 eval-xxx 不存在",
    "details": null
  }
}
```

常见 HTTP 状态码：

| 状态码 | 说明 |
|--------|------|
| 400 | 请求参数错误 |
| 401 | 未认证或 Token 已过期 |
| 403 | 无权限访问 |
| 404 | 资源不存在 |
| 409 | 资源冲突（如 Agent ID 已存在） |
| 422 | 请求体验证失败 |
| 429 | 请求频率超限（触发限流） |
| 500 | 服务器内部错误 |

Python 错误处理示例：

```python
try:
    resp = client.get("/api/v1/evaluation/non-existent-id")
    resp.raise_for_status()
except httpx.HTTPStatusError as e:
    error_data = e.response.json()
    print(f"错误码: {error_data['error']['code']}")
    print(f"错误信息: {error_data['error']['message']}")
```

---

## 完整调用流程示例

以下是一个完整的评测流程示例，从 Agent 注册到报告生成：

```python
import httpx
import time

BASE_URL = "http://localhost:8000"

def run_full_evaluation():
    # 1. 登录
    resp = httpx.post(f"{BASE_URL}/api/v1/auth/login", json={
        "username": "admin",
        "password": "your_password",
    })
    token = resp.json()["access_token"]
    client = httpx.Client(base_url=BASE_URL, headers={"Authorization": f"Bearer {token}"})

    # 2. 注册 Agent
    client.post("/api/v1/agents/register", json={
        "agent_id": "my-agent",
        "agent_name": "我的基金助手",
        "agent_type": "http",
        "endpoint": "http://localhost:8001/chat",
    })

    # 3. 启动评测（启用三阶段流水线）
    resp = client.post("/api/v1/evaluation/start", json={
        "agent_id": "my-agent",
        "eval_mode": "quick",
        "enable_three_stage": True,
    })
    eval_id = resp.json()["eval_id"]
    print(f"评测已启动: {eval_id}")

    # 4. 轮询评测状态
    while True:
        resp = client.get(f"/api/v1/evaluation/{eval_id}")
        data = resp.json()
        print(f"状态: {data['status']} | 阶段: {data['current_phase']} | 进度: {data['progress']['percentage']}%")
        if data["status"] in ("completed", "failed", "cancelled"):
            break
        time.sleep(60)

    # 5. 生成报告
    resp = client.post("/api/v1/reports/generate", json={
        "eval_id": eval_id,
        "format": "json",
    })
    report_id = resp.json()["report_id"]
    print(f"报告已生成: {report_id}")

    # 6. 获取报告
    resp = client.get(f"/api/v1/reports/{report_id}")
    report = resp.json()
    print(f"总评分: {report['overall_score']} ({report['overall_rating']})")

    client.close()

if __name__ == "__main__":
    run_full_evaluation()
```
