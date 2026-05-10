# 行业基准对比

> 本文档介绍如何使用行业基准对比功能，了解您的 Agent 在行业中的位置。

---

## 1. 功能概述

行业基准对比功能允许您：

- 将评测结果与行业平均对比
- 与头部表现对比
- 查看百分位排名
- 获取改进建议

### 基准数据来源

- 匿名化的评测数据聚合
- 行业调研数据
- 公开基准测试结果

---

## 2. 使用方法

### 2.1 Web 界面操作

1. 打开「行业基准」页面
2. 选择已完成的评测
3. 选择基准类型：
   - 行业平均
   - 头部表现（Top 10%）
4. 选择业务分段（可选）
5. 点击「开始对比」

### 2.2 API 调用

```bash
curl -X POST "http://localhost:8000/api/v1/benchmark" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "evaluation_id": "eval-20250601-abc123",
    "benchmark_type": "industry_average",
    "segments": ["fund_analysis", "investment_advice", "risk_assessment"]
  }'
```

### 2.3 Python SDK

```python
from finagent import BenchmarkComparison

# 创建基准对比
comparison = BenchmarkComparison(
    evaluation_id="eval-20250601-abc123",
    benchmark_type="industry_average"
)

# 执行对比
result = await comparison.run()

# 查看结果
print(f"您的评分: {result.your_score}")
print(f"行业平均: {result.benchmark_score}")
print(f"百分位排名: {result.percentile}%")
```

---

## 3. 结果解读

### 3.1 对比报告结构

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
  ]
}
```

### 3.2 百分位排名

百分位排名表示您的 Agent 超过了行业中多少比例的 Agent：

- **90%+**: 头部表现，行业领先
- **70-90%**: 高于平均，表现良好
- **50-70%**: 接近平均，有提升空间
- **<50%**: 低于平均，需要改进

### 3.3 状态说明

| 状态 | 说明 |
|------|------|
| above_average | 高于行业平均 |
| at_average | 接近行业平均 |
| below_average | 低于行业平均 |

---

## 4. 业务分段对比

### 4.1 可用分段

| 分段 | 说明 |
|------|------|
| fund_analysis | 基金分析场景 |
| investment_advice | 投资建议场景 |
| risk_assessment | 风险评估场景 |
| market_research | 市场研究场景 |
| customer_service | 客户服务场景 |

### 4.2 分段对比价值

- 识别 Agent 在特定场景的优劣势
- 针对性优化改进
- 场景化部署决策

---

## 5. 注意事项

- 基准数据定期更新（每季度）
- 对比结果仅供参考
- 样本量较小时，基准可能不够准确
- 不同业务场景的基准可能存在差异
