# FinAgent-Eval v1.0.0 发布说明

**发布日期**: 2026-05-14

---

## 概述

FinAgent-Eval v1.0.0 是首个正式发布版本，提供面向基金金融场景的 AI Agent 标准化评测能力。系统采用 4+7 双层评测维度体系，结合 LLM-as-Judge 多模型交叉验证机制，支持 LangGraph、AutoGen、CrewAI、HTTP API 等主流框架适配。

## 质量指标

| 指标 | 结果 |
|------|------|
| 代码风格 (ruff) | 0 errors |
| 类型检查 (mypy) | 0 errors (77 source files) |
| 安全检查 (bandit) | 0 High, 0 Medium |
| 单元测试 | 733 passed, 1 skipped |
| 测试覆盖率 | 61.77% |
| 代码复杂度 | Avg C (10.2) |

## 快速开始

### 安装

```bash
pip install finagent-eval

# 或安装全部可选依赖
pip install "finagent-eval[all]"
```

### 启动服务

```bash
finagent-eval serve --host 127.0.0.1 --port 8000
```

### 运行评测

```bash
# 快速评测
finagent-eval eval --agent-id my-agent --endpoint http://localhost:8001 --mode quick

# 完整评测
finagent-eval eval --agent-id my-agent --endpoint http://localhost:8001 --mode full
```

### 生成评测任务

```bash
finagent-eval generate --count 20 --output tasks.json --mode full
```

## 核心功能

- **4+7 双层评测维度体系** — 准确性、完整性、推理能力、工具使用 + 专业性、合规性、风险意识等
- **S/A/B/C/D 五级评级** — 量化评分 + 一票否决机制
- **多框架适配** — LangGraph、AutoGen、CrewAI、HTTP API
- **LLM-as-Judge** — GPT-4o、Claude、DeepSeek 多模型交叉验证
- **四级对抗性测试** — baseline → noisy → meta_cognitive → adversarial
- **三阶段流水线** — STATIC → DYNAMIC → TRUST，支持断点续跑
- **数据质量治理** — 验证增强、质量监控、Prometheus 指标、Grafana 面板
- **弹性机制** — 熔断器、指数退避重试、外部数据缓存
- **Redis 分布式调度** — 多实例水平扩展与负载均衡
- **17 个 REST API 端点** — 评测、Agent 管理、任务生成、报告、基准对比、合规认证

## 文档

| 文档 | 说明 |
|------|------|
| [README.md](README.md) | 项目主文档 |
| [CHANGELOG.md](CHANGELOG.md) | 版本变更记录 |
| [docs/architecture.md](docs/architecture.md) | 系统架构 |
| [docs/api_reference.md](docs/api_reference.md) | API 接口文档 |
| [docs/deployment.md](docs/deployment.md) | 部署指南 |
| [docs/adapter_guide.md](docs/adapter_guide.md) | 适配器开发指南 |
| [docs/tutorial.md](docs/tutorial.md) | 使用教程 |
| [docs/faq.md](docs/faq.md) | 常见问题 |

## 升级指南

从 v0.9.0 升级到 v1.0.0：

1. **异常类重命名**: `EvaluationException` → `EvaluationError`，请更新所有引用
2. **EvalTask 属性变更**: `query` → `input_data.get("query")`, `dimensions` → `dimension`
3. **默认绑定地址**: `0.0.0.0` → `127.0.0.1`，生产环境需显式指定 `--host 0.0.0.0`
4. **pyproject.toml**: ruff lint 配置已迁移到 `[tool.ruff.lint]` 区块

## 贡献者

感谢所有为 FinAgent-Eval 做出贡献的开发者。

## 许可证

[MIT License](LICENSE)
