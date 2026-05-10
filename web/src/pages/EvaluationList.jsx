import React, { useState, useEffect, useMemo } from 'react';
import {
  Table, Button, Modal, Form, Select, DatePicker, Tag,
  Space, Input, message, Row, Col, Card, Typography, Switch,
} from 'antd';
import {
  PlusOutlined, ReloadOutlined, StopOutlined, EyeOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import dayjs from 'dayjs';
import StatusTag from '../components/StatusTag';
import ScoreBadge from '../components/ScoreBadge';
import { useEvaluations, useAgents, evaluationApi } from '../hooks/useApi';
import { EmptyStates } from '../components/EmptyStates';

const { Title } = Typography;
const { RangePicker } = DatePicker;

// 模拟数据 - 作为API失败时的fallback
const mockEvaluations = [
  { id: 'eval-001', agent: '智能投顾Agent', agentId: 'agent-001', mode: 'full', status: 'completed', score: 85.2, rating: 'A', created: '2025-01-15 14:30:00', current_phase: 'trust', enable_three_stage: true },
  { id: 'eval-002', agent: '量化研究Agent', agentId: 'agent-002', mode: 'quick', status: 'completed', score: 72.1, rating: 'B', created: '2025-01-15 13:20:00', current_phase: null, enable_three_stage: false },
  { id: 'eval-003', agent: '风控分析Agent', agentId: 'agent-003', mode: 'full', status: 'running', score: null, rating: null, created: '2025-01-15 12:00:00', current_phase: 'dynamic', enable_three_stage: true },
  { id: 'eval-004', agent: '交易执行Agent', agentId: 'agent-004', mode: 'quick', status: 'failed', score: 45.0, rating: 'D', created: '2025-01-15 10:45:00', current_phase: 'static', enable_three_stage: true },
  { id: 'eval-005', agent: '财务分析Agent', agentId: 'agent-005', mode: 'full', status: 'completed', score: 91.5, rating: 'S', created: '2025-01-14 16:30:00', current_phase: 'trust', enable_three_stage: true },
  { id: 'eval-006', agent: '合规检查Agent', agentId: 'agent-006', mode: 'quick', status: 'completed', score: 68.3, rating: 'C', created: '2025-01-14 15:00:00', current_phase: null, enable_three_stage: false },
  { id: 'eval-007', agent: '新闻解读Agent', agentId: 'agent-007', mode: 'full', status: 'completed', score: 78.9, rating: 'B', created: '2025-01-14 11:20:00', current_phase: 'trust', enable_three_stage: true },
  { id: 'eval-008', agent: '资产配置Agent', agentId: 'agent-008', mode: 'quick', status: 'pending', score: null, rating: null, created: '2025-01-14 09:00:00', current_phase: null, enable_three_stage: false },
  { id: 'eval-009', agent: '行情分析Agent', agentId: 'agent-009', mode: 'full', status: 'completed', score: 82.6, rating: 'A', created: '2025-01-13 17:00:00', current_phase: 'trust', enable_three_stage: true },
  { id: 'eval-010', agent: '信用评估Agent', agentId: 'agent-010', mode: 'quick', status: 'completed', score: 55.2, rating: 'C', created: '2025-01-13 14:30:00', current_phase: null, enable_three_stage: false },
  { id: 'eval-011', agent: '智能投顾Agent', agentId: 'agent-001', mode: 'quick', status: 'completed', score: 88.0, rating: 'A', created: '2025-01-13 10:00:00', current_phase: null, enable_three_stage: false },
  { id: 'eval-012', agent: '量化研究Agent', agentId: 'agent-002', mode: 'full', status: 'completed', score: 70.5, rating: 'B', created: '2025-01-12 16:00:00', current_phase: 'trust', enable_three_stage: true },
];

const mockAgents = [
  { id: 'agent-001', name: '智能投顾Agent' },
  { id: 'agent-002', name: '量化研究Agent' },
  { id: 'agent-003', name: '风控分析Agent' },
  { id: 'agent-004', name: '交易执行Agent' },
  { id: 'agent-005', name: '财务分析Agent' },
];

const EvaluationList = () => {
  // 使用自定义hooks获取真实数据
  const { data: apiEvaluations, loading: evalLoading, refetch: refetchEvaluations, setData: setEvaluations } = useEvaluations();
  const { data: apiAgents, loading: agentsLoading } = useAgents();
  
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm();
  const navigate = useNavigate();

  // 筛选状态
  const [statusFilter, setStatusFilter] = useState(null);
  const [modeFilter, setModeFilter] = useState(null);
  const [dateRange, setDateRange] = useState(null);
  const [searchText, setSearchText] = useState('');

  // 使用API数据，如果失败则使用mock数据
  const evaluations = useMemo(() => {
    if (apiEvaluations && apiEvaluations.length > 0) {
      return apiEvaluations.map(item => ({
        id: item.id || item.evaluation_id,
        agent: item.agent_name || item.agent,
        agentId: item.agent_id || item.agentId,
        mode: item.mode || item.eval_mode,
        status: item.status,
        score: item.overall_score ?? item.score,
        rating: item.overall_rating ?? item.rating,
        created: item.created_at || item.created,
        current_phase: item.current_phase,
        enable_three_stage: item.enable_three_stage,
      }));
    }
    return mockEvaluations;
  }, [apiEvaluations]);

  const agents = useMemo(() => {
    if (apiAgents && apiAgents.length > 0) {
      return apiAgents.map(agent => ({
        id: agent.id || agent.agent_id,
        name: agent.name || agent.agent_name,
      }));
    }
    return mockAgents;
  }, [apiAgents]);

  const filteredData = evaluations.filter((item) => {
    if (statusFilter && item.status !== statusFilter) return false;
    if (modeFilter && item.mode !== modeFilter) return false;
    if (searchText && !item.agent.includes(searchText) && !item.id.includes(searchText)) return false;
    if (dateRange) {
      const created = dayjs(item.created);
      if (created.isBefore(dateRange[0]) || created.isAfter(dateRange[1])) return false;
    }
    return true;
  });

  const handleNewEvaluation = async () => {
    try {
      const values = await form.validateFields();
      
      // 调用真实API
      try {
        const result = await evaluationApi.start({
          agent_id: values.agent_id,
          eval_mode: values.eval_mode,
          task_count: values.task_count,
          enable_three_stage: values.enable_three_stage || false,
        });
        
        // 刷新列表
        refetchEvaluations();
        setModalOpen(false);
        form.resetFields();
        message.success('评测任务已创建');
      } catch (apiError) {
        // API调用失败，使用本地模拟
        console.warn('API调用失败，使用本地模拟:', apiError.message);
        const newEval = {
          id: `eval-${String(evaluations.length + 1).padStart(3, '0')}`,
          agent: agents.find((a) => a.id === values.agent_id)?.name || values.agent_id,
          agentId: values.agent_id,
          mode: values.eval_mode,
          status: 'pending',
          score: null,
          rating: null,
          created: dayjs().format('YYYY-MM-DD HH:mm:ss'),
          current_phase: values.enable_three_stage ? 'static' : null,
          enable_three_stage: values.enable_three_stage || false,
        };
        setEvaluations([newEval, ...evaluations]);
        setModalOpen(false);
        form.resetFields();
        message.success('评测任务已创建 (离线模式)');
      }
    } catch (error) {
      console.error('表单验证失败:', error);
    }
  };

  const handleCancel = async (id) => {
    try {
      // 调用真实API
      await evaluationApi.cancel(id);
      message.info('评测任务已取消');
      refetchEvaluations();
    } catch (apiError) {
      // API调用失败，使用本地模拟
      console.warn('API调用失败，使用本地模拟:', apiError.message);
      setEvaluations(evaluations.map((item) =>
        item.id === id ? { ...item, status: 'cancelled' } : item
      ));
      message.info('评测任务已取消 (离线模式)');
    }
  };

  const handleRerun = async (record) => {
    try {
      // 调用真实API重新发起评测
      await evaluationApi.start({
        agent_id: record.agentId,
        eval_mode: record.mode,
        enable_three_stage: record.enable_three_stage,
      });
      message.success('已重新发起评测');
      refetchEvaluations();
    } catch (apiError) {
      // API调用失败，使用本地模拟
      console.warn('API调用失败，使用本地模拟:', apiError.message);
      const rerunEval = {
        ...record,
        id: `eval-${String(evaluations.length + 1).padStart(3, '0')}`,
        status: 'pending',
        score: null,
        rating: null,
        created: dayjs().format('YYYY-MM-DD HH:mm:ss'),
      };
      setEvaluations([rerunEval, ...evaluations]);
      message.success('已重新发起评测 (离线模式)');
    }
  };

  const modeLabels = { full: '完整评测', quick: '快速评测' };

  const columns = [
    { title: '评测ID', dataIndex: 'id', key: 'id', width: 110 },
    { title: 'Agent名称', dataIndex: 'agent', key: 'agent', ellipsis: true },
    {
      title: '评测模式', dataIndex: 'mode', key: 'mode', width: 100,
      render: (mode) => <Tag>{modeLabels[mode] || mode}</Tag>,
    },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 100,
      render: (status) => <StatusTag status={status} />,
    },
    {
      title: '当前阶段', dataIndex: 'current_phase', key: 'current_phase', width: 110,
      render: (phase, record) => {
        if (!record.enable_three_stage) return <Tag type="secondary">未启用</Tag>;
        if (!phase) return <Tag>等待中</Tag>;
        const phaseStatusKey = `${phase}_eval`;
        return <StatusTag status={phaseStatusKey} />;
      },
    },
    {
      title: '评分', key: 'score', width: 110,
      render: (_, record) => record.score !== null && record.score !== undefined
        ? <ScoreBadge rating={record.rating} score={record.score} />
        : '-',
    },
    { title: '创建时间', dataIndex: 'created', key: 'created', width: 170 },
    {
      title: '操作', key: 'actions', width: 180, fixed: 'right',
      render: (_, record) => (
        <Space size="small">
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => navigate(`/evaluations/${record.id}`)}
          >
            详情
          </Button>
          {record.status === 'running' && (
            <Button
              type="link"
              size="small"
              danger
              icon={<StopOutlined />}
              onClick={() => handleCancel(record.id)}
            >
              取消
            </Button>
          )}
          {(record.status === 'completed' || record.status === 'failed') && (
            <Button
              type="link"
              size="small"
              icon={<ReloadOutlined />}
              onClick={() => handleRerun(record)}
            >
              重跑
            </Button>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div className="page-header">
        <Title level={4}>评测管理</Title>
        <p>管理所有评测任务，创建新评测或查看历史结果</p>
      </div>

      {/* 筛选栏 */}
      <Card style={{ marginBottom: 16 }}>
        <Row gutter={[16, 12]} align="middle">
          <Col xs={24} sm={8} md={6}>
            <Input
              placeholder="搜索Agent名称或ID"
              prefix={<SearchOutlined />}
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              allowClear
            />
          </Col>
          <Col xs={12} sm={6} md={4}>
            <Select
              placeholder="状态筛选"
              allowClear
              style={{ width: '100%' }}
              value={statusFilter}
              onChange={setStatusFilter}
              options={[
                { label: '等待中', value: 'pending' },
                { label: '运行中', value: 'running' },
                { label: '已完成', value: 'completed' },
                { label: '失败', value: 'failed' },
                { label: '已取消', value: 'cancelled' },
              ]}
            />
          </Col>
          <Col xs={12} sm={6} md={4}>
            <Select
              placeholder="模式筛选"
              allowClear
              style={{ width: '100%' }}
              value={modeFilter}
              onChange={setModeFilter}
              options={[
                { label: '完整评测', value: 'full' },
                { label: '快速评测', value: 'quick' },
              ]}
            />
          </Col>
          <Col xs={24} sm={8} md={6}>
            <RangePicker
              style={{ width: '100%' }}
              onChange={(dates) => setDateRange(dates)}
              placeholder={['开始日期', '结束日期']}
            />
          </Col>
          <Col xs={24} sm={24} md={4} style={{ textAlign: 'right' }}>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => setModalOpen(true)}
            >
              新建评测
            </Button>
          </Col>
        </Row>
      </Card>

      {/* 评测列表 */}
      <Card>
        {filteredData.length === 0 && !evalLoading ? (
          EmptyStates.noEvaluations(() => setModalOpen(true))
        ) : (
          <Table
            columns={columns}
            dataSource={filteredData}
            rowKey="id"
            loading={evalLoading}
            pagination={{
              total: filteredData.length,
              pageSize: 10,
              showTotal: (total) => `共 ${total} 条记录`,
              showSizeChanger: true,
            }}
            scroll={{ x: 900 }}
          />
        )}
      </Card>

      {/* 新建评测弹窗 */}
      <Modal
        title="新建评测"
        open={modalOpen}
        onOk={handleNewEvaluation}
        onCancel={() => { setModalOpen(false); form.resetFields(); }}
        okText="创建"
        cancelText="取消"
        destroyOnClose
      >
        <Form form={form} layout="vertical" className="modal-form">
          <Form.Item
            name="agent_id"
            label="选择Agent"
            rules={[{ required: true, message: '请选择Agent' }]}
          >
            <Select placeholder="请选择要评测的Agent" loading={agentsLoading}>
              {agents.map((agent) => (
                <Select.Option key={agent.id} value={agent.id}>
                  {agent.name}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item
            name="eval_mode"
            label="评测模式"
            initialValue="full"
            rules={[{ required: true, message: '请选择评测模式' }]}
          >
            <Select
              options={[
                { label: '完整评测 (11个维度)', value: 'full' },
                { label: '快速评测 (5个核心维度)', value: 'quick' },
              ]}
            />
          </Form.Item>
          <Form.Item name="task_count" label="任务数量">
            <Select
              placeholder="默认使用标准配置"
              allowClear
              options={[
                { label: '10个任务', value: 10 },
                { label: '20个任务', value: 20 },
                { label: '50个任务', value: 50 },
              ]}
            />
          </Form.Item>
          <Form.Item
            name="enable_three_stage"
            label="启用三阶段流水线"
            valuePropName="checked"
            initialValue={false}
          >
            <Switch
              checkedChildren="启用"
              unCheckedChildren="关闭"
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default EvaluationList;
