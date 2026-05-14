# FinAgent-Eval 部署指南

## 环境要求

| 组件 | 最低版本 | 推荐版本 |
|------|----------|----------|
| Python | 3.10 | 3.11+ |
| PostgreSQL | 14 | 16 |
| Redis | 7.0 | 7.2+ |
| Node.js | 18 | 20 LTS |

## 快速部署

### 1. 安装

```bash
# 克隆项目
git clone https://github.com/jarrey-0804/finagent-eval.git
cd finagent-eval

# 创建虚拟环境
python -m venv venv
source venv/bin/activate

# 安装核心依赖
pip install -e .

# 安装全部可选依赖
pip install -e ".[all]"
```

### 2. 配置

```bash
# 生成默认配置
finagent-eval config --init

# 编辑配置文件
vim config.yaml
```

关键配置项：

```yaml
database:
  url: "postgresql://user:password@localhost:5432/finagent_eval"
  pool_size: 10

llm:
  openai_api_key: "sk-..."
  default_model: "gpt-4o"
  temperature: 0.1

evaluation:
  default_mode: "full"
  max_concurrent_tasks: 5
  task_timeout: 300
```

### 3. 初始化数据库

```bash
# 创建数据库
createdb finagent_eval

# 运行迁移（如有）
finagent-eval db migrate
```

### 4. 启动服务

```bash
# 开发模式
finagent-eval serve --host 127.0.0.1 --port 8000

# 生产模式（多进程）
finagent-eval serve --host 0.0.0.0 --port 8000 --workers 4
```

## Docker 部署

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install -e ".[all]" --break-system-packages

COPY . .

EXPOSE 8000

CMD ["finagent-eval", "serve", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### Docker Compose

```yaml
version: "3.8"

services:
  finagent-eval:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:5432/finagent_eval
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    depends_on:
      - postgres
      - redis

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: finagent_eval
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./deploy/prometheus:/etc/prometheus

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    volumes:
      - ./deploy/grafana:/etc/grafana

volumes:
  pgdata:
```

## 监控配置

### Prometheus

将以下内容添加到 `prometheus.yml`：

```yaml
scrape_configs:
  - job_name: "finagent-eval"
    static_configs:
      - targets: ["localhost:8000"]
    metrics_path: "/metrics"
    scrape_interval: "30s"
```

数据质量告警规则已预配置在 `deploy/prometheus/alerts/data_quality.yml`。

### Grafana

1. 导入仪表盘：`deploy/grafana/dashboards/finagent-data-quality.json`
2. 配置 Prometheus 数据源
3. 仪表盘包含：综合评分、六维度评分、字段完整率、响应状态分布、趋势图

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DATABASE_URL` | PostgreSQL 连接 URL | `postgresql://localhost:5432/finagent_eval` |
| `REDIS_URL` | Redis 连接 URL | `redis://localhost:6379` |
| `OPENAI_API_KEY` | OpenAI API 密钥 | 无 |
| `ANTHROPIC_API_KEY` | Anthropic API 密钥 | 无 |
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 | 无 |
| `JWT_SECRET` | JWT 签名密钥 | 自动生成 |
| `CORS_ORIGINS` | CORS 允许的源 | `["http://localhost:3000"]` |

## 健康检查

服务启动后，以下端点可用于健康检查：

| 端点 | 说明 |
|------|------|
| `GET /health` | 存活检查（进程是否运行） |
| `GET /ready` | 就绪检查（依赖是否可用） |
| `GET /live` | 启动检查（是否完成初始化） |
| `GET /metrics` | Prometheus 指标 |

## 安全建议

1. **生产环境**：使用 `--host 0.0.0.0` 时确保配置防火墙规则
2. **API 密钥**：通过环境变量传递，不要写入配置文件
3. **HTTPS**：使用 Nginx/Caddy 反向代理并配置 TLS 证书
4. **数据库**：使用强密码并限制网络访问
5. **Redis**：启用 `requirepass` 认证

## 故障排查

| 问题 | 解决方案 |
|------|----------|
| 服务启动失败 | 检查端口是否被占用、数据库/Redis 是否可连接 |
| 评测超时 | 增大 `evaluation.task_timeout` 配置 |
| LLM 调用失败 | 检查 API 密钥、网络代理配置 |
| 内存不足 | 减少 `max_concurrent_tasks` 或增加内存 |
