import React, { useState, useEffect, useMemo } from 'react';
import {
  Table, Modal, Form, Select, Input, Popconfirm, Button,
  Tag, Typography, Card, Space, message,
} from 'antd';
import {
  PlusOutlined, DeleteOutlined, ReloadOutlined,
  RobotOutlined, LinkOutlined,
} from '@ant-design/icons';
import { useAgents, agentApi } from '../hooks/useApi';
import { EmptyStates } from '../components/EmptyStates';

const { Title, Text } = Typography;
const { TextArea } = Input;

// 模拟Agent数据 - 作为API失败时的fallback
const mockAgents = [
  { id: 'agent-001', name: '智能投顾Agent', type: 'langgraph', status: 'active', endpoint: 'http://localhost:8001', lastEvaluated: '2025-01-15 14:30', description: '基于LangGraph的智能投资顾问' },
  { id: 'agent-002', name: '量化研究Agent', type: 'autogen', status: 'active', endpoint: 'http://localhost:8002', lastEvaluated: '2025-01-15 13:20', description: '基于AutoGen的量化研究助手' },
  { id: 'agent-003', name: '风控分析Agent', type: 'crewai', status: 'active', endpoint: 'http://localhost:8003', lastEvaluated: '2025-01-15 12:00', description: '基于CrewAI的风控分析系统' },
  { id: 'agent-004', name: '交易执行Agent', type: 'http', status: 'inactive', endpoint: 'http://localhost:8004', lastEvaluated: '2025-01-10 09:00', description: 'HTTP接口交易执行Agent' },
  { id: 'agent-005', name: '财务分析Agent', type: 'langgraph', status: 'active', endpoint: 'http://localhost:8005', lastEvaluated: '2025-01-14 16:30', description: '基于LangGraph的财务分析助手' },
  { id: 'agent-006', name: '合规检查Agent', type: 'http', status: 'active', endpoint: 'http://localhost:8006', lastEvaluated: '2025-01-14 15:00', description: 'HTTP接口合规检查Agent' },
];

const typeLabels = {
  langgraph: 'LangGraph',
  autogen: 'AutoGen',
  crewai: 'CrewAI',
  http: 'HTTP接口',
};

const typeColors = {
  langgraph: 'blue',
  autogen: 'green',
  crewai: 'purple',
  http: 'orange',
};

const AgentManagement = () => {
  // 使用自定义hooks获取真实数据
  const { data: apiAgents, loading: agentsLoading, setData: setAgents } = useAgents();
  
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm();

  // 使用API数据，如果失败则使用mock数据
  const data = useMemo(() => {
    if (apiAgents && apiAgents.length > 0) {
      return apiAgents.map(agent => ({
        id: agent.id || agent.agent_id,
        name: agent.name || agent.agent_name,
        type: agent.type || agent.agent_type,
        status: agent.status || 'active',
        endpoint: agent.endpoint || agent.endpoint_url,
        lastEvaluated: agent.last_evaluated || agent.lastEvaluated || '-',
        description: agent.description || '',
      }));
    }
    return mockAgents;
  }, [apiAgents]);

  const handleRegister = async () => {
    try {
      const values = await form.validateFields();
      let config = {};
      try {
        config = values.config ? JSON.parse(values.config) : {};
      } catch {
        message.error('配置JSON格式错误');
        return;
      }

      // 调用真实API
      try {
        const result = await agentApi.register({
          agent_id: values.agent_id,
          agent_name: values.agent_name,
          agent_type: values.agent_type,
          endpoint_url: values.endpoint_url,
          description: values.description,
          config: config,
        });
        
        // 刷新列表
        setAgents([result, ...data]);
        setModalOpen(false);
        form.resetFields();
        message.success('Agent注册成功');
      } catch (apiError) {
        // API调用失败，使用本地模拟
        console.warn('API调用失败，使用本地模拟:', apiError.message);
        const newAgent = {
          id: values.agent_id,
          name: values.agent_name,
          type: values.agent_type,
          status: 'active',
          endpoint: values.endpoint_url,
          lastEvaluated: '-',
          description: values.description || '',
        };
        setAgents([newAgent, ...data]);
        setModalOpen(false);
        form.resetFields();
        message.success('Agent注册成功 (离线模式)');
      }
    } catch (error) {
      console.error('表单验证失败:', error);
    }
  };

  const handleUnregister = async (id) => {
    try {
      // 调用真实API
      await agentApi.delete(id);
      setAgents(data.filter((item) => item.id !== id));
      message.success('Agent已注销');
    } catch (apiError) {
      // API调用失败，使用本地模拟
      console.warn('API调用失败，使用本地模拟:', apiError.message);
      setAgents(data.filter((item) => item.id !== id));
      message.success('Agent已注销 (离线模式)');
    }
  };

  const columns = [
    {
      title: 'Agent名称', dataIndex: 'name', key: 'name',
      render: (name, record) => (
        <Space>
          <RobotOutlined style={{ color: '#1677ff' }} />
          <div>
            <Text strong>{name}</Text>
            <br />
            <Text type="secondary" style={{ fontSize: 12 }}>{record.id}</Text>
          </div>
        </Space>
      ),
    },
    {
      title: '类型', dataIndex: 'type', key: 'type', width: 120,
      render: (type) => <Tag color={typeColors[type]}>{typeLabels[type] || type}</Tag>,
    },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 100,
      render: (status) => (
        <Tag color={status === 'active' ? 'success' : 'default'}>
          {status === 'active' ? '活跃' : '未激活'}
        </Tag>
      ),
    },
    {
      title: '端点地址', dataIndex: 'endpoint', key: 'endpoint', ellipsis: true,
      render: (url) => (
        <Space>
          <LinkOutlined />
          <Text copyable style={{ fontSize: 12 }}>{url}</Text>
        </Space>
      ),
    },
    {
      title: '最近评测', dataIndex: 'lastEvaluated', key: 'lastEvaluated', width: 160,
      render: (time) => time === '-' ? <Text type="secondary">暂无</Text> : time,
    },
    {
      title: '操作', key: 'actions', width: 120, fixed: 'right',
      render: (_, record) => (
        <Popconfirm
          title="确认注销"
          description={`确定要注销 ${record.name} 吗？此操作不可撤销。`}
          onConfirm={() => handleUnregister(record.id)}
          okText="确认"
          cancelText="取消"
          okButtonProps={{ danger: true }}
        >
          <Button type="link" danger icon={<DeleteOutlined />} size="small">
            注销
          </Button>
        </Popconfirm>
      ),
    },
  ];

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <Title level={4}>Agent管理</Title>
          <p>注册和管理待评测的金融AI Agent</p>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
          注册Agent
        </Button>
      </div>

      <Card>
        {data.length === 0 && !agentsLoading ? (
          EmptyStates.noAgents(() => setModalOpen(true))
        ) : (
          <Table
            columns={columns}
            dataSource={data}
            rowKey="id"
            loading={agentsLoading}
            pagination={{
              total: data.length,
              pageSize: 10,
              showTotal: (total) => `共 ${total} 个Agent`,
            }}
            scroll={{ x: 800 }}
          />
        )}
      </Card>

      {/* 注册Agent弹窗 */}
      <Modal
        title="注册新Agent"
        open={modalOpen}
        onOk={handleRegister}
        onCancel={() => { setModalOpen(false); form.resetFields(); }}
        okText="注册"
        cancelText="取消"
        width={560}
        destroyOnClose
      >
        <Form form={form} layout="vertical" className="modal-form">
          <Form.Item
            name="agent_id"
            label="Agent ID"
            rules={[{ required: true, message: '请输入Agent ID' }]}
            tooltip="Agent的唯一标识符"
          >
            <Input placeholder="例如: my-finance-agent" />
          </Form.Item>
          <Form.Item
            name="agent_name"
            label="Agent名称"
            rules={[{ required: true, message: '请输入Agent名称' }]}
          >
            <Input placeholder="例如: 智能投顾Agent" />
          </Form.Item>
          <Form.Item
            name="agent_type"
            label="Agent类型"
            rules={[{ required: true, message: '请选择Agent类型' }]}
          >
            <Select
              placeholder="请选择Agent框架类型"
              options={[
                { label: 'LangGraph', value: 'langgraph' },
                { label: 'AutoGen', value: 'autogen' },
                { label: 'CrewAI', value: 'crewai' },
                { label: 'HTTP接口', value: 'http' },
              ]}
            />
          </Form.Item>
          <Form.Item
            name="endpoint_url"
            label="端点URL"
            rules={[{ required: true, message: '请输入Agent端点URL' }]}
            tooltip="Agent的HTTP服务地址"
          >
            <Input placeholder="例如: http://localhost:8001" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input placeholder="简要描述Agent的功能" />
          </Form.Item>
          <Form.Item
            name="config"
            label="配置 (JSON)"
            tooltip="Agent的额外配置，以JSON格式输入"
          >
            <TextArea
              rows={4}
              placeholder='{"llm_backend": "gpt-4o", "max_tokens": 4096}'
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default AgentManagement;
