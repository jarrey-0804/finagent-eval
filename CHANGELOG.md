# 变更日志

本项目的所有重要变更都将记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

---

## [1.0.0] - 2025-05-09

### 新增

#### 核心功能
- 三阶段评估流水线（STATIC → DYNAMIC → TRUST）
- WebSocket 实时评测进度推送
- Agent 对比评测功能
- 行业基准对比功能
- 合规认证报告生成
- 智能改进建议功能
- Redis 分布式任务调度器
- API 响应时间监控中间件（P95 < 500ms）
- 断点续跑（Checkpoint/Resume）机制

#### 前端功能
- React 管理端完整实现
- 深色模式支持
- 响应式设计
- 骨架屏加载状态
- 空状态提示组件
- 错误边界组件
- WebSocket 实时进度展示

#### 评测能力
- 4+7 双层评测维度体系
- LLM-as-Judge 多模型交叉验证
- 四级对抗性测试框架
- 一票否决机制
- 多框架适配器（LangGraph/AutoGen/CrewAI/HTTP）

#### 监控与运维
- Prometheus 指标采集
- Grafana 可视化面板
- AlertManager 告警规则
- 健康检查端点（/health, /ready, /live）
- 代码复杂度 CI 门控

### 改进

- 前端 API 集成与错误处理优化
- 数据库连接池配置优化
- 任务调度性能提升
- 文档结构重组和完善

### 修复

- JavaScript `eval` 保留字冲突问题
- WebSocket 连接稳定性问题
- 多项 UI/UX 问题修复

---

## [0.9.0] - 2025-04-15

### 新增

- 基础评测流水线引擎
- LangGraph 适配器
- AutoGen 适配器
- CrewAI 适配器
- HTTP 适配器
- 基础评分引擎
- 任务生成模块
- 报告生成模块

### 改进

- 评测任务并行执行
- 评分算法优化

---

## [0.8.0] - 2025-03-01

### 新增

- 项目初始化
- 基础项目结构
- CLI 命令行工具
- 配置管理模块
- 日志系统

---

## 版本规划

### [1.1.0] - 计划中

- 自定义评测维度支持
- 更多 LLM Judge 模型支持
- 评测任务模板
- 批量评测优化

### [1.2.0] - 计划中

- 多语言支持（英文文档）
- 插件系统
- 自定义数据集上传
- 评测结果可视化增强

---

[1.0.0]: https://github.com/finagent/finagent-eval/releases/tag/v1.0.0
[0.9.0]: https://github.com/finagent/finagent-eval/releases/tag/v0.9.0
[0.8.0]: https://github.com/finagent/finagent-eval/releases/tag/v0.8.0
