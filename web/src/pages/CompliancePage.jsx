import React, { useState } from 'react';
import {
  Card, Input, Button, Table, Tag, Progress, Row, Col, Statistic, List, Typography, Space, Spin, Badge, Alert, message,
} from 'antd';
import { SafetyCertificateOutlined, CheckCircleOutlined, CloseCircleOutlined, WarningOutlined } from '@ant-design/icons';
import { complianceApi } from '../api';

const { Title, Text } = Typography;

const mockComplianceData = {
  evaluation_id: 'eval-mock',
  overall_compliance: 'conditional_pass',
  compliance_score: 72.5,
  checks: [
    { id: 'CC-001', name: '金融数据准确性', category: '数据合规', score: 85.0, status: 'pass', weight: 20 },
    { id: 'CC-002', name: '投资建议合规性', category: '监管合规', score: 62.0, status: 'fail', weight: 25 },
    { id: 'CC-003', name: '风险提示充分性', category: '监管合规', score: 78.0, status: 'pass', weight: 20 },
    { id: 'CC-004', name: '个人信息保护', category: '数据安全', score: 90.0, status: 'pass', weight: 15 },
    { id: 'CC-005', name: '禁止内幕交易', category: '行为合规', score: 55.0, status: 'fail', weight: 20 },
  ],
  risk_items: [
    { check_id: 'CC-002', check_name: '投资建议合规性', severity: 'medium', description: '投资建议合规性检查未通过，得分62.0，低于70分阈值', suggestion: '建议加强投资建议合规性相关能力' },
    { check_id: 'CC-005', check_name: '禁止内幕交易', severity: 'high', description: '禁止内幕交易检查未通过，得分55.0，低于70分阈值', suggestion: '建议加强禁止内幕交易相关能力' },
  ],
  summary: '合规评分 72.5/100，存在合规风险',
  generated_at: new Date().toISOString(),
};

const CompliancePage = () => {
  const [evaluationId, setEvaluationId] = useState('');
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);

  const generateReport = async () => {
    if (!evaluationId.trim()) {
      message.warning('请输入评测ID');
      return;
    }
    setLoading(true);
    try {
      const res = await complianceApi.generate({ evaluation_id: evaluationId });
      setData(res);
    } catch {
      message.warning('无法连接后端服务，使用模拟数据展示');
      setData({ ...mockComplianceData, evaluation_id: evaluationId });
    } finally {
      setLoading(false);
    }
  };

  const getOverallConfig = (status) => {
    switch (status) {
      case 'pass':
        return { color: '#52c41a', text: '合规通过', icon: <CheckCircleOutlined /> };
      case 'conditional_pass':
        return { color: '#faad14', text: '有条件通过', icon: <WarningOutlined /> };
      case 'fail':
        return { color: '#ff4d4f', text: '合规不通过', icon: <CloseCircleOutlined /> };
      default:
        return { color: '#999', text: '未知', icon: null };
    }
  };

  const checkColumns = [
    {
      title: '检查项ID',
      dataIndex: 'id',
      key: 'id',
      width: 100,
    },
    {
      title: '检查项名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '类别',
      dataIndex: 'category',
      key: 'category',
      render: (cat) => <Tag>{cat}</Tag>,
    },
    {
      title: '权重',
      dataIndex: 'weight',
      key: 'weight',
      render: (w) => `${w}%`,
    },
    {
      title: '得分',
      dataIndex: 'score',
      key: 'score',
      render: (score) => (
        <Progress
          percent={score}
          size="small"
          strokeColor={score >= 70 ? '#52c41a' : '#ff4d4f'}
          format={(p) => `${p}`}
          style={{ width: 120 }}
        />
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status) => (
        <Badge
          status={status === 'pass' ? 'success' : 'error'}
          text={status === 'pass' ? '通过' : '未通过'}
        />
      ),
    },
  ];

  const severityConfig = {
    high: { color: 'red', text: '高风险' },
    medium: { color: 'orange', text: '中风险' },
    low: { color: 'blue', text: '低风险' },
  };

  return (
    <div>
      <Title level={3}><SafetyCertificateOutlined /> 合规认证报告</Title>
      <Text type="secondary" style={{ display: 'block', marginBottom: 24 }}>
        基于评测结果生成合规认证报告，检查金融数据、监管合规、数据安全等维度
      </Text>

      <Card style={{ marginBottom: 24 }}>
        <Space>
          <Input
            placeholder="请输入评测ID"
            value={evaluationId}
            onChange={(e) => setEvaluationId(e.target.value)}
            style={{ width: 300 }}
            onPressEnter={generateReport}
          />
          <Button type="primary" onClick={generateReport} loading={loading}>
            生成报告
          </Button>
        </Space>
      </Card>

      {loading && (
        <div style={{ textAlign: 'center', padding: 60 }}>
          <Spin size="large" tip="正在生成合规报告..." />
        </div>
      )}

      {data && !loading && (
        <>
          {/* 总体合规状态 */}
          <Row gutter={16} style={{ marginBottom: 24 }}>
            <Col span={8}>
              <Card>
                <div style={{ textAlign: 'center' }}>
                  {(() => {
                    const cfg = getOverallConfig(data.overall_compliance);
                    return (
                      <>
                        <div style={{ fontSize: 48, color: cfg.color, marginBottom: 12 }}>
                          {cfg.icon}
                        </div>
                        <Tag color={cfg.color} style={{ fontSize: 16, padding: '4px 16px' }}>
                          {cfg.text}
                        </Tag>
                      </>
                    );
                  })()}
                </div>
              </Card>
            </Col>
            <Col span={8}>
              <Card>
                <Statistic
                  title="合规评分"
                  value={data.compliance_score}
                  precision={1}
                  suffix="/ 100"
                  valueStyle={{
                    color: data.compliance_score >= 80 ? '#52c41a' : data.compliance_score >= 60 ? '#faad14' : '#ff4d4f',
                  }}
                />
              </Card>
            </Col>
            <Col span={8}>
              <Card>
                <Statistic
                  title="检查项通过率"
                  value={data.checks ? Math.round(data.checks.filter(c => c.status === 'pass').length / data.checks.length * 100) : 0}
                  suffix="%"
                  valueStyle={{ color: '#1677ff' }}
                />
              </Card>
            </Col>
          </Row>

          {/* 摘要 */}
          <Alert
            message="合规摘要"
            description={data.summary}
            type={data.overall_compliance === 'pass' ? 'success' : data.overall_compliance === 'conditional_pass' ? 'warning' : 'error'}
            showIcon
            style={{ marginBottom: 24 }}
          />

          {/* 检查项表格 */}
          <Card title="合规检查项详情" style={{ marginBottom: 24 }}>
            <Table
              dataSource={data.checks}
              columns={checkColumns}
              rowKey="id"
              pagination={false}
              size="middle"
            />
          </Card>

          {/* 风险项 */}
          {data.risk_items && data.risk_items.length > 0 && (
            <Card title="风险项" style={{ marginBottom: 24 }}>
              <List
                dataSource={data.risk_items}
                renderItem={(item) => {
                  const sev = severityConfig[item.severity] || severityConfig.medium;
                  return (
                    <List.Item>
                      <List.Item.Meta
                        title={
                          <Space>
                            <Tag color={sev.color}>{sev.text}</Tag>
                            <Text strong>{item.check_name}</Text>
                            <Text type="secondary">({item.check_id})</Text>
                          </Space>
                        }
                        description={
                          <div>
                            <Text>{item.description}</Text>
                            <br />
                            <Text type="secondary">建议: {item.suggestion}</Text>
                          </div>
                        }
                      />
                    </List.Item>
                  );
                }}
              />
            </Card>
          )}

          {/* 生成时间 */}
          <Text type="secondary">
            报告生成时间: {data.generated_at ? new Date(data.generated_at).toLocaleString('zh-CN') : '-'}
          </Text>
        </>
      )}
    </div>
  );
};

export default CompliancePage;
