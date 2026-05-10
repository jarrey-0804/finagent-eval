# 合规认证报告

> 本文档介绍如何生成和使用合规认证报告，满足监管合规要求。

---

## 1. 功能概述

合规认证报告功能提供：

- 符合监管要求的合规检查
- 详细的检查项评分
- 证据材料收集
- 认证有效期管理

### 支持的合规框架

| 框架 | 说明 |
|------|------|
| china_fund_regulation | 中国基金监管要求 |
| sec_finra | 美国 SEC/FINRA 要求 |

---

## 2. 使用方法

### 2.1 Web 界面操作

1. 打开「合规报告」页面
2. 选择已完成的评测
3. 选择合规框架
4. 选择是否包含证据材料
5. 点击「生成报告」

### 2.2 API 调用

```bash
curl -X POST "http://localhost:8000/api/v1/compliance/report" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "evaluation_id": "eval-20250601-abc123",
    "compliance_framework": "china_fund_regulation",
    "include_evidence": true
  }'
```

### 2.3 Python SDK

```python
from finagent import ComplianceReportGenerator

# 创建报告生成器
generator = ComplianceReportGenerator(
    evaluation_id="eval-20250601-abc123",
    framework="china_fund_regulation",
    include_evidence=True
)

# 生成报告
report = await generator.generate()

# 查看结果
print(f"认证状态: {report.status}")
print(f"合规评分: {report.overall_compliance_score}")
print(f"有效期至: {report.valid_until}")
```

---

## 3. 检查项说明

### 3.1 中国基金监管框架

| 检查项 | 说明 | 权重 |
|--------|------|------|
| risk_disclosure | 风险披露完整性 | 20% |
| suitability | 投资者适当性管理 | 20% |
| information_disclosure | 信息披露规范性 | 15% |
| prohibited_content | 禁止内容检测 | 15% |
| data_privacy | 数据隐私保护 | 15% |
| record_keeping | 记录保存合规 | 15% |

### 3.2 SEC/FINRA 框架

| 检查项 | 说明 | 权重 |
|--------|------|------|
| suitability | 适当性义务 | 25% |
| disclosure | 披露义务 | 20% |
| best_interest | 最佳利益原则 | 20% |
| supervision | 监督机制 | 15% |
| record_keeping | 记录保存 | 10% |
| advertising | 广告合规 | 10% |

---

## 4. 结果解读

### 4.1 报告结构

```json
{
  "report_id": "comp-20250601-xyz",
  "evaluation_id": "eval-20250601-abc123",
  "framework": "china_fund_regulation",
  "status": "passed",
  "overall_compliance_score": 92.5,
  "check_items": [
    {
      "item_id": "risk_disclosure",
      "name": "风险披露",
      "status": "passed",
      "score": 95.0,
      "evidence_count": 15,
      "issues": []
    },
    {
      "item_id": "suitability",
      "name": "投资者适当性",
      "status": "passed",
      "score": 90.0,
      "evidence_count": 12,
      "issues": []
    }
  ],
  "veto_triggered": false,
  "generated_at": "2025-06-01T16:00:00Z",
  "valid_until": "2025-09-01T16:00:00Z"
}
```

### 4.2 认证状态

| 状态 | 说明 |
|------|------|
| passed | 通过认证 |
| conditional | 条件通过，需整改 |
| failed | 未通过认证 |

### 4.3 一票否决

以下情况将触发一票否决，直接判定为未通过：

- 合规性维度得分 < 30
- 检测到严重违规内容
- PII 数据泄露

---

## 5. 证据材料

### 5.1 证据类型

- 评测任务原始输入/输出
- Agent 响应截图
- 工具调用记录
- 评分明细

### 5.2 证据管理

- 证据加密存储
- 访问权限控制
- 保留期限管理

---

## 6. 报告使用

### 6.1 有效期

- 默认有效期：3 个月
- 可申请延期：最长 6 个月
- 重大变更需重新认证

### 6.2 报告用途

- 内部合规审查
- 监管报送
- 第三方审计
- 客户证明材料

---

## 7. 注意事项

- 报告仅针对评测时的 Agent 版本
- Agent 更新后需重新认证
- 不同监管框架要求不同
- 建议定期进行合规评测
