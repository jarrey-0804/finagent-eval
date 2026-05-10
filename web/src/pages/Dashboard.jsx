import React, { useState, useEffect, useMemo } from 'react';
import { Card, Row, Col, Statistic, Table, Typography } from 'antd';
import {
  CheckCircleOutlined,
  ThunderboltOutlined,
  TrophyOutlined,
  RobotOutlined,
  ClockCircleOutlined,
  DashboardOutlined,
} from '@ant-design/icons';
import StatusTag from '../components/StatusTag';
import ScoreBadge from '../components/ScoreBadge';
import { DashboardSkeleton } from '../components/Skeletons';
import { useEvaluations, useAgents, useSystemHealth, useSystemInfo } from '../hooks/useApi';

const { Title, Text } = Typography;

// 模拟数据 - 作为API失败时的fallback
const mockStats = {
  totalEvaluations: 156,
  successRate: 87.5,
  avgScore: 76.3,
  activeAgents: 12,
};

const mockRecentEvals = [
  { id: 'eval-001', agent: '智能投顾Agent', mode: '完整评测', status: 'completed', score: 85.2, rating: 'A', created: '2025-01-15 14:30' },
  { id: 'eval-002', agent: '量化研究Agent', mode: '快速评测', status: 'completed', score: 72.1, rating: 'B', created: '2025-01-15 13:20' },
  { id: 'eval-003', agent: '风控分析Agent', mode: '完整评测', status: 'running', score: null, rating: null, created: '2025-01-15 12:00' },
  { id: 'eval-004', agent: '交易执行Agent', mode: '快速评测', status: 'failed', score: 45.0, rating: 'D', created: '2025-01-15 10:45' },
  { id: 'eval-005', agent: '财务分析Agent', mode: '完整评测', status: 'completed', score: 91.5, rating: 'S', created: '2025-01-14 16:30' },
  { id: 'eval-006', agent: '合规检查Agent', mode: '快速评测', status: 'completed', score: 68.3, rating: 'C', created: '2025-01-14 15:00' },
  { id: 'eval-007', agent: '新闻解读Agent', mode: '完整评测', status: 'completed', score: 78.9, rating: 'B', created: '2025-01-14 11:20' },
  { id: 'eval-008', agent: '资产配置Agent', mode: '快速评测', status: 'pending', score: null, rating: null, created: '2025-01-14 09:00' },
  { id: 'eval-009', agent: '行情分析Agent', mode: '完整评测', status: 'completed', score: 82.6, rating: 'A', created: '2025-01-13 17:00' },
  { id: 'eval-010', agent: '信用评估Agent', mode: '快速评测', status: 'completed', score: 55.2, rating: 'C', created: '2025-01-13 14:30' },
];

const mockScoreDistribution = [
  { range: '0-20', count: 5, color: '#ff4d4f' },
  { range: '20-40', count: 8, color: '#fa8c16' },
  { range: '40-60', count: 18, color: '#faad14' },
  { range: '60-80', count: 35, color: '#1677ff' },
  { range: '80-100', count: 24, color: '#52c41a' },
];

const mockResponseTime = { p95: 234, p99: 456, avg: 128 };
const mockScheduler = { queue_size: 8, running_count: 3, mode: 'distributed' };

const mockPhaseDistribution = [
  { phase: '静态评估', count: 45, color: '#1677ff', status: 'static_eval' },
  { phase: '动态评估', count: 32, color: '#fa8c16', status: 'dynamic_eval' },
  { phase: '可信度评估', count: 28, color: '#722ed1', status: 'trust_eval' },
];

const Dashboard = () => {
  const { data: evaluations, loading: evalLoading } = useEvaluations({ limit: 10 });
  const { data: agents, loading: agentsLoading } = useAgents();
  const { health, loading: healthLoading } = useSystemHealth();
  const { info, loading: infoLoading } = useSystemInfo();

  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => setLoading(false), 500);
    return () => clearTimeout(timer);
  }, [evalLoading, agentsLoading, healthLoading, infoLoading]);

  const stats = useMemo(() => {
    if (info && info.stats) {
      return {
        totalEvaluations: info.stats.total_evaluations || mockStats.totalEvaluations,
        successRate: info.stats.success_rate || mockStats.successRate,
        avgScore: info.stats.avg_score || mockStats.avgScore,
        activeAgents: agents.length || mockStats.activeAgents,
      };
    }
    if (evaluations && evaluations.length > 0) {
      const completed = evaluations.filter(e => e.status === 'completed');
      const successCount = completed.filter(e => e.score >= 60).length;
      const avgScore = completed.length > 0 
        ? completed.reduce((sum, e) => sum + (e.score || 0), 0) / completed.length 
        : mockStats.avgScore;
      return {
        totalEvaluations: evaluations.length,
        successRate: completed.length > 0 ? (successCount / completed.length * 100).toFixed(1) : mockStats.successRate,
        avgScore: avgScore.toFixed(1),
        activeAgents: agents.length || mockStats.activeAgents,
      };
    }
    return { ...mockStats, activeAgents: agents.length || mockStats.activeAgents };
  }, [evaluations, agents, info]);

  const recentEvals = useMemo(() => {
    if (evaluations && evaluations.length > 0) {
      return evaluations.slice(0, 10).map(item => ({
        id: item.id || item.evaluation_id,
        agent: item.agent_name || item.agent,
        mode: item.mode === 'full' ? '完整评测' : item.mode === 'quick' ? '快速评测' : item.mode,
        status: item.status,
        score: item.overall_score ?? item.score,
        rating: item.overall_rating ?? item.rating,
        created: item.created_at || item.created,
      }));
    }
    return mockRecentEvals;
  }, [evaluations]);

  const responseTime = useMemo(() => health?.response_time || mockResponseTime, [health]);
  const scheduler = useMemo(() => info?.scheduler || mockScheduler, [info]);
  const maxCount = Math.max(...mockScoreDistribution.map((d) => d.count));

  const columns = [
    { title: '评测ID', dataIndex: 'id', key: 'id', width: 120 },
    { title: 'Agent名称', dataIndex: 'agent', key: 'agent' },
    { title: '评测模式', dataIndex: 'mode', key: 'mode', width: 100 },
    { title: '状态', dataIndex: 'status', key: 'status', width: 100, render: (status) => <StatusTag status={status} /> },
    { title: '评分', key: 'score', width: 100, render: (_, record) => record.score != null ? <ScoreBadge rating={record.rating} score={record.score} /> : '-' },
    { title: '创建时间', dataIndex: 'created', key: 'created', width: 160 },
  ];

  return (
    <div>
      <div className="page-header">
        <Title level={4}>仪表盘</Title>
        <p>金融AI Agent评测系统概览</p>
      </div>

      {loading && <DashboardSkeleton />}

      {!loading && (
        <>
          <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
            <Col xs={24} sm={12} lg={6}>
              <Card className="stat-card">
                <Statistic title="总评测次数" value={stats.totalEvaluations} prefix={<CheckCircleOutlined />} valueStyle={{ color: '#1677ff' }} />
              </Card>
            </Col>
            <Col xs={24} sm={12} lg={6}>
              <Card className="stat-card">
                <Statistic title="成功率" value={stats.successRate} suffix="%" prefix={<ThunderboltOutlined />} valueStyle={{ color: '#52c41a' }} />
              </Card>
            </Col>
            <Col xs={24} sm={12} lg={6}>
              <Card className="stat-card">
                <Statistic title="平均评分" value={stats.avgScore} prefix={<TrophyOutlined />} valueStyle={{ color: '#fa8c16' }} />
              </Card>
            </Col>
            <Col xs={24} sm={12} lg={6}>
              <Card className="stat-card">
                <Statistic title="活跃Agent" value={stats.activeAgents} prefix={<RobotOutlined />} valueStyle={{ color: '#722ed1' }} />
              </Card>
            </Col>
          </Row>

          <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
            <Col xs={24} sm={12} lg={6}>
              <Card className="stat-card">
                <Statistic title="API 响应时间 (P95)" value={responseTime.p95} suffix="ms" prefix={<ClockCircleOutlined />} valueStyle={{ color: '#13c2c2' }} />
              </Card>
            </Col>
            <Col xs={24} sm={12} lg={6}>
              <Card className="stat-card">
                <Statistic title="调度器队列大小" value={scheduler.queue_size} prefix={<DashboardOutlined />} valueStyle={{ color: '#eb2f96' }} />
              </Card>
            </Col>
            <Col xs={24} sm={12} lg={6}>
              <Card className="stat-card">
                <Statistic title="运行中任务数" value={scheduler.running_count} prefix={<ThunderboltOutlined />} valueStyle={{ color: '#52c41a' }} />
              </Card>
            </Col>
            <Col xs={24} sm={12} lg={6}>
              <Card className="stat-card">
                <Statistic title="调度器模式" value={scheduler.mode === 'distributed' ? '分布式' : '内存'} prefix={<DashboardOutlined />} valueStyle={{ color: '#1677ff', fontSize: 20 }} />
              </Card>
            </Col>
          </Row>

          <Card title="三阶段评测分布" style={{ marginBottom: 24 }}>
            <Row gutter={[16, 16]}>
              {mockPhaseDistribution.map((item) => (
                <Col xs={24} sm={8} key={item.phase}>
                  <Card size="small" style={{ borderLeft: `4px solid ${item.color}` }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                      <StatusTag status={item.status} />
                      <Text strong style={{ fontSize: 24, color: item.color }}>{item.count}</Text>
                    </div>
                    <div style={{ height: 8, backgroundColor: '#f0f0f0', borderRadius: 4, overflow: 'hidden' }}>
                      <div style={{ height: '100%', width: `${(item.count / Math.max(...mockPhaseDistribution.map(d => d.count))) * 100}%`, backgroundColor: item.color, borderRadius: 4, transition: 'width 0.3s' }} />
                    </div>
                  </Card>
                </Col>
              ))}
            </Row>
          </Card>

          <Row gutter={[16, 16]}>
            <Col xs={24} lg={10}>
              <Card title="评分分布">
                <div className="score-bar-chart">
                  {mockScoreDistribution.map((item) => (
                    <div className="score-bar-item" key={item.range}>
                      <span className="score-bar-value">{item.count}</span>
                      <div className="score-bar" style={{ height: `${(item.count / maxCount) * 160}px`, backgroundColor: item.color }} />
                      <span className="score-bar-label">{item.range}</span>
                    </div>
                  ))}
                </div>
              </Card>
            </Col>
            <Col xs={24} lg={14}>
              <Card title="最近评测记录">
                <Table columns={columns} dataSource={recentEvals} rowKey="id" size="small" pagination={false} scroll={{ y: 320 }} />
              </Card>
            </Col>
          </Row>
        </>
      )}
    </div>
  );
};

export default Dashboard;
