# Agent 对比评测

> 本文档介绍如何使用 Agent 对比评测功能，同时评测多个 Agent 并生成对比报告。

---

## 1. 功能概述

Agent 对比评测功能允许您：

- 同时评测多个 Agent（最多 5 个）
- 使用相同的评测任务和标准
- 生成对比报告和排名
- 快速识别最优 Agent

### 适用场景

- Agent 版本选型
- 多模型对比
- 框架迁移评估
- 竞品分析

---

## 2. 使用方法

### 2.1 Web 界面操作

1. 打开「Agent 对比」页面
2. 选择要对比的 Agent（勾选最多 5 个）
3. 选择评测模式：
   - 快速评测（推荐）
   - 完整评测
4. 选择评测维度（可选）
5. 点击「开始对比」

### 2.2 API 调用

```bash
curl -X POST "http://localhost:8000/api/v1/evaluation/compare" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_ids": ["agent-001", "agent-002", "agent-003"],
    "eval_mode": "quick",
    "dimensions": ["accuracy", "completeness", "reasoning", "compliance"],
    "datasets": ["bizfinbench"]
  }'
```

### 2.3 Python SDK

```python
from finagent import ComparisonPipeline

# 创建对比评测
pipeline = ComparisonPipeline(
    agent_ids=["agent-001", "agent-002", "agent-003"],
    eval_mode="quick",
    dimensions=["accuracy", "completeness", "reasoning", "compliance"]
)

# 执行对比
result = await pipeline.run()

# 查看排名
for i, agent in enumerate(result.ranking):
    print(f"#{i+1}: {agent['agent_name']} - {agent['overall_score']}分")
```

---

## 3. 结果解读

### 3.1 对比报告结构

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
    }
  ],
  "ranking": ["agent-001", "agent-002", "agent-003"],
  "comparison_summary": {
    "best_in_accuracy": "agent-001",
    "best_in_completeness": "agent-002",
    "best_in_reasoning": "agent-001",
    "best_in_compliance": "agent-001"
  }
}
```

### 3.2 排名依据

排名基于总体评分（overall_score），评分计算方式：

```
overall_score = Σ(dimension_score × dimension_weight)
```

### 3.3 维度最佳

对比报告会标注每个维度的最佳 Agent，帮助识别各维度的优势 Agent。

---

## 4. 最佳实践

### 4.1 选择对比维度

- **版本对比**：使用全部维度
- **模型对比**：重点关注 accuracy、reasoning
- **合规评估**：重点关注 compliance、security

### 4.2 评测模式选择

| 场景 | 推荐模式 |
|------|----------|
| 快速筛选 | 快速评测 |
| 最终选型 | 完整评测 |
| 深度分析 | 完整评测 + 三阶段流水线 |

### 4.3 结果分析建议

1. 关注维度差异，而非仅看总分
2. 结合业务场景选择最优 Agent
3. 考虑 Agent 的稳定性和一致性

---

## 5. 注意事项

- 对比评测会同时启动多个评测任务，资源消耗较大
- 建议在非高峰期执行大规模对比
- 对比结果有效期 7 天，可重新生成
