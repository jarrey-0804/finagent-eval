# REST API 参考文档

> FinAgent-Eval API -- 基础路径 `/api/v1`

> **端点状态说明：** ✅ 已实现 | 🚧 规划中 | 🔧 部分实现

## 1. 认证

API 使用 JWT Bearer Token 认证。以下路径免认证：`/health`、`/api/v1/info`、`/docs`、`/openapi.json`。

**请求头：**
```
Authorization: Bearer <token>
```

Token 默认有效期 24 小时，支持 HS256 算法签名。

## 2. 评测管理（/api/v1/evaluation）

### POST /api/v1/evaluation/start ✅

启动评测任务（异步后台执行）。

**请求体：**
```json
{
    "agent_id": "my-agent",
    "agent_type": "langgraph",
    "agent_config": {},
    "eval_mode": "full",
    "dimensions": ["accuracy", "compliance"],
    "task_count": 20,
    "endpoint_url": "http://localhost:8001",
    "headers": {},
    "enable_three_stage": true
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| agent_id | string | 是 | Agent ID |
| agent_type | string | 否 | 默认 langgraph |
| eval_mode | string | 否 | quick 或 full，默认 full |
| dimensions | list | 否 | 指定评测维度 |
| task_count | int | 否 | 任务数量 |
| endpoint_url | string | 否 | Agent HTTP 端点 |
| enable_three_stage | boolean | 否 | 是否启用三阶段流水线，默认 false |

**响应：**
```json
{
    "evaluation_id": "uuid",
    "status": "pending",
    "message": "评测任务已启动",
    "created_at": "2026-05-08T10:00:00"
}
```

### GET /api/v1/evaluation/{evaluation_id} ✅

获取评测状态和进度。

**响应：**
```json
{
    "evaluation_id": "uuid",
    "agent_id": "my-agent",
    "status": "running",
    "current_stage": "running",
    "current_phase": "DYNAMIC",
    "progress": 45.0,
    "started_at": "2026-05-08T10:00:00",
    "completed_at": null,
    "result": null,
    "error": null
}
```

### DELETE /api/v1/evaluation/{evaluation_id} ✅

取消评测任务。

### GET /api/v1/evaluation/ ✅

列出评测任务。

**查询参数：** `status`（按状态过滤）、`limit`（数量限制，默认 20）

### POST /api/v1/evaluation/{evaluation_id}/resume 🚧

从检查点恢复评测任务。

**响应：**
```json
{
    "evaluation_id": "uuid",
    "status": "running",
    "message": "评测已从检查点恢复",
    "resumed_from_phase": "DYNAMIC",
    "resumed_from_task": 36
}
```

### POST /api/v1/evaluation/compare ✅

> ⚠️ 当前版本参数为 `agent_ids` + `eval_mode`，`dimensions` 和 `datasets` 参数为规划功能。

Agent 对比评测，同时评测多个 Agent 并生成对比报告。

**请求体：**
```json
{
    "agent_ids": ["agent-001", "agent-002", "agent-003"],
    "eval_mode": "quick",
    "dimensions": ["accuracy", "completeness", "reasoning"],
    "datasets": ["bizfinbench"]
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| agent_ids | list[string] | 是 | 待对比的 Agent ID 列表（最多 5 个） |
| eval_mode | string | 否 | 评测模式，默认 quick |
| dimensions | list | 否 | 指定评测维度 |
| datasets | list | 否 | 指定评测数据集 |

**响应：**
```json
{
    "comparison_id": "comp-20250601-xyz",
    "status": "running",
    "agent_ids": ["agent-001", "agent-002", "agent-003"],
    "created_at": "2025-06-01T10:00:00Z",
    "estimated_duration": "4h"
}
```

### POST /api/v1/evaluation/batch ✅

> ⚠️ 当前版本参数为 `agent_ids`（多Agent各一次评测），文档描述的 `agent_id` + `runs`（单Agent多次评测）为规划目标。

批量评测，对单个 Agent 执行多次评测。

**请求体：**
```json
{
    "agent_id": "my-agent",
    "runs": 3,
    "eval_mode": "quick",
    "variation": true
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| agent_id | string | 是 | Agent ID |
| runs | int | 否 | 评测次数，默认 3，最大 10 |
| eval_mode | string | 否 | 评测模式 |
| variation | boolean | 否 | 是否使用不同任务集，默认 true |

**响应：**
```json
{
    "batch_id": "batch-20250601-abc",
    "agent_id": "my-agent",
    "status": "running",
    "total_runs": 3,
    "completed_runs": 0,
    "created_at": "2025-06-01T10:00:00Z"
}
```

## 3. Agent 管理（/api/v1/agents）

### POST /api/v1/agents/register ✅

注册 Agent。

**请求体：**
```json
{
    "agent_id": "my-agent",
    "agent_name": "我的金融Agent",
    "agent_type": "langgraph",
    "description": "基金分析Agent",
    "endpoint_url": "http://localhost:8001",
    "config": {}
}
```

### GET /api/v1/agents/{agent_id} ✅

获取 Agent 信息。

### DELETE /api/v1/agents/{agent_id} ✅

注销 Agent。

### GET /api/v1/agents/ ✅

列出 Agent。**查询参数：** `agent_type`（按类型过滤）、`limit`

## 4. 任务管理（/api/v1/tasks）

### POST /api/v1/tasks/generate ✅

生成评测任务。

**请求体：**
```json
{
    "sources": ["BizFinBench", "FinMCP-Bench"],
    "task_count": 20,
    "eval_mode": "full",
    "difficulty_distribution": {"easy": 0.2, "medium": 0.5, "hard": 0.3}
}
```

### GET /api/v1/tasks/datasets ✅

列出可用数据集：BizFinBench、FinMCP-Bench、StockBench、TraderBench、FINTRUST。

## 5. 报告管理（/api/v1/reports）

### POST /api/v1/reports/generate ✅

> ⚠️ 当前版本请求字段名为 `evaluation_id`，文档中的 `eval_id` 为历史写法。

生成评测报告。

**请求体：**
```json
{
    "evaluation_id": "uuid",
    "format": "json",
    "include_details": true
}
```

支持格式：`json`、`markdown`、`html`。

### GET /api/v1/reports/{evaluation_id} ✅

获取评测报告。

## 6. 行业基准对比（/api/v1/benchmark）

> ⚠️ 当前版本请求参数为 `agent_id` + `agent_type`，文档描述的 `evaluation_id` + `benchmark_type` 模型为规划目标。

### POST /api/v1/benchmark ✅

将评测结果与行业基准进行对比。

**请求体：**
```json
{
    "evaluation_id": "eval-20250601-abc123",
    "benchmark_type": "industry_average",
    "segments": ["fund_analysis", "investment_advice", "risk_assessment"]
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| evaluation_id | string | 是 | 已完成的评测 ID |
| benchmark_type | string | 否 | 基准类型：`industry_average`（行业平均）、`top_performers`（头部表现），默认 industry_average |
| segments | list | 否 | 按业务分段对比 |

**响应：**
```json
{
    "benchmark_id": "bm-20250601-xyz",
    "evaluation_id": "eval-20250601-abc123",
    "benchmark_type": "industry_average",
    "comparison": {
        "overall": {
            "your_score": 87.5,
            "benchmark_score": 75.2,
            "percentile": 85,
            "status": "above_average"
        },
        "dimensions": {
            "accuracy": {
                "your_score": 88.5,
                "benchmark_score": 78.0,
                "percentile": 82
            },
            "completeness": {
                "your_score": 82.0,
                "benchmark_score": 72.5,
                "percentile": 78
            }
        }
    },
    "recommendations": [
        "您的 Agent 在准确性维度表现优秀，超过行业平均 10.5 分",
        "建议加强完整性维度，当前低于行业头部水平"
    ],
    "generated_at": "2025-06-01T15:00:00Z"
}
```

## 7. 合规认证报告（/api/v1/compliance）

> ⚠️ 当前版本仅支持 `evaluation_id` 参数，`compliance_framework` 和 `include_evidence` 为规划功能。

### POST /api/v1/compliance/report ✅

生成合规认证报告，用于监管合规检查。

**请求体：**
```json
{
    "evaluation_id": "eval-20250601-abc123",
    "compliance_framework": "china_fund_regulation",
    "include_evidence": true
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| evaluation_id | string | 是 | 已完成的评测 ID |
| compliance_framework | string | 否 | 合规框架：`china_fund_regulation`（中国基金监管）、`sec_finra`（美国 SEC/FINRA），默认 china_fund_regulation |
| include_evidence | boolean | 否 | 是否包含证据材料，默认 true |

**响应：**
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
        },
        {
            "item_id": "information_disclosure",
            "name": "信息披露",
            "status": "passed",
            "score": 92.5,
            "evidence_count": 18
        }
    ],
    "veto_triggered": false,
    "generated_at": "2025-06-01T16:00:00Z",
    "valid_until": "2025-09-01T16:00:00Z"
}
```

## 8. 智能改进建议（/api/v1/improvement）

> ⚠️ 当前版本仅支持 `evaluation_id` 参数，`focus_areas` 和 `detail_level` 为规划功能。

### POST /api/v1/improvement/suggestions ✅

基于评测结果生成智能改进建议。

**请求体：**
```json
{
    "evaluation_id": "eval-20250601-abc123",
    "focus_areas": ["completeness", "risk_awareness"],
    "detail_level": "comprehensive"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| evaluation_id | string | 是 | 已完成的评测 ID |
| focus_areas | list | 否 | 重点关注维度，默认全部维度 |
| detail_level | string | 否 | 详细程度：`summary`（摘要）、`comprehensive`（全面），默认 comprehensive |

**响应：**
```json
{
    "suggestion_id": "sug-20250601-xyz",
    "evaluation_id": "eval-20250601-abc123",
    "overall_assessment": "您的 Agent 整体表现优秀，但在完整性和风险意识方面仍有提升空间。",
    "suggestions": [
        {
            "dimension": "completeness",
            "current_score": 82.0,
            "target_score": 90.0,
            "priority": "high",
            "issues": [
                "在复杂金融问题场景下，回答覆盖度不足",
                "部分回答缺少风险提示和免责声明"
            ],
            "recommendations": [
                {
                    "action": "增强多轮对话信息整合能力",
                    "description": "建议优化对话上下文管理，确保多轮对话中信息不遗漏",
                    "implementation": "在 Agent 状态管理中增加信息收集清单机制"
                },
                {
                    "action": "添加标准化风险提示模板",
                    "description": "在投资建议类回答末尾添加风险提示",
                    "implementation": "配置风险提示模板，在特定场景自动触发"
                }
            ]
        },
        {
            "dimension": "risk_awareness",
            "current_score": 84.0,
            "target_score": 90.0,
            "priority": "medium",
            "issues": [
                "下行风险分析不够深入"
            ],
            "recommendations": [
                {
                    "action": "增强风险分析工具调用",
                    "description": "在投资分析场景自动调用风险评估工具",
                    "implementation": "添加风险分析工具到 Agent 工具列表"
                }
            ]
        }
    ],
    "quick_wins": [
        "添加风险提示模板可快速提升合规性 3-5 分",
        "优化回答结构模板可提升完整性 2-3 分"
    ],
    "generated_at": "2025-06-01T17:00:00Z"
}
```

## 9. WebSocket 实时推送（/ws） ✅

### WS /ws/evaluation/{evaluation_id}

实时推送评测进度，支持前端实时更新评测状态。

**连接 URL：**
```
ws://localhost:8000/ws/evaluation/{evaluation_id}?token={jwt_token}
```

**认证方式：**
- 通过 URL 参数 `token` 传递 JWT Token
- 或在连接建立后发送认证消息

**消息类型：**

#### 1. 进度更新（progress）

```json
{
    "type": "progress",
    "evaluation_id": "eval-20250601-abc123",
    "current_phase": "DYNAMIC",
    "progress": 45.5,
    "stage": "running",
    "message": "正在执行动态评估任务 36/80",
    "timestamp": "2025-06-01T14:20:00Z"
}
```

#### 2. 状态变更（status_change）

```json
{
    "type": "status_change",
    "evaluation_id": "eval-20250601-abc123",
    "status": "completed",
    "result": {
        "overall_score": 87.5,
        "overall_rating": "A"
    },
    "timestamp": "2025-06-01T18:00:00Z"
}
```

#### 3. 任务完成（task_completed）

```json
{
    "type": "task_completed",
    "evaluation_id": "eval-20250601-abc123",
    "task_id": "task-001",
    "dimension": "accuracy",
    "score": 88.5,
    "timestamp": "2025-06-01T14:15:00Z"
}
```

#### 4. 错误通知（error）

```json
{
    "type": "error",
    "evaluation_id": "eval-20250601-abc123",
    "error": "MCP 服务连接超时",
    "timestamp": "2025-06-01T14:10:00Z"
}
```

**心跳机制：**
- 服务端每 30 秒发送 `{"type": "ping"}` 消息
- 客户端应回复 `{"type": "pong"}`
- 超过 60 秒无响应将断开连接

## 10. 限流规则 ✅

基于滑动窗口的请求限流，默认配置：

| 参数 | 值 | 说明 |
|------|------|------|
| max_requests | 100 | 时间窗口内最大请求数 |
| window_seconds | 60 | 时间窗口（秒） |
| burst_size | 10 | 突发请求数 |

限流键支持按 IP、用户 ID 或端点设置。超限返回 `429 Too Many Requests`，响应头包含 `Retry-After`。

## 11. 错误码

| 错误码 | HTTP 状态码 | 说明 |
|--------|-------------|------|
| EVAL_UNKNOWN | 500 | 未知评测错误 |
| EVAL_TIMEOUT | 408 | 任务执行超时 |
| EVAL_NOT_FOUND | 404 | 评测任务不存在 |
| AGENT_ERROR | 500 | Agent 执行错误 |
| TOOL_ERROR | 500 | 工具调用失败 |
| ENV_ERROR | 500 | 环境错误 |
| MCP_CONNECTION_ERROR | 502 | MCP 连接失败 |
| DB_ERROR | 500 | 数据库错误 |
| VALIDATION_ERROR | 400 | 数据验证失败 |
| SCORING_ERROR | 500 | 评分错误 |
| LLM_JUDGE_ERROR | 500 | LLM Judge 评分错误 |
| COMPARISON_ERROR | 500 | 对比评测错误 |
| BENCHMARK_ERROR | 500 | 基准对比错误 |
| COMPLIANCE_ERROR | 500 | 合规检查错误 |

**错误响应格式：**
```json
{
    "error": "VALIDATION_ERROR",
    "message": "Validation error: agent_id - Agent ID已存在",
    "details": {"field": "agent_id", "reason": "Agent ID已存在"},
    "timestamp": "2026-05-08T10:00:00"
}
```

## 12. 健康检查端点 ✅

### GET /health

基础健康检查，无需认证。

**响应：**
```json
{
    "status": "healthy",
    "version": "1.0.0",
    "timestamp": "2025-06-01T10:00:00Z"
}
```

### GET /ready

就绪检查，包含数据库和 Redis 连接检测。

**响应：**
```json
{
    "status": "ready",
    "checks": {
        "database": "ok",
        "redis": "ok"
    },
    "timestamp": "2025-06-01T10:00:00Z"
}
```

### GET /live

存活检查，仅确认进程存活。

**响应：**
```json
{
    "status": "alive"
}
```

### GET /metrics

Prometheus 指标端点，无需认证。

## 13. 系统信息 🔧

> ⚠️ 当前版本返回简化字段（name, version, endpoints），完整功能列表（features, datasets等）为规划目标。

### GET /api/v1/info

获取系统版本和支持的功能列表。

**响应：**
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
        "websocket_progress": true,
        "agent_comparison": true,
        "industry_benchmark": true,
        "compliance_report": true,
        "improvement_suggestions": true,
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
