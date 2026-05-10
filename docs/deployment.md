# 部署指南

> FinAgent-Eval 生产环境部署

## 1. Docker 部署

### 1.1 构建镜像

```bash
docker build -t finagent-eval:1.0.0 .
```

镜像基于 `python:3.11-slim`，安装全部依赖，使用非 root 用户运行，内置健康检查。

### 1.2 docker-compose 一键部署

```bash
# 启动全部服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f api
```

服务组成：

| 服务 | 镜像 | 端口 | 说明 |
|------|------|------|------|
| api | finagent-eval | 8000 | API 服务 |
| db | postgres:16-alpine | 5432 | PostgreSQL 数据库 |
| redis | redis:7-alpine | 6379 | Redis 分布式任务调度与缓存 |
| prometheus | prom/prometheus | 9090 | 指标采集 |
| grafana | grafana/grafana | 3000 | 可视化面板 |

## 2. PostgreSQL 配置

默认连接信息：

```yaml
host: localhost
port: 5432
database: finagent_eval
user: postgres
password: postgres
```

通过环境变量 `DATABASE_URL` 覆盖：

```bash
DATABASE_URL=postgresql://user:pass@host:5432/finagent_eval
```

连接池默认配置：`pool_size=10`，`max_overflow=20`。

## 3. 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| DATABASE_URL | 数据库连接 URL | postgresql://localhost:5432/finagent_eval |
| REDIS_URL | Redis 连接 URL | redis://localhost:6379/0 |
| OPENAI_API_KEY | OpenAI API 密钥 | 无 |
| ANTHROPIC_API_KEY | Anthropic API 密钥 | 无 |
| DEEPSEEK_API_KEY | DeepSeek API 密钥 | 无 |
| RESPONSE_TIMEOUT_MS | API 响应超时时间（毫秒） | 30000 |
| P95_THRESHOLD_MS | P95 响应时间告警阈值（毫秒） | 500 |

在 docker-compose 中通过 `.env` 文件或 `environment` 字段配置。

## 4. CI/CD 流水线

建议的 CI/CD 配置要点：

1. **测试阶段：** 运行 `pytest` 单元测试和集成测试
2. **代码质量：** 使用 `black`、`isort`、`ruff`、`mypy` 检查
3. **构建阶段：** `docker build` 构建镜像
4. **部署阶段：** 推送镜像到仓库，更新 docker-compose

```bash
# 本地运行完整检查
pip install -e ".[dev]"
pytest tests/
black --check src/
isort --check-only src/
ruff check src/
mypy src/
```

## 5. 监控配置

### 5.1 Prometheus

配置文件路径：`config/prometheus.yml`。Prometheus 采集 API 服务的 `/metrics` 端点。

### 5.2 Grafana

访问 `http://localhost:3000`，默认管理员密码 `admin`。数据源配置指向 Prometheus，面板配置位于 `config/grafana/` 目录。

### 5.3 健康检查

API 服务内置三个健康检查端点：

| 端点 | 说明 | 适用场景 |
|------|------|----------|
| `GET /health` | 基础健康检查 | 通用健康探针 |
| `GET /ready` | 就绪检查（含数据库与 Redis 连接检测） | Kubernetes readinessProbe |
| `GET /live` | 存活检查（仅确认进程存活） | Kubernetes livenessProbe |

Docker 默认每 30 秒检查一次（超时 10 秒，启动等待 5 秒，重试 3 次）。

## 6. 响应时间中间件配置

系统内置响应时间监控中间件，通过以下环境变量进行配置：

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `RESPONSE_TIMEOUT_MS` | 单次请求最大允许响应时间（毫秒） | 30000 |
| `P95_THRESHOLD_MS` | P95 响应时间告警阈值（毫秒），超过此值将记录告警日志 | 500 |

配置示例：

```bash
# .env 文件
RESPONSE_TIMEOUT_MS=30000
P95_THRESHOLD_MS=500
```

中间件会自动记录每个 API 端点的响应时间指标，并通过 Prometheus `/metrics` 端点暴露。可在 Grafana 中配置面板查看各端点的 P50/P95/P99 延迟趋势。

## 7. 三阶段评估流水线配置

系统支持三阶段评估流水线（STATIC -> DYNAMIC -> TRUST），可通过 API 请求参数启用。

### 7.1 启用三阶段流水线

在启动评测时设置 `enable_three_stage: true`：

```bash
curl -X POST "http://localhost:8000/api/v1/evaluation/start" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "my-agent",
    "eval_mode": "full",
    "enable_three_stage": true
  }'
```

### 7.2 阶段说明

| 阶段 | 说明 | 预计耗时 |
|------|------|----------|
| STATIC | 静态分析阶段，检查 Agent 配置、接口定义、安全策略等 | 约 30 分钟 |
| DYNAMIC | 动态执行阶段，运行实际评测任务并收集结果 | 约 8-10 小时 |
| TRUST | 可信度评估阶段，基于动态结果进行可信度维度评分 | 约 1-2 小时 |

### 7.3 阶段监控

通过查询评测状态可查看当前阶段与各阶段进度：

```bash
curl -X GET "http://localhost:8000/api/v1/evaluation/<eval_id>" \
  -H "Authorization: Bearer <token>"
```

响应中的 `current_phase` 字段指示当前阶段，`phase_progress` 字段显示各阶段完成状态。

## 8. 分布式调度器配置

系统使用基于 Redis 的分布式任务调度器，支持多实例水平扩展。

### 8.1 Redis 要求

- **版本：** Redis 7.0+
- **内存：** 建议至少 512MB（大规模评测场景建议 1GB+）
- **持久化：** 建议开启 AOF 持久化，避免重启后任务状态丢失
- **网络：** 调度器与 Redis 之间的网络延迟应低于 5ms

### 8.2 配置

通过 `REDIS_URL` 环境变量指定 Redis 连接：

```bash
# .env 文件
REDIS_URL=redis://localhost:6379/0

# 带密码的 Redis
REDIS_URL=redis://:your_password@redis-host:6379/0

# Redis Sentinel（高可用）
REDIS_URL=redis://sentinel-host:26379/0?sentinel=mymaster
```

### 8.3 多实例部署

在 docker-compose 中扩展 API 服务实例以实现水平扩展：

```bash
# 启动 3 个 API 实例
docker-compose up -d --scale api=3
```

多个 API 实例通过 Redis 共享任务队列，自动实现负载均衡。每个实例启动时会自动注册到调度器，实例下线后未完成的任务会被其他实例接管。

### 8.4 监控

分布式调度器的运行指标通过 Prometheus 暴露，包括：

- 任务队列长度
- 任务分发速率
- 各实例负载情况
- 任务失败与重试次数
