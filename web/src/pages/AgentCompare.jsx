import React, { useState, useEffect, useMemo } from 'react';
import {
  Card, Table, Tag, Typography, Button, Space, Select, Row, Col,
  Alert, Spin, Tooltip, message,
} from 'antd';
import {
  BarChartOutlined, CheckCircleOutlined, CloseCircleOutlined,
} from '@ant-design/icons';
import { comparisonApi, agentApi } from '../api';
import { EmptyStates } from '../components/EmptyStates';

const { Title, Text } = Typography;

// 维度中文名映射
const dimensionLabels = {
  accuracy: '准确性',
  completeness: '完整性',
  reasoning: '推理能力',
  tool_usage: '工具使用',
  professionalism: '专业性',
  compliance: '合规性',
  risk_awareness: '风险意识',
  robustness: '鲁棒性',
  security: '安全性',
  transparency: '透明度',
  consistency: '一致性',
};

// Mock数据 - 当API不可用时使用
const mockAgents = [
  {
    agent_id: 'agent-001',
    agent_name: '智能投顾Agent',
    agent_type: 'langgraph',
    description: '基于大语言模型的智能投资顾问',
    status: 'registered',
  },
  {
    agent_id: 'agent-002',
    agent_name: '量化分析Agent',
    agent_type: 'langgraph',
    description: '专注于量化策略分析的Agent',
    status: 'registered',
  },
  {
    agent_id: 'agent-003',
    agent_name: '风控合规Agent',
    agent_type: 'langgraph',
    description: '专注于风险控制和合规检查的Agent',
    status: 'registered',
  },
];

const mockComparisonData = {
  comparison_id: 'cmp-mock-001',
  agents: [
    { agent_id: 'agent-001', agent_name: '智能投顾Agent', evaluation_id: 'eval-001', status: 'completed' },
    { agent_id: 'agent-002', agent_name: '量化分析Agent', evaluation_id: 'eval-002', status: 'completed' },
    { agent_id: 'agent-003', agent_name: '风控合规Agent', evaluation_id: 'eval-003', status: 'completed' },
  ],
  dimensions: ['accuracy', 'completeness', 'reasoning', 'tool_usage', 'professionalism', 'compliance', 'risk_awareness', 'robustness', 'security', 'transparency', 'consistency'],
  scores: [
    { agent_id: 'agent-001', agent_name: '智能投顾Agent', overall_score: 85.2, overall_rating: 'A', accuracy: 88, completeness: 82, reasoning: 79, tool_usage: 90, professionalism: 85, compliance: 92, risk_awareness: 86, robustness: 78, security: 88, transparency: 80, consistency: 84 },
    { agent_id: 'agent-002', agent_name: '量化分析Agent', overall_score: 82.5, overall_rating: 'B', accuracy: 85, completeness: 80, reasoning: 88, tool_usage: 82, professionalism: 78, compliance: 85, risk_awareness: 90, robustness: 82, security: 80, transparency: 76, consistency: 80 },
    { agent_id: 'agent-003', agent_name: '风控合规Agent', overall_score: 88.0, overall_rating: 'A', accuracy: 82, completeness: 88, reasoning: 80, tool_usage: 75, professionalism: 90, compliance: 95, risk_awareness: 92, robustness: 88, security: 92, transparency: 88, consistency: 90 },
  ],
};

// 多Agent雷达图叠加组件
const MultiRadarChart = ({ agents, dimensions, scores }) => {
  const n = dimensions.length;
  const size = 400;
  const center = size / 2;
  const maxRadius = 150;

  const angleStep = (2 * Math.PI) / n;
  const startAngle = -Math.PI / 2;

  const getPoint = (index, value) => {
    const angle = startAngle + index * angleStep;
    const r = (value / 100) * maxRadius;
    return {
      x: center + r * Math.cos(angle),
      y: center + r * Math.sin(angle),
    };
  };

  // 颜色列表
  const colors = ['#1677ff', '#fa8c16', '#52c41a', '#722ed1', '#eb2f96'];

  // 网格线
  const gridLevels = [20, 40, 60, 80, 100];
  const gridPaths = gridLevels.map((level) => {
    const points = dimensions.map((_, i) => getPoint(i, level));
    const pathData = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ') + ' Z';
    return <path key={`grid-${level}`} d={pathData} fill="none" stroke="#e8e8e8" strokeWidth="1" />;
  });

  // 轴线
  const axisLines = dimensions.map((_, i) => {
    const p = getPoint(i, 100);
    return <line key={`axis-${i}`} x1={center} y1={center} x2={p.x} y2={p.y} stroke="#e8e8e8" strokeWidth="1" />;
  });

  // 标签
  const labels = dimensions.map((dim, i) => {
    const p = getPoint(i, 118);
    const anchor = Math.abs(p.x - center) < 10 ? 'middle' : p.x > center ? 'start' : 'end';
    return (
      <text key={`label-${dim}`} x={p.x} y={p.y} textAnchor={anchor} fontSize="11" fill="#666" dominantBaseline="middle">
        {dimensionLabels[dim] || dim}
      </text>
    );
  });

  // 各Agent数据区域
  const agentAreas = scores.map((score, agentIndex) => {
    const color = colors[agentIndex % colors.length];
    const dataPoints = dimensions.map((dim, i) => getPoint(i, score[dim] || 0));
    const dataPath = dataPoints.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ') + ' Z';
    const dots = dataPoints.map((p, i) => (
      <circle key={`dot-${agentIndex}-${i}`} cx={p.x} cy={p.y} r="3" fill={color} stroke="#fff" strokeWidth="1.5" />
    ));
    return (
      <g key={`agent-${agentIndex}`}>
        <path d={dataPath} fill={`${color}20`} stroke={color} strokeWidth="2" />
        {dots}
      </g>
    );
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {gridPaths}
        {axisLines}
        {agentAreas}
        {labels}
      </svg>
      {/* 图例 */}
      <div style={{ display: 'flex', gap: 24, marginTop: 16, flexWrap: 'wrap', justifyContent: 'center' }}>
        {scores.map((score, i) => (
          <Space key={score.agent_id}>
            <div style={{ width: 12, height: 12, borderRadius: 2, backgroundColor: colors[i % colors.length] }} />
            <Text>{score.agent_name || score.agent_id}</Text>
          </Space>
        ))}
      </div>
    </div>
  );
};

const AgentCompare = () => {
  const [agents, setAgents] = useState([]);
  const [selectedAgentIds, setSelectedAgentIds] = useState([]);
  const [comparisonData, setComparisonData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [agentsLoading, setAgentsLoading] = useState(false);
  const [useMock, setUseMock] = useState(false);

  // 加载Agent列表
  useEffect(() => {
    const fetchAgents = async () => {
      setAgentsLoading(true);
      try {
        const result = await agentApi.list();
        const agentList = result?.agents || result || [];
        if (Array.isArray(agentList) && agentList.length > 0) {
          setAgents(agentList);
        } else {
          // 使用mock数据
          setAgents(mockAgents);
          setUseMock(true);
        }
      } catch (err) {
        console.warn('获取Agent列表失败，使用mock数据:', err);
        setAgents(mockAgents);
        setUseMock(true);
      } finally {
        setAgentsLoading(false);
      }
    };
    fetchAgents();
  }, []);

  // Agent选择选项
  const agentOptions = useMemo(() => {
    return agents.map((a) => ({
      label: a.agent_name || a.agent_id,
      value: a.agent_id,
    }));
  }, [agents]);

  // 执行对比
  const handleCompare = async () => {
    if (selectedAgentIds.length < 2) {
      message.warning('请至少选择2个Agent进行对比');
      return;
    }

    setLoading(true);
    try {
      const result = await comparisonApi.compare({ agent_ids: selectedAgentIds });
      // 合并Agent名称信息
      const enrichedScores = (result.scores || []).map((s) => {
        const agent = agents.find((a) => a.agent_id === s.agent_id);
        return { ...s, agent_name: agent?.agent_name || s.agent_id };
      });
      const enrichedAgents = (result.agents || []).map((a) => {
        const agent = agents.find((ag) => ag.agent_id === a.agent_id);
        return { ...a, agent_name: agent?.agent_name || a.agent_id };
      });
      setComparisonData({
        ...result,
        scores: enrichedScores,
        agents: enrichedAgents,
      });
    } catch (err) {
      console.warn('对比API调用失败，使用mock数据:', err);
      // 使用mock数据作为fallback
      const filteredScores = mockComparisonData.scores.filter((s) =>
        selectedAgentIds.includes(s.agent_id)
      );
      const filteredAgents = mockComparisonData.agents.filter((a) =>
        selectedAgentIds.includes(a.agent_id)
      );
      setComparisonData({
        ...mockComparisonData,
        scores: filteredScores.length > 0 ? filteredScores : mockComparisonData.scores,
        agents: filteredAgents.length > 0 ? filteredAgents : mockComparisonData.agents,
      });
    } finally {
      setLoading(false);
    }
  };

  // 维度对比表格列
  const dimensionColumns = useMemo(() => {
    if (!comparisonData) return [];
    const agentColumns = comparisonData.scores.map((s, i) => ({
      title: s.agent_name || s.agent_id,
      dataIndex: s.agent_id,
      key: s.agent_id,
      width: 120,
      render: (val) => {
        const color = val >= 85 ? '#52c41a' : val >= 70 ? '#1677ff' : val >= 60 ? '#fa8c16' : '#ff4d4f';
        return <Text strong style={{ color }}>{val}</Text>;
      },
      sorter: (a, b) => (a[s.agent_id] || 0) - (b[s.agent_id] || 0),
    }));

    return [
      {
        title: '评测维度',
        dataIndex: 'dimension',
        key: 'dimension',
        width: 120,
        fixed: 'left',
        render: (dim) => <Text strong>{dimensionLabels[dim] || dim}</Text>,
      },
      ...agentColumns,
      {
        title: '最高分',
        key: 'best',
        width: 100,
        render: (_, record) => {
          const vals = comparisonData.scores.map((s) => record[s.agent_id] || 0);
          const maxVal = Math.max(...vals);
          const bestAgent = comparisonData.scores.find((s) => record[s.agent_id] === maxVal);
          return (
            <Tooltip title={bestAgent?.agent_name || ''}>
              <Tag color="gold">{maxVal}</Tag>
            </Tooltip>
          );
        },
      },
    ];
  }, [comparisonData]);

  // 维度对比表格数据
  const dimensionTableData = useMemo(() => {
    if (!comparisonData) return [];
    return comparisonData.dimensions.map((dim) => {
      const row = { key: dim, dimension: dim };
      comparisonData.scores.forEach((s) => {
        row[s.agent_id] = s[dim] || 0;
      });
      return row;
    });
  }, [comparisonData]);

  // 总分对比表格
  const summaryColumns = [
    { title: 'Agent名称', dataIndex: 'agent_name', key: 'agent_name' },
    { title: 'Agent ID', dataIndex: 'agent_id', key: 'agent_id' },
    {
      title: '总体评分',
      dataIndex: 'overall_score',
      key: 'overall_score',
      sorter: (a, b) => a.overall_score - b.overall_score,
      render: (val) => <Text strong style={{ fontSize: 16, color: '#1677ff' }}>{val}</Text>,
    },
    {
      title: '总体评级',
      dataIndex: 'overall_rating',
      key: 'overall_rating',
      render: (val) => <Tag color={val === 'S' ? 'gold' : val === 'A' ? 'green' : val === 'B' ? 'blue' : 'orange'}>{val}</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (s) => s === 'completed'
        ? <Tag icon={<CheckCircleOutlined />} color="success">已完成</Tag>
        : <Tag icon={<CloseCircleOutlined />} color="default">未评测</Tag>,
    },
  ];

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 24 }}>
        <BarChartOutlined style={{ fontSize: 24, color: '#1677ff' }} />
        <div>
          <Title level={4} style={{ margin: 0 }}>Agent对比</Title>
          <p style={{ margin: '4px 0 0', color: '#888' }}>选择多个Agent进行评测结果对比分析</p>
        </div>
      </div>

      {/* Agent选择区域 */}
      <Card title="选择对比Agent" style={{ marginBottom: 16 }}>
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <div>
            <Text type="secondary" style={{ marginBottom: 8, display: 'block' }}>
              请选择至少2个Agent进行对比（最多5个）
            </Text>
            <Select
              mode="multiple"
              placeholder="选择要对比的Agent"
              value={selectedAgentIds}
              onChange={(vals) => setSelectedAgentIds(vals.slice(0, 5))}
              options={agentOptions}
              style={{ width: '100%' }}
              maxTagCount="responsive"
              loading={agentsLoading}
              allowClear
            />
          </div>
          <Space>
            <Button
              type="primary"
              onClick={handleCompare}
              loading={loading}
              disabled={selectedAgentIds.length < 2}
            >
              开始对比
            </Button>
            <Button onClick={() => { setSelectedAgentIds([]); setComparisonData(null); }}>
              重置
            </Button>
          </Space>
          {useMock && (
            <Alert
              type="info"
              message="当前使用模拟数据"
              description="无法连接到后端API，正在使用模拟数据进行展示"
              showIcon
            />
          )}
        </Space>
      </Card>

      {/* 对比结果 */}
      {comparisonData && (
        <>
          {/* 总分对比 */}
          <Card title="总体评分对比" style={{ marginBottom: 16 }}>
            <Table
              columns={summaryColumns}
              dataSource={comparisonData.scores.map((s) => ({
                ...s,
                status: comparisonData.agents.find((a) => a.agent_id === s.agent_id)?.status || 'not_found',
              }))}
              rowKey="agent_id"
              pagination={false}
              size="small"
            />
          </Card>

          {/* 雷达图对比 */}
          <Card title="维度雷达图对比" style={{ marginBottom: 16 }}>
            <MultiRadarChart
              agents={comparisonData.agents}
              dimensions={comparisonData.dimensions}
              scores={comparisonData.scores}
            />
          </Card>

          {/* 维度详细对比表 */}
          <Card title="维度评分详细对比">
            <Table
              columns={dimensionColumns}
              dataSource={dimensionTableData}
              rowKey="dimension"
              pagination={false}
              size="small"
              scroll={{ x: 800 }}
            />
          </Card>
        </>
      )}

      {/* 空状态 */}
      {!comparisonData && !loading && (
        <Card>
          {EmptyStates.noAgents(() => {
            // 聚焦到Agent选择器
            document.querySelector('.ant-select')?.focus();
          })}
        </Card>
      )}
    </div>
  );
};

export default AgentCompare;
