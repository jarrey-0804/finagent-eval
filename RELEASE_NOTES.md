# FinAgent-Eval v1.0.0 发布说明

**发布日期**: 2026-05-10  
**版本号**: v1.0.0  
**状态**: 正式发布

---

## 概述

FinAgent-Eval 是面向基金金融场景的 AI Agent 自主评测系统，采用三阶段评测流水线（STATIC → DYNAMIC → TRUST）、LLM-as-Judge 多模型交叉验证、四层对抗测试框架等技术方案。

---

## 核心功能

### 评测能力
- **三阶段评估流水线**: STATIC（静态合规）→ DYNAMIC（动态能力）→ TRUST（可信度评估）
- **4+7 双层评测维度**: 4 项能力维度 + 7 项可信度维度
- **LLM-as-Judge 多模型交叉验证**: 支持 GPT-4o、Claude-3-Opus、DeepSeek-V3
- **四级对抗性测试框架**: 提示注入、越狱攻击、金融场景对抗、语义变异
- **一票否决机制**: 合规/安全红线自动触发

### 系统特性
- **WebSocket 实时评测进度推送**
- **Redis 分布式任务调度器**
- **API 响应时间监控中间件** (P95 < 500ms)
- **断点续跑（Checkpoint/Resume）机制**
- **多框架适配器**: LangGraph、AutoGen、CrewAI、HTTP

### 前端功能
- **React 管理端完整实现**
- **深色模式支持**
- **响应式设计**
- **WebSocket 实时进度展示**

### 监控与运维
- **Prometheus 指标采集**
- **Grafana 可视化面板**
- **健康检查端点**: /health, /ready, /live

---

## 发布包

| 文件 | 大小 | 说明 |
|------|------|------|
| `finagent_eval-1.0.0-py3-none-any.whl` | 172 KB | Python Wheel 包 |
| `finagent_eval-1.0.0.tar.gz` | 148 KB | 源码分发包 |

---

## 质量指标

| 指标 | 数值 | 状态 |
|------|------|------|
| 测试通过率 | 566/567 (99.8%) | ✅ |
| 代码覆盖率 | 60% | ✅ |
| Ruff 代码规范 | 10 个风格建议 | ✅ |
| 前端构建 | 成功 (6.8s) | ✅ |

---

## 安装

```bash
# 使用 pip 安装
pip install finagent-eval==1.0.0

# 或使用 Wheel 包
pip install finagent_eval-1.0.0-py3-none-any.whl
```

---

## 快速开始

```bash
# 启动评测服务
finagent-eval server

# 或使用 Python
python -m finagent server
```

---

## 文档

- [快速入门教程](docs/tutorial.md)
- [API 参考文档](docs/api_reference.md)
- [部署指南](docs/deployment.md)
- [用户手册](docs/user_manual.md)

---

## 兼容性

- **Python**: >= 3.10
- **Node.js**: >= 18 (前端构建)

---

## 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

---

## 致谢

感谢所有参与开发和测试的团队成员！

---

**FinAgent Team**  
Email: finagent@example.com  
GitHub: https://github.com/finagent/finagent-eval
