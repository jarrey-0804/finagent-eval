# 运维手册

> 本文档提供 FinAgent-Eval 生产环境的运维指南。

---

## 1. 部署架构

### 1.1 单机部署

适用于开发测试和小规模使用：

```
┌─────────────────────────────────────────────────────────────────┐
│                        单机部署                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Docker Compose                        │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐       │   │
│  │  │   API   │ │   DB    │ │  Redis  │ │ Grafana │       │   │
│  │  │  :8000  │ │  :5432  │ │  :6379  │ │  :3000  │       │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘       │   │
│  │  ┌─────────┐                                           │   │
│  │  │Prometheus│                                          │   │
│  │  │  :9090  │                                           │   │
│  │  └─────────┘                                           │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 分布式部署

适用于大规模生产环境：

```
┌─────────────────────────────────────────────────────────────────┐
│                        分布式部署                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐     ┌─────────────────────────────────────┐   │
│  │ 负载均衡器   │────▶│           API 集群                  │   │
│  │   (Nginx)   │     │  ┌─────┐ ┌─────┐ ┌─────┐           │   │
│  └─────────────┘     │  │API 1│ │API 2│ │API 3│ ...       │   │
│                      │  └─────┘ └─────┘ └─────┘           │   │
│                      └─────────────────────────────────────┘   │
│                                    │                            │
│                      ┌─────────────┴─────────────┐             │
│                      ▼                           ▼             │
│              ┌─────────────┐            ┌─────────────┐        │
│              │ PostgreSQL  │            │    Redis    │        │
│              │   主从复制   │            │   Sentinel  │        │
│              └─────────────┘            └─────────────┘        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 高可用方案

**数据库高可用：**

- PostgreSQL 主从复制 + 自动故障转移
- 使用 Patroni 或 repmgr 管理

**Redis 高可用：**

- Redis Sentinel 模式
- 3 个 Sentinel 节点 + 1 主 2 从

**API 高可用：**

- 多实例部署 + 负载均衡
- 健康检查自动摘除故障节点

---

## 2. 配置管理

### 2.1 环境变量

| 变量名 | 说明 | 默认值 | 必填 |
|--------|------|--------|------|
| DATABASE_URL | 数据库连接 URL | - | 是 |
| REDIS_URL | Redis 连接 URL | redis://localhost:6379/0 | 否 |
| OPENAI_API_KEY | OpenAI API 密钥 | - | 是 |
| ANTHROPIC_API_KEY | Anthropic API 密钥 | - | 否 |
| DEEPSEEK_API_KEY | DeepSeek API 密钥 | - | 否 |
| JWT_SECRET_KEY | JWT 签名密钥 | - | 是 |
| API_WORKERS | API Worker 数量 | 4 | 否 |
| RESPONSE_TIMEOUT_MS | API 响应超时 | 30000 | 否 |
| P95_THRESHOLD_MS | P95 延迟阈值 | 500 | 否 |
| LOG_LEVEL | 日志级别 | INFO | 否 |

### 2.2 配置文件

**config/config.yaml:**

```yaml
database:
  url: "${DATABASE_URL}"
  pool_size: 10
  max_overflow: 20
  pool_timeout: 30

redis:
  url: "${REDIS_URL}"
  max_connections: 50

llm:
  openai_api_key: "${OPENAI_API_KEY}"
  anthropic_api_key: "${ANTHROPIC_API_KEY}"
  deepseek_api_key: "${DEEPSEEK_API_KEY}"
  default_model: "gpt-4o"
  temperature: 0.1
  max_tokens: 2048

evaluation:
  default_mode: "full"
  max_concurrent_tasks: 5
  task_timeout: 300
  pass_threshold: 60.0
  veto_threshold: 30.0
  three_stage:
    enabled: true
    phases:
      static:
        enabled: true
        task_count: 50
      dynamic:
        enabled: true
        task_count: 30
      trust:
        enabled: true
        task_count: 20

api:
  host: "0.0.0.0"
  port: 8000
  workers: 4
  cors_origins: ["*"]

logging:
  level: "${LOG_LEVEL}"
  format: "json"
  file: "/var/log/finagent/app.log"
```

### 2.3 敏感信息管理

**推荐方案：**

1. **Kubernetes Secrets**
   ```yaml
   apiVersion: v1
   kind: Secret
   metadata:
     name: finagent-secrets
   type: Opaque
   stringData:
     DATABASE_URL: "postgresql://..."
     OPENAI_API_KEY: "sk-xxx"
   ```

2. **HashiCorp Vault**
   ```bash
   vault kv put secret/finagent \
     DATABASE_URL="postgresql://..." \
     OPENAI_API_KEY="sk-xxx"
   ```

3. **AWS Secrets Manager / Azure Key Vault**

---

## 3. 监控告警

### 3.1 Prometheus 指标

**关键指标：**

```yaml
# 评测指标
- finagent_evaluations_total
- finagent_evaluations_active
- finagent_evaluation_duration_seconds
- finagent_evaluation_score

# API 指标
- finagent_api_requests_total
- finagent_api_response_time_seconds
- finagent_api_errors_total

# 系统指标
- finagent_workers_active
- finagent_tasks_pending
- finagent_tasks_completed
```

### 3.2 Grafana 面板

**预置面板：**

| 面板 | 文件 | 说明 |
|------|------|------|
| 评测总览 | evaluation_overview.json | 评测数量、通过率、耗时分布 |
| LLM Judge | llm_judge.json | 多模型评分一致性、共识率 |
| MCP 服务器 | mcp_servers.json | 工具调用成功率、响应延迟 |
| 资源使用 | resource_usage.json | CPU、内存、数据库连接池 |

### 3.3 AlertManager 规则

**config/alertmanager/alert_rules.yml:**

```yaml
groups:
  - name: finagent-alerts
    rules:
      # API 响应时间告警
      - alert: HighAPILatency
        expr: histogram_quantile(0.95, rate(finagent_api_response_time_seconds_bucket[5m])) > 0.5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "API P95 响应时间超过 500ms"
          description: "当前 P95: {{ $value }}s"

      # 评测失败率告警
      - alert: HighEvaluationFailureRate
        expr: rate(finagent_evaluations_total{status="failed"}[1h]) / rate(finagent_evaluations_total[1h]) > 0.1
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: "评测失败率超过 10%"

      # Worker 数量告警
      - alert: NoActiveWorkers
        expr: finagent_workers_active == 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "没有活跃的 Worker"

      # 数据库连接池告警
      - alert: DatabaseConnectionPoolExhausted
        expr: finagent_db_connections_active / finagent_db_connections_max > 0.9
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "数据库连接池使用率超过 90%"
```

---

## 4. 日志管理

### 4.1 日志格式

**JSON 格式日志：**

```json
{
  "timestamp": "2025-06-01T10:00:00Z",
  "level": "INFO",
  "logger": "finagent.pipeline",
  "message": "Evaluation started",
  "evaluation_id": "eval-xxx",
  "agent_id": "agent-001",
  "eval_mode": "full",
  "request_id": "req-xxx"
}
```

### 4.2 日志收集

**推荐方案：**

1. **ELK Stack (Elasticsearch + Logstash + Kibana)**
2. **Loki + Grafana**
3. **Fluentd / Fluent Bit**

### 4.3 日志分析

**常用查询：**

```bash
# 查看错误日志
docker-compose logs api | grep ERROR

# 查看特定评测日志
docker-compose logs api | grep "evaluation_id=eval-xxx"

# 查看慢请求
docker-compose logs api | grep "response_time" | awk '$NF > 1000'
```

---

## 5. 备份恢复

### 5.1 数据库备份

**自动备份脚本：**

```bash
#!/bin/bash
# backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backup/postgresql"
DAYS_TO_KEEP=7

# 创建备份目录
mkdir -p $BACKUP_DIR

# 执行备份
pg_dump -h localhost -U postgres finagent_eval | gzip > $BACKUP_DIR/finagent_eval_$DATE.sql.gz

# 清理旧备份
find $BACKUP_DIR -name "*.sql.gz" -mtime +$DAYS_TO_KEEP -delete

echo "Backup completed: finagent_eval_$DATE.sql.gz"
```

**定时任务 (crontab):**

```bash
# 每天凌晨 2 点备份
0 2 * * * /opt/finagent/scripts/backup.sh >> /var/log/finagent/backup.log 2>&1
```

### 5.2 配置备份

```bash
# 备份配置文件
tar -czvf config_backup_$DATE.tar.gz \
  config/ \
  .env \
  docker-compose.yml
```

### 5.3 灾难恢复

**恢复步骤：**

```bash
# 1. 停止服务
docker-compose down

# 2. 恢复数据库
gunzip -c finagent_eval_20250601.sql.gz | psql -h localhost -U postgres finagent_eval

# 3. 恢复配置
tar -xzvf config_backup_20250601.tar.gz

# 4. 启动服务
docker-compose up -d

# 5. 验证服务
curl http://localhost:8000/health
```

---

## 6. 故障排查

### 6.1 常见问题

| 问题 | 诊断命令 | 解决方案 |
|------|----------|----------|
| API 无响应 | `curl http://localhost:8000/health` | 检查容器状态、重启服务 |
| 数据库连接失败 | `docker-compose logs db` | 检查数据库状态、连接配置 |
| Redis 连接失败 | `redis-cli ping` | 检查 Redis 状态、重启服务 |
| 评测任务卡住 | 查看任务队列 | 清理僵尸任务、重启 Worker |
| 内存不足 | `docker stats` | 调整资源限制、扩展实例 |

### 6.2 诊断命令

```bash
# 查看服务状态
docker-compose ps

# 查看资源使用
docker stats

# 查看日志
docker-compose logs -f api

# 进入容器调试
docker-compose exec api bash

# 检查数据库连接
docker-compose exec db psql -U postgres -c "SELECT 1"

# 检查 Redis 连接
docker-compose exec redis redis-cli ping

# 查看任务队列
docker-compose exec redis redis-cli LLEN task:queue:normal
```

### 6.3 应急处理

**服务重启：**

```bash
# 优雅重启 API
docker-compose restart api

# 完全重建
docker-compose down && docker-compose up -d
```

**清理僵尸任务：**

```bash
# 连接 Redis
redis-cli

# 查看任务队列
LRANGE task:queue:normal 0 -1

# 清理队列
DEL task:queue:normal
```

**数据库恢复：**

```bash
# 检查数据库状态
pg_isready -h localhost

# 重建连接池
docker-compose restart api
```

---

## 7. 性能调优

### 7.1 数据库优化

```sql
-- 创建索引
CREATE INDEX idx_evaluations_agent_id ON evaluations(agent_id);
CREATE INDEX idx_evaluations_status ON evaluations(status);
CREATE INDEX idx_tasks_evaluation_id ON tasks(evaluation_id);

-- 分析查询性能
EXPLAIN ANALYZE SELECT * FROM evaluations WHERE agent_id = 'xxx';
```

### 7.2 缓存优化

```yaml
# Redis 配置优化
redis:
  maxmemory: 1gb
  maxmemory-policy: allkeys-lru
  timeout: 300
```

### 7.3 并发配置

```yaml
# API Worker 配置
api:
  workers: 4  # CPU 核心数

# 评测并发配置
evaluation:
  max_concurrent_tasks: 10  # 根据内存调整

# 数据库连接池
database:
  pool_size: 20
  max_overflow: 40
```

---

## 8. 安全加固

### 8.1 网络安全

```yaml
# docker-compose.yml
services:
  api:
    networks:
      - frontend
      - backend
  
  db:
    networks:
      - backend  # 仅内部网络

networks:
  frontend:
  backend:
    internal: true  # 内部网络，不暴露外部
```

### 8.2 访问控制

```yaml
# API 限流配置
api:
  rate_limit:
    enabled: true
    max_requests: 100
    window_seconds: 60
```

### 8.3 安全检查清单

- [ ] 更改默认密码
- [ ] 启用 HTTPS
- [ ] 配置防火墙规则
- [ ] 启用 API 认证
- [ ] 配置 CORS 白名单
- [ ] 定期更新依赖
- [ ] 启用审计日志
