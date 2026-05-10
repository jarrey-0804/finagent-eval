import React, { useState } from 'react';
import {
  Card, Select, Button, Table, Tag, Progress, Row, Col, Statistic, List, Typography, Space, Spin, message,
} from 'antd';
import { FundOutlined, ArrowUpOutlined, ArrowDownOutlined } from '@ant-design/icons';
import { benchmarkApi } from '../api';

const { Title, Text } = Typography;

const AGENT_TYPES = [
  { value: 'investment_decision', label: '投资决策' },
  { value: 'quant_research', label: '量化研究' },
  { value: 'trade_execution', label: '交易执行' },
  { value: 'financial_analysis', label: '金融分析' },
];

const DIMENSION_LABELS = {
  accuracy: '准确性', completeness: '完整性', reasoning: '推理能力',
  professionalism: '专业性', tool_usage: '工具使用', compliance: '合规性',
  security: '安全性', risk_awareness: '风险意识', robustness: '鲁棒性',
  transparency: '透明度', consistency: '一致性',
};

const mockBenchmarkData = {
  agent_id: 'mock-agent',
  agent_type: 'investment_decision',
  agent_score: 75.0,
  benchmark_avg: 68.5,
  benchmark_p50: 70.2,
  benchmark_p75: 78.5,
  benchmark_p90: 85.0,
  percentile_rank: 58.3,
  dimension_comparison: [
    { dimension: 'accuracy', agent_score: 78.0, benchmark_avg: 72.0, gap: 6.0 },
    { dimension: 'completeness', agent_score: 68.0, benchmark_avg: 68.5, gap: -0.5 },
    { dimension: 'reasoning', agent_score: 72.0, benchmark_avg: 65.0, gap: 7.0 },
    { dimension: 'professionalism', agent_score: 70.0, benchmark_avg: 70.0, gap: 0.0 },
    { dimension: 'tool_usage', agent_score: 65.0, benchmark_avg: 62.0, gap: 3.0 },
    { dimension: 'compliance', agent_score: 80.0, benchmark_avg: 75.0, gap: 5.0 },
    { dimension: 'security', agent_score: 85.0, benchmark_avg: 80.0, gap: 5.0 },
    { dimension: 'risk_awareness', agent_score: 68.0, benchmark_avg: 70.0, gap: -2.0 },
    { dimension: 'robustness', agent_score: 58.0, benchmark_avg: 60.0, gap: -2.0 },
    { dimension: 'transparency', agent_score: 63.0, benchmark_avg: 65.0, gap: -2.0 },
    { dimension: 'consistency', agent_score: 67.0, benchmark_avg: 68.0, gap: -1.0 },
  ],
  recommendations: [
    '重点提升以下维度: robustness, transparency, consistency',
    '表现优秀，已超过行业75%分位',
  ],
};

const BenchmarkPage = () => {
  const [agentId, setAgentId] = useState('agent-001');
  const [agentType, setAgentType] = useState('investment_decision');
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);

  const fetchBenchmark = async () => {
    setLoading(true);
    try {
      const res = await benchmarkApi.compare({ agent_id: agentId, agent_type: agentType });
      setData(res);
    } catch {
      message.warning('无法连接后端服务，使用模拟数据展示');
      setData({ ...mockBenchmarkData, agent_id: agentId, agent_type: agentType });
    } finally {
      setLoading(false);
    }
  };

  const dimensionColumns = [
    {
      title: '维度',
      dataIndex: 'dimension',
      key: 'dimension',
      render: (dim) => DIMENSION_LABELS[dim] || dim,
    },
    {
      title: 'Agent得分',
      dataIndex: 'agent_score',
      key: 'agent_score',
      render: (val) => <Text strong>{val}</Text>,
    },
    {
      title: '行业平均',
      dataIndex: 'benchmark_avg',
      key: 'benchmark_avg',
    },
    {
      title: '差距',
      dataIndex: 'gap',
      key: 'gap',
      render: (gap) => {
        if (gap > 0) return <Text type="success"><ArrowUpOutlined /> +{gap}</Text>;
        if (gap < 0) return <Text type="danger"><ArrowDownOutlined /> {gap}</Text>;
        return <Text type="secondary">-</Text>;
      },
    },
    {
      title: '对比',
      key: 'bar',
      render: (_, record) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Progress
            percent={record.agent_score}
            size="small"
            strokeColor="#1677ff"
            format={() => ''}
            style={{ flex: 1, marginBottom: 0 }}
          />
          <Progress
            percent={record.benchmark_avg}
            size="small"
            strokeColor="#faad14"
            format={() => ''}
            style={{ flex: 1, marginBottom: 0 }}
          />
        </div>
      ),
    },
  ];

  const getPercentileColor = (rank) => {
    if (rank >= 75) return '#52c41a';
    if (rank >= 50) return '#1677ff';
    if (rank >= 25) return '#faad14';
    return '#ff4d4f';
  };

  return (
    <div>
      <Title level={3}><FundOutlined /> 行业基准对比</Title>
      <Text type="secondary" style={{ display: 'block', marginBottom: 24 }}>
        将您的 Agent 评测表现与行业基准进行对比，了解相对位置和改进方向
      </Text>

      <Card style={{ marginBottom: 24 }}>
        <Space wrap>
          <div>
            <Text strong style={{ display: 'block', marginBottom: 4 }}>Agent ID</Text>
            <Select
              value={agentId}
              onChange={setAgentId}
              style={{ width: 200 }}
              options={[
                { value: 'agent-001', label: 'Agent-001' },
                { value: 'agent-002', label: 'Agent-002' },
                { value: 'agent-003', label: 'Agent-003' },
              ]}
            />
          </div>
          <div>
            <Text strong style={{ display: 'block', marginBottom: 4 }}>Agent 类型</Text>
            <Select
              value={agentType}
              onChange={setAgentType}
              style={{ width: 200 }}
              options={AGENT_TYPES}
            />
          </div>
          <Button type="primary" onClick={fetchBenchmark} loading={loading}>
            开始对比
          </Button>
        </Space>
      </Card>

      {loading && (
        <div style={{ textAlign: 'center', padding: 60 }}>
          <Spin size="large" tip="正在获取基准数据..." />
        </div>
      )}

      {data && !loading && (
        <>
          {/* 核心指标卡片 */}
          <Row gutter={16} style={{ marginBottom: 24 }}>
            <Col span={6}>
              <Card>
                <Statistic
                  title="Agent 评分"
                  value={data.agent_score}
                  precision={1}
                  suffix="/ 100"
                  valueStyle={{ color: '#1677ff' }}
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic
                  title="行业平均"
                  value={data.benchmark_avg}
                  precision={1}
                  suffix="/ 100"
                  valueStyle={{ color: '#faad14' }}
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic
                  title="行业中位数 (P50)"
                  value={data.benchmark_p50}
                  precision={1}
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic
                  title="行业 P75"
                  value={data.benchmark_p75}
                  precision={1}
                />
              </Card>
            </Col>
          </Row>

          {/* 百分位排名 */}
          <Card title="百分位排名" style={{ marginBottom: 24 }}>
            <div style={{ textAlign: 'center', padding: '20px 0' }}>
              <Progress
                type="circle"
                percent={Math.round(data.percentile_rank)}
                size={160}
                strokeColor={getPercentileColor(data.percentile_rank)}
                format={(percent) => (
                  <div>
                    <div style={{ fontSize: 28, fontWeight: 'bold', color: getPercentileColor(data.percentile_rank) }}>
                      {percent}%
                    </div>
                    <div style={{ fontSize: 12, color: '#999' }}>百分位排名</div>
                  </div>
                )}
              />
              <div style={{ marginTop: 16 }}>
                <Tag color={data.percentile_rank >= 75 ? 'green' : data.percentile_rank >= 50 ? 'blue' : 'orange'}>
                  {data.percentile_rank >= 75 ? '超过行业75%的Agent' : data.percentile_rank >= 50 ? '超过行业中位数' : '低于行业中位数'}
                </Tag>
              </div>
            </div>
          </Card>

          {/* 维度对比表格 */}
          <Card title="维度对比详情" style={{ marginBottom: 24 }}>
            <Table
              dataSource={data.dimension_comparison}
              columns={dimensionColumns}
              rowKey="dimension"
              pagination={false}
              size="middle"
            />
            <div style={{ marginTop: 12, display: 'flex', gap: 16 }}>
              <span><span style={{ display: 'inline-block', width: 12, height: 12, backgroundColor: '#1677ff', borderRadius: 2, marginRight: 4 }} />Agent得分</span>
              <span><span style={{ display: 'inline-block', width: 12, height: 12, backgroundColor: '#faad14', borderRadius: 2, marginRight: 4 }} />行业平均</span>
            </div>
          </Card>

          {/* 改进建议 */}
          {data.recommendations && data.recommendations.length > 0 && (
            <Card title="改进建议">
              <List
                dataSource={data.recommendations}
                renderItem={(item) => (
                  <List.Item>
                    <Text>{item}</Text>
                  </List.Item>
                )}
              />
            </Card>
          )}
        </>
      )}
    </div>
  );
};

export default BenchmarkPage;
