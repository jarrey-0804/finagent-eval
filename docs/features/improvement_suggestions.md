# 智能改进建议

> 本文档介绍如何使用智能改进建议功能，获取针对性的 Agent 优化建议。

---

## 1. 功能概述

智能改进建议功能提供：

- 基于评测结果的智能分析
- 针对性的改进措施建议
- 问题根因诊断
- 快速见效建议

### 建议生成逻辑

1. 分析各维度得分和任务表现
2. 识别薄弱维度和问题模式
3. 匹配改进知识库
4. 生成针对性建议

---

## 2. 使用方法

### 2.1 Web 界面操作

1. 打开「改进建议」页面
2. 选择已完成的评测
3. 选择关注维度（可选）
4. 选择详细程度：
   - 摘要模式
   - 全面模式
5. 点击「获取建议」

### 2.2 API 调用

```bash
curl -X POST "http://localhost:8000/api/v1/improvement/suggestions" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "evaluation_id": "eval-20250601-abc123",
    "focus_areas": ["completeness", "risk_awareness"],
    "detail_level": "comprehensive"
  }'
```

### 2.3 Python SDK

```python
from finagent import ImprovementSuggester

# 创建建议生成器
suggester = ImprovementSuggester(
    evaluation_id="eval-20250601-abc123",
    focus_areas=["completeness", "risk_awareness"],
    detail_level="comprehensive"
)

# 获取建议
suggestions = await suggester.get_suggestions()

# 查看结果
print(f"总体评估: {suggestions.overall_assessment}")
for sug in suggestions.suggestions:
    print(f"\n【{sug.dimension}】")
    print(f"当前: {sug.current_score} → 目标: {sug.target_score}")
    for rec in sug.recommendations:
        print(f"  - {rec.action}")
```

---

## 3. 建议分类

### 3.1 按优先级

| 优先级 | 说明 | 示例 |
|--------|------|------|
| high | 高优先级，建议立即处理 | 合规性问题 |
| medium | 中优先级，建议近期处理 | 性能优化 |
| low | 低优先级，可延后处理 | 体验优化 |

### 3.2 按改进类型

| 类型 | 说明 | 典型措施 |
|------|------|----------|
| prompt | Prompt 优化 | 添加指令、调整格式 |
| tool | 工具优化 | 增加工具、优化调用 |
| knowledge | 知识增强 | 补充知识库、更新数据 |
| architecture | 架构优化 | 调整流程、增加模块 |

---

## 4. 结果解读

### 4.1 建议结构

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
          "implementation": "在 Agent 状态管理中增加信息收集清单机制",
          "type": "architecture"
        },
        {
          "action": "添加标准化风险提示模板",
          "description": "在投资建议类回答末尾添加风险提示",
          "implementation": "配置风险提示模板，在特定场景自动触发",
          "type": "prompt"
        }
      ]
    }
  ],
  "quick_wins": [
    "添加风险提示模板可快速提升合规性 3-5 分",
    "优化回答结构模板可提升完整性 2-3 分"
  ]
}
```

### 4.2 快速见效建议

快速见效建议是指实施成本低、效果明显的改进措施：

- Prompt 模板优化
- 输出格式规范
- 简单规则添加

---

## 5. 实施建议

### 5.1 优先级排序

1. 处理 high 优先级问题
2. 实施 quick_wins 建议
3. 逐步处理 medium/low 优先级

### 5.2 验证改进效果

```bash
# 实施改进后重新评测
curl -X POST "http://localhost:8000/api/v1/evaluation/start" \
  -d '{"agent_id": "my-agent", "eval_mode": "quick"}'

# 对比改进前后分数
# 关注目标维度的分数变化
```

### 5.3 持续迭代

- 定期获取改进建议
- 跟踪改进效果
- 调整优化策略

---

## 6. 常见改进措施

### 6.1 准确性维度

| 问题 | 措施 |
|------|------|
| 事实错误 | 更新知识库、添加事实校验 |
| 计算错误 | 增加计算工具、添加校验步骤 |
| 数据过时 | 定期更新数据源 |

### 6.2 完整性维度

| 问题 | 措施 |
|------|------|
| 信息遗漏 | 添加信息检查清单 |
| 回答不完整 | 优化 Prompt 要求完整回答 |
| 缺少补充说明 | 添加补充信息模板 |

### 6.3 合规性维度

| 问题 | 措施 |
|------|------|
| 缺少风险提示 | 添加风险提示模板 |
| 违规内容 | 添加内容审核模块 |
| 适当性不足 | 增加投资者评估流程 |

---

## 7. 注意事项

- 建议仅供参考，需结合实际情况
- 实施改进后需重新评测验证
- 部分改进可能影响其他维度
- 建议分批实施，逐步验证
