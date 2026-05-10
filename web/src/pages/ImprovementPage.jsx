import React, { useState } from 'react';
import {
  Card, Input, Button, Tag, Progress, Row, Col, Statistic, Typography, Space, Spin, Collapse, Steps, message,
} from 'antd';
import { BulbOutlined, ArrowUpOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { improvementApi } from '../api';

const { Title, Text } = Typography;
const { Panel } = Collapse;

const DIMENSION_LABELS = {
  accuracy: '准确性', completeness: '完整性', reasoning: '推理能力',
  professionalism: '专业性', tool_usage: '工具使用', compliance: '合规性',
  security: '安全性', risk_awareness: '风险意识', robustness: '鲁棒性',
  transparency: '透明度', consistency: '一致性',
};

const mockImprovementData = {
  evaluation_id: 'eval-mock',
  overall_score: 65.0,
  rating: 'C',
  priority_improvements: [
    {
      priority: 'high', dimension: 'accuracy', current_score: 62.5, target_score: 80.0, gap: 17.5,
      suggestion: '加强金融知识库的覆盖范围，特别是衍生品和固定收益领域',
      actions: ['补充训练数据', '引入专业知识检索工具', '增加知识验证环节'],
      estimated_impact: '+12~15分',
    },
    {
      priority: 'high', dimension: 'compliance', current_score: 58.0, target_score: 75.0, gap: 17.0,
      suggestion: '强化监管规则理解，确保投资建议符合合规要求',
      actions: ['更新合规规则库', '添加合规检查中间件', '增加合规审查流程'],
      estimated_impact: '+10~13分',
    },
    {
      priority: 'medium', dimension: 'reasoning', current_score: 70.0, target_score: 82.0, gap: 12.0,
      suggestion: '提升多步推理能力，增强复杂金融场景的分析深度',
      actions: ['引入Chain-of-Thought提示', '增加推理步骤验证', '优化模型温度参数'],
      estimated_impact: '+8~10分',
    },
    {
      priority: 'medium', dimension: 'robustness', current_score: 55.0, target_score: 70.0, gap: 15.0,
      suggestion: '增强对异常数据和对抗性输入的鲁棒性',
      actions: ['添加数据验证层', '引入对抗性训练', '增加异常检测机制'],
      estimated_impact: '+8~12分',
    },
    {
      priority: 'low', dimension: 'tool_usage', current_score: 75.0, target_score: 85.0, gap: 10.0,
      suggestion: '优化工具调用准确性和效率',
      actions: ['增加工具使用示例', '优化工具选择策略', '添加工具调用结果验证'],
      estimated_impact: '+5~8分',
    },
  ],
  dimension_analysis: [
    { dimension: 'accuracy', score: 62.5, status: 'weak' },
    { dimension: 'compliance', score: 58.0, status: 'weak' },
    { dimension: 'reasoning', score: 70.0, status: 'normal' },
    { dimension: 'robustness', score: 55.0, status: 'weak' },
    { dimension: 'tool_usage', score: 75.0, status: 'normal' },
  ],
  action_plan: [
    { phase: '第一阶段（1-2周）', actions: ['补充金融知识库', '更新合规规则库'], expected_gain: '+15~20分' },
    { phase: '第二阶段（3-4周）', actions: ['引入CoT推理', '添加数据验证层'], expected_gain: '+10~15分' },
    { phase: '第三阶段（5-6周）', actions: ['优化工具调用', '增加对抗性训练'], expected_gain: '+8~12分' },
  ],
};

const priorityConfig = {
  high: { color: 'red', text: '高优先级' },
  medium: { color: 'orange', text: '中优先级' },
  low: { color: 'blue', text: '低优先级' },
};

const statusConfig = {
  weak: { color: '#ff4d4f', text: '薄弱' },
  normal: { color: '#faad14', text: '一般' },
  strong: { color: '#52c41a', text: '优秀' },
};

const ImprovementPage = () => {
  const [evaluationId, setEvaluationId] = useState('');
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);

  const fetchSuggestions = async () => {
    if (!evaluationId.trim()) {
      message.warning('请输入评测ID');
      return;
    }
    setLoading(true);
    try {
      const res = await improvementApi.suggestions({ evaluation_id: evaluationId });
      setData(res);
    } catch {
      message.warning('无法连接后端服务，使用模拟数据展示');
      setData({ ...mockImprovementData, evaluation_id: evaluationId });
    } finally {
      setLoading(false);
    }
  };

  const getRatingColor = (rating) => {
    switch (rating) {
      case 'A': case 'A+': return '#52c41a';
      case 'B': case 'B+': return '#1677ff';
      case 'C': case 'C+': return '#faad14';
      default: return '#ff4d4f';
    }
  };

  return (
    <div>
      <Title level={3}><BulbOutlined /> 智能改进建议</Title>
      <Text type="secondary" style={{ display: 'block', marginBottom: 24 }}>
        基于评测结果智能分析薄弱维度，生成优先级排序的改进建议和行动计划
      </Text>

      <Card style={{ marginBottom: 24 }}>
        <Space>
          <Input
            placeholder="请输入评测ID"
            value={evaluationId}
            onChange={(e) => setEvaluationId(e.target.value)}
            style={{ width: 300 }}
            onPressEnter={fetchSuggestions}
          />
          <Button type="primary" onClick={fetchSuggestions} loading={loading}>
            生成建议
          </Button>
        </Space>
      </Card>

      {loading && (
        <div style={{ textAlign: 'center', padding: 60 }}>
          <Spin size="large" tip="正在分析评测结果..." />
        </div>
      )}

      {data && !loading && (
        <>
          {/* 总分和评级 */}
          <Row gutter={16} style={{ marginBottom: 24 }}>
            <Col span={8}>
              <Card>
                <Statistic
                  title="综合评分"
                  value={data.overall_score}
                  precision={1}
                  suffix="/ 100"
                  valueStyle={{ color: '#1677ff' }}
                />
              </Card>
            </Col>
            <Col span={8}>
              <Card>
                <div style={{ textAlign: 'center' }}>
                  <Text type="secondary">综合评级</Text>
                  <div style={{
                    fontSize: 48, fontWeight: 'bold', color: getRatingColor(data.rating),
                    marginTop: 8,
                  }}>
                    {data.rating}
                  </div>
                </div>
              </Card>
            </Col>
            <Col span={8}>
              <Card>
                <Statistic
                  title="待改进维度"
                  value={data.dimension_analysis ? data.dimension_analysis.filter(d => d.status === 'weak').length : 0}
                  suffix={`/ ${data.dimension_analysis ? data.dimension_analysis.length : 0}`}
                  valueStyle={{ color: '#ff4d4f' }}
                />
              </Card>
            </Col>
          </Row>

          {/* 维度分析概览 */}
          <Card title="维度分析概览" style={{ marginBottom: 24 }}>
            <Row gutter={[16, 16]}>
              {data.dimension_analysis && data.dimension_analysis.map((dim) => {
                const cfg = statusConfig[dim.status] || statusConfig.normal;
                return (
                  <Col span={8} key={dim.dimension}>
                    <Card size="small" style={{ borderLeft: `3px solid ${cfg.color}` }}>
                      <Space direction="vertical" style={{ width: '100%' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                          <Text strong>{DIMENSION_LABELS[dim.dimension] || dim.dimension}</Text>
                          <Tag color={cfg.color}>{cfg.text}</Tag>
                        </div>
                        <Progress
                          percent={dim.score}
                          strokeColor={cfg.color}
                          format={(p) => `${p}`}
                        />
                      </Space>
                    </Card>
                  </Col>
                );
              })}
            </Row>
          </Card>

          {/* 优先改进建议 */}
          <Card title="优先改进建议" style={{ marginBottom: 24 }}>
            <Collapse accordion>
              {data.priority_improvements && data.priority_improvements.map((item, idx) => {
                const pCfg = priorityConfig[item.priority] || priorityConfig.medium;
                return (
                  <Panel
                    key={idx}
                    header={
                      <Space>
                        <Tag color={pCfg.color}>{pCfg.text}</Tag>
                        <Text strong>{DIMENSION_LABELS[item.dimension] || item.dimension}</Text>
                        <Text type="secondary">
                          {item.current_score} {'->'} {item.target_score}
                        </Text>
                        <Tag color="green"><ArrowUpOutlined /> {item.estimated_impact}</Tag>
                      </Space>
                    }
                  >
                    <div style={{ padding: '8px 0' }}>
                      <Text>{item.suggestion}</Text>
                      <div style={{ marginTop: 12 }}>
                        <Text strong>具体行动:</Text>
                        <ul style={{ marginTop: 8, paddingLeft: 20 }}>
                          {item.actions.map((action, i) => (
                            <li key={i}><Text>{action}</Text></li>
                          ))}
                        </ul>
                      </div>
                      <div style={{ marginTop: 8 }}>
                        <Text type="secondary">差距: </Text>
                        <Text strong type="danger">{item.gap}分</Text>
                        <Text type="secondary" style={{ marginLeft: 16 }}>预估提升: </Text>
                        <Text strong type="success">{item.estimated_impact}</Text>
                      </div>
                    </div>
                  </Panel>
                );
              })}
            </Collapse>
          </Card>

          {/* 行动计划 */}
          <Card title={<Space><ThunderboltOutlined /> 行动计划</Space>}>
            <Steps
              direction="vertical"
              current={-1}
              items={data.action_plan && data.action_plan.map((step, idx) => ({
                title: step.phase,
                description: (
                  <div>
                    <div style={{ marginBottom: 8 }}>
                      {step.actions.map((action, i) => (
                        <Tag key={i} style={{ marginBottom: 4 }}>{action}</Tag>
                      ))}
                    </div>
                    <Text type="success" strong>预期提升: {step.expected_gain}</Text>
                  </div>
                ),
              }))}
            />
          </Card>
        </>
      )}
    </div>
  );
};

export default ImprovementPage;
