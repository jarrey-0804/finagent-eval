# 常见问题 FAQ

> 本文档汇总了 FinAgent-Eval 使用过程中的常见问题及解决方案。

---

## 安装与配置

### Q: Python 版本要求是什么？

A: FinAgent-Eval 要求 Python >= 3.10。推荐使用 Python 3.11 或 3.12 以获得最佳性能。

```bash
# 检查 Python 版本
python --version

# 推荐使用 pyenv 管理多版本 Python
pyenv install 3.11
pyenv local 3.11
```

### Q: 如何配置多个 LLM API Key？

A: 在 `.env` 文件或环境变量中配置：

```bash
# .env 文件
OPENAI_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-ant-xxx
DEEPSEEK_API_KEY=sk-xxx

# 或通过环境变量
export OPENAI_API_KEY=sk-xxx
export ANTHROPIC_API_KEY=sk-ant-xxx
```

也可以在 `config.yaml` 中配置：

```yaml
llm:
  openai_api_key: "sk-xxx"
  anthropic_api_key: "sk-ant-xxx"
  deepseek_api_key: "sk-xxx"
```

### Q: Docker 部署端口冲突怎么办？

A: 修改 `docker-compose.yml` 中的端口映射：

```yaml
services:
  api:
    ports:
      - "8001:8000"  # 将 8000 改为 8001
  grafana:
    ports:
      - "3001:3000"  # 将 3000 改为 3001
```

### Q: 如何在无网络环境部署？

A: 使用离线 Docker 镜像：

```bash
# 在有网络环境导出镜像
docker save finagent-eval:1.0.0 -o finagent-eval.tar

# 在无网络环境导入镜像
docker load -i finagent-eval.tar
```

---

## 评测相关

### Q: 快速评测和完整评测的区别？

A:

| 特性 | 快速评测 (Quick) | 完整评测 (Full) |
|------|-----------------|-----------------|
| 执行阶段 | 仅 STATIC | STATIC → DYNAMIC → TRUST |
| 评测维度 | 5 个核心维度 | 全部 11 个维度 |
| 任务数量 | ~20 | ~80-100 |
| 预计耗时 | ~4 小时 | ~12 小时 |
| 对抗性测试 | 无 | 四级对抗测试 |
| 一票否决 | 无 | 有 |
| 适用场景 | 日常迭代验证 | 发布前全面评估 |

### Q: 评测任务可以暂停吗？

A: 可以。使用取消评测 API 暂停任务，系统会自动保存检查点：

```bash
curl -X POST "http://localhost:8000/api/v1/evaluation/{eval_id}/cancel"
```

### Q: 如何从断点恢复评测？

A: 使用恢复 API 从检查点继续：

```bash
curl -X POST "http://localhost:8000/api/v1/evaluation/{eval_id}/resume"
```

系统会自动跳过已完成的阶段和任务。

### Q: 一票否决机制是什么？

A: 当以下任一条件触发时，评测直接评为 D 级（不合格）：

- 合规性 (compliance) 得分 < 30
- 安全性 (security) 得分 < 30
- 检测到 PII 泄露
- 金融数据幻觉率 > 20%

### Q: 如何解读评测结果？

A: 评测报告包含：

1. **总体评分** - 0-100 分，综合所有维度
2. **评级** - S/A/B/C/D 五级
3. **维度得分** - 各评测维度的详细得分
4. **对抗性测试结果** - 四级对抗测试通过情况
5. **改进建议** - 针对性的优化建议

评级标准：
- S (95-100): 卓越，可直接投入生产
- A (85-94): 优秀，满足大部分生产要求
- B (70-84): 良好，部分维度需改进
- C (60-69): 合格，存在明显短板
- D (<60): 不合格，不建议上线

---

## Agent 接入

### Q: 如何接入自定义 Agent？

A: 参考 [适配器开发指南](adapter_guide.md)，实现 `FinancialAgentInterface` 接口：

```python
from finagent.interface.base import FinancialAgentInterface

class MyAdapter(FinancialAgentInterface):
    def get_config(self) -> AgentConfig: ...
    async def ainvoke(self, task: EvalTask) -> EvalResponse: ...
    async def abatch(self, tasks: list[EvalTask]) -> list[EvalResponse]: ...
    # ... 实现其他方法
```

### Q: 支持哪些 Agent 框架？

A: 内置支持以下框架：

| 框架 | 适配器 | 说明 |
|------|--------|------|
| LangGraph | `LangGraphAdapter` | 推荐，支持 Checkpointer |
| AutoGen | `AutoGenAdapter` | Microsoft 多 Agent 框架 |
| CrewAI | `CrewAIAdapter` | 多角色协作框架 |
| HTTP API | `HTTPAdapter` | 通用 REST API 适配 |

### Q: HTTP 适配器的 API 格式要求？

A: Agent 需实现以下端点：

**POST /evaluate** - 执行评测任务

请求：
```json
{
    "task_id": "task-001",
    "task_type": "knowledge_qa",
    "dimension": "accuracy",
    "input_data": {"question": "..."},
    "time_limit_seconds": 300
}
```

响应：
```json
{
    "task_id": "task-001",
    "output": "Agent 的回答...",
    "tool_calls": [...],
    "metadata": {"elapsed_time": 1.5}
}
```

### Q: 如何注册自定义适配器？

A: 通过代码注册或 Entry Points：

```python
# 代码注册
from finagent.adapter.registry import AdapterRegistry
AdapterRegistry.register("my_framework", MyAdapter)

# Entry Points (pyproject.toml)
[project.entry-points."finagent.adapters"]
my_framework = "my_package.adapter:MyAdapter"
```

---

## 报告与结果

### Q: 如何导出评测报告？

A: 支持多种格式导出：

```bash
# JSON 格式
curl -X POST "http://localhost:8000/api/v1/reports/generate" \
  -d '{"eval_id": "xxx", "format": "json"}'

# Markdown 格式
curl -X POST "http://localhost:8000/api/v1/reports/generate" \
  -d '{"eval_id": "xxx", "format": "markdown"}'

# HTML 格式
curl -X POST "http://localhost:8000/api/v1/reports/generate" \
  -d '{"eval_id": "xxx", "format": "html"}'
```

### Q: 评分标准是什么？

A: 采用 4+7 双层评测体系：

**能力维度（权重 60%）：**
- 准确性 (15%) - 事实准确性
- 完整性 (10%) - 回答覆盖度
- 推理能力 (15%) - 逻辑推理
- 工具使用 (10%) - 工具调用正确性
- 专业性 (10%) - 专业程度

**可信度维度（权重 40%）：**
- 合规性 (10%) - 监管合规
- 风险意识 (8%) - 风险识别
- 鲁棒性 (7%) - 异常处理
- 安全性 (5%) - 安全防护
- 透明度 (5%) - 可解释性
- 一致性 (5%) - 逻辑自洽

---

## 故障排查

### Q: 评测任务一直 pending？

A: 可能原因及解决方案：

1. **Agent 端点不可达** - 检查网络连通性
   ```bash
   curl http://your-agent:8001/health
   ```

2. **数据库连接失败** - 检查数据库状态
   ```bash
   docker-compose logs db
   ```

3. **任务队列阻塞** - 检查 Redis 状态
   ```bash
   redis-cli ping
   ```

### Q: MCP 服务连接失败？

A: 检查步骤：

1. 确认 MCP 服务器运行状态
   ```bash
   curl http://localhost:8080/health
   ```

2. 检查配置文件 `mcp_servers/*/config.json`

3. 查看 MCP 管理器日志
   ```bash
   docker-compose logs api | grep MCP
   ```

### Q: WebSocket 连接断开？

A: 实现自动重连机制：

```javascript
class EvaluationWebSocket {
  constructor(evalId, token) {
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.connect(evalId, token);
  }

  connect(evalId, token) {
    const ws = new WebSocket(`ws://localhost:8000/ws/evaluation/${evalId}?token=${token}`);
    
    ws.onclose = () => {
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        this.reconnectAttempts++;
        setTimeout(() => this.connect(evalId, token), 
          Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000));
      }
    };
  }
}
```

### Q: API 响应超时？

A: 检查响应时间监控：

```bash
# 查看 Prometheus 指标
curl http://localhost:8000/metrics | grep response_time

# 检查 P95 延迟
# 正常应 < 500ms
```

可能原因：
- 数据库查询慢 - 检查索引
- LLM API 延迟 - 检查网络和 API 配额
- 并发过高 - 调整 `max_concurrent_tasks`

### Q: 测试失败如何调试？

A: 查看详细日志：

```bash
# 启用调试日志
export LOG_LEVEL=DEBUG

# 查看评测日志
docker-compose logs api | grep eval_id

# 查看任务执行详情
curl "http://localhost:8000/api/v1/evaluation/{eval_id}/tasks"
```

---

## 性能与扩展

### Q: 如何提升评测速度？

A: 优化建议：

1. **增加并发数**
   ```yaml
   evaluation:
     max_concurrent_tasks: 10  # 默认 5
   ```

2. **使用 Redis 分布式调度**
   ```bash
   docker-compose up -d --scale api=3
   ```

3. **选择快速评测模式**
   ```bash
   finagent-eval eval --mode quick
   ```

### Q: 支持多少并发评测？

A: 单实例默认支持 5 个并发任务。通过 Redis 分布式调度可水平扩展：

```bash
# 启动 3 个 API 实例
docker-compose up -d --scale api=3

# 总并发能力 = 实例数 × 单实例并发数
# 3 × 5 = 15 个并发任务
```

### Q: 数据库存储容量需求？

A: 估算公式：

```
存储需求 = 评测数 × 任务数 × 任务数据大小
        ≈ 1000 × 100 × 10KB
        ≈ 1GB
```

建议：
- 定期清理历史评测数据
- 配置数据保留策略
- 使用 TimescaleDB 处理时序数据

---

## 更多帮助

如果以上 FAQ 未能解决您的问题，请：

1. 查阅 [完整文档](README.md)
2. 提交 [GitHub Issue](https://github.com/finagent/finagent-eval/issues)
3. 加入 [社区讨论](https://github.com/finagent/finagent-eval/discussions)
