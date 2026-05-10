import React, { useState, useEffect } from 'react';
import {
  Card, Form, Input, Button, List, Tag, Typography,
  Switch, message, Divider, Space, Alert, InputNumber, Descriptions, Badge,
} from 'antd';
import {
  KeyOutlined, CloudServerOutlined, InfoCircleOutlined,
  SaveOutlined, ReloadOutlined, ControlOutlined,
  ClockCircleOutlined, DashboardOutlined,
} from '@ant-design/icons';

const { Title, Text, Paragraph } = Typography;

// 模拟MCP服务器数据
const mockMCPServers = [
  { name: 'tushare', status: 'running', description: 'Tushare金融数据接口', uptime: '2天3小时' },
  { name: 'yahoo_finance', status: 'running', description: 'Yahoo Finance数据接口', uptime: '2天3小时' },
  { name: 'calculator', status: 'running', description: '金融计算器工具', uptime: '2天3小时' },
  { name: 'web_search', status: 'stopped', description: '网络搜索工具', uptime: '-' },
  { name: 'sec_edgar', status: 'running', description: 'SEC EDGAR文件查询', uptime: '1天12小时' },
  { name: 'fund_data', status: 'error', description: '基金数据查询', uptime: '-' },
  { name: 'ashare_data', status: 'running', description: 'A股行情数据', uptime: '2天3小时' },
  { name: 'filesystem', status: 'running', description: '文件系统操作', uptime: '2天3小时' },
];

const mockSystemInfo = {
  version: '1.0.0',
  uptime: '2天3小时15分钟',
  database: 'PostgreSQL 16.4 (已连接)',
  pythonVersion: '3.10.12',
  cpuUsage: '23%',
  memoryUsage: '1.2 GB / 8 GB',
};

const Settings = () => {
  const [apiKeys, setApiKeys] = useState({
    openai: 'sk-****************************a3F2',
    anthropic: 'sk-ant-****************************k8D1',
    deepseek: 'sk-****************************m7E4',
  });
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);

  // 流水线配置状态
  const [pipelineConfig, setPipelineConfig] = useState({
    enable_three_stage: true,
    checkpoint_interval: 10,
    max_concurrent_tasks: 5,
  });

  // 响应时间配置状态
  const [responseTimeConfig, setResponseTimeConfig] = useState({
    p95_threshold: 500,
    request_timeout: 5000,
    enable_timeout_interrupt: true,
  });

  // 调度器状态模拟数据
  const mockSchedulerStatus = {
    mode: 'distributed',
    queue_size: 8,
    running_count: 3,
    redis_connected: true,
  };

  const handleSaveKeys = () => {
    form.validateFields().then((values) => {
      setSaving(true);
      setTimeout(() => {
        setApiKeys({
          openai: values.openai_key ? `sk-****************************${values.openai_key.slice(-4)}` : apiKeys.openai,
          anthropic: values.anthropic_key ? `sk-ant-****************************${values.anthropic_key.slice(-4)}` : apiKeys.anthropic,
          deepseek: values.deepseek_key ? `sk-****************************${values.deepseek_key.slice(-4)}` : apiKeys.deepseek,
        });
        setSaving(false);
        form.resetFields();
        message.success('API密钥已保存');
      }, 1000);
    });
  };

  const mcpStatusMap = {
    running: { color: 'success', text: '运行中' },
    stopped: { color: 'default', text: '已停止' },
    error: { color: 'error', text: '异常' },
  };

  return (
    <div>
      <div className="page-header">
        <Title level={4}>系统设置</Title>
        <p>管理API密钥、MCP服务器和系统配置</p>
      </div>

      {/* API密钥配置 */}
      <Card
        title={
          <Space>
            <KeyOutlined />
            <span>API密钥配置</span>
          </Space>
        }
        style={{ marginBottom: 16 }}
      >
        <Alert
          type="info"
          message="API密钥用于LLM评判和任务生成，请妥善保管"
          showIcon
          style={{ marginBottom: 16 }}
        />
        <Form form={form} layout="vertical">
          <Form.Item label="OpenAI API Key">
            <Input.Password
              name="openai_key"
              placeholder={apiKeys.openai}
              visibilityToggle={false}
            />
            <Text type="secondary" style={{ fontSize: 12 }}>
              当前: {apiKeys.openai}
            </Text>
          </Form.Item>
          <Form.Item label="Anthropic API Key">
            <Input.Password
              name="anthropic_key"
              placeholder={apiKeys.anthropic}
              visibilityToggle={false}
            />
            <Text type="secondary" style={{ fontSize: 12 }}>
              当前: {apiKeys.anthropic}
            </Text>
          </Form.Item>
          <Form.Item label="DeepSeek API Key">
            <Input.Password
              name="deepseek_key"
              placeholder={apiKeys.deepseek}
              visibilityToggle={false}
            />
            <Text type="secondary" style={{ fontSize: 12 }}>
              当前: {apiKeys.deepseek}
            </Text>
          </Form.Item>
          <Form.Item>
            <Button
              type="primary"
              icon={<SaveOutlined />}
              loading={saving}
              onClick={handleSaveKeys}
            >
              保存密钥
            </Button>
          </Form.Item>
        </Form>
      </Card>

      {/* MCP服务器状态 */}
      <Card
        title={
          <Space>
            <CloudServerOutlined />
            <span>MCP服务器状态</span>
          </Space>
        }
        style={{ marginBottom: 16 }}
      >
        <List
          dataSource={mockMCPServers}
          renderItem={(server) => {
            const statusInfo = mcpStatusMap[server.status] || mcpStatusMap.stopped;
            return (
              <List.Item
                actions={[
                  <Tag color={statusInfo.color} key="status">
                    {statusInfo.text}
                  </Tag>,
                  <Button
                    key="restart"
                    type="link"
                    size="small"
                    icon={<ReloadOutlined />}
                    disabled={server.status === 'running'}
                    onClick={() => message.success(`正在重启 ${server.name}...`)}
                  >
                    重启
                  </Button>,
                ]}
              >
                <List.Item.Meta
                  title={
                    <Space>
                      <Text strong>{server.name}</Text>
                    </Space>
                  }
                  description={
                    <Space split="|" size="small">
                      <Text type="secondary">{server.description}</Text>
                      <Text type="secondary">运行时间: {server.uptime}</Text>
                    </Space>
                  }
                />
              </List.Item>
            );
          }}
        />
      </Card>

      {/* 系统信息 */}
      <Card
        title={
          <Space>
            <InfoCircleOutlined />
            <span>系统信息</span>
          </Space>
        }
        style={{ marginBottom: 16 }}
      >
        <List
          dataSource={[
            { label: '系统版本', value: mockSystemInfo.version },
            { label: '运行时间', value: mockSystemInfo.uptime },
            { label: '数据库状态', value: mockSystemInfo.database },
            { label: 'Python版本', value: mockSystemInfo.pythonVersion },
            { label: 'CPU使用率', value: mockSystemInfo.cpuUsage },
            { label: '内存使用', value: mockSystemInfo.memoryUsage },
          ]}
          renderItem={(item) => (
            <List.Item>
              <Text type="secondary" style={{ minWidth: 120 }}>{item.label}</Text>
              <Text strong>{item.value}</Text>
            </List.Item>
          )}
        />
      </Card>

      {/* 流水线配置 */}
      <Card
        title={
          <Space>
            <ControlOutlined />
            <span>流水线配置</span>
          </Space>
        }
        style={{ marginBottom: 16 }}
      >
        <Alert
          type="info"
          message="三阶段流水线将评测分为静态评估、动态评估和可信度评估三个阶段依次执行"
          showIcon
          style={{ marginBottom: 16 }}
        />
        <List
          dataSource={[
            {
              label: '三阶段流水线',
              description: '启用后将按 STATIC -> DYNAMIC -> TRUST 顺序执行评测',
              content: (
                <Switch
                  checked={pipelineConfig.enable_three_stage}
                  onChange={(checked) => {
                    setPipelineConfig({ ...pipelineConfig, enable_three_stage: checked });
                    message.success(checked ? '已启用三阶段流水线' : '已关闭三阶段流水线');
                  }}
                  checkedChildren="启用"
                  unCheckedChildren="关闭"
                />
              ),
            },
            {
              label: '检查点间隔',
              description: '每隔多少个任务保存一次检查点',
              content: (
                <InputNumber
                  min={1}
                  max={100}
                  value={pipelineConfig.checkpoint_interval}
                  onChange={(value) => {
                    setPipelineConfig({ ...pipelineConfig, checkpoint_interval: value });
                  }}
                  addonAfter="个任务"
                />
              ),
            },
            {
              label: '最大并发任务数',
              description: '同时执行的最大评测任务数量',
              content: (
                <InputNumber
                  min={1}
                  max={20}
                  value={pipelineConfig.max_concurrent_tasks}
                  onChange={(value) => {
                    setPipelineConfig({ ...pipelineConfig, max_concurrent_tasks: value });
                  }}
                  addonAfter="个"
                />
              ),
            },
          ]}
          renderItem={(item) => (
            <List.Item actions={[item.content]}>
              <List.Item.Meta
                title={<Text strong>{item.label}</Text>}
                description={item.description}
              />
            </List.Item>
          )}
        />
      </Card>

      {/* 响应时间配置 */}
      <Card
        title={
          <Space>
            <ClockCircleOutlined />
            <span>响应时间配置</span>
          </Space>
        }
        style={{ marginBottom: 16 }}
      >
        <Alert
          type="info"
          message="配置API响应时间监控阈值，超过阈值将触发告警"
          showIcon
          style={{ marginBottom: 16 }}
        />
        <List
          dataSource={[
            {
              label: 'P95 阈值',
              description: 'API响应时间P95告警阈值',
              content: (
                <InputNumber
                  min={100}
                  max={10000}
                  step={50}
                  value={responseTimeConfig.p95_threshold}
                  onChange={(value) => {
                    setResponseTimeConfig({ ...responseTimeConfig, p95_threshold: value });
                  }}
                  addonAfter="ms"
                />
              ),
            },
            {
              label: '请求超时',
              description: '单个API请求的超时时间',
              content: (
                <InputNumber
                  min={1000}
                  max={60000}
                  step={1000}
                  value={responseTimeConfig.request_timeout}
                  onChange={(value) => {
                    setResponseTimeConfig({ ...responseTimeConfig, request_timeout: value });
                  }}
                  addonAfter="ms"
                />
              ),
            },
            {
              label: '启用超时中断',
              description: '请求超时后是否自动中断评测任务',
              content: (
                <Switch
                  checked={responseTimeConfig.enable_timeout_interrupt}
                  onChange={(checked) => {
                    setResponseTimeConfig({ ...responseTimeConfig, enable_timeout_interrupt: checked });
                    message.success(checked ? '已启用超时中断' : '已关闭超时中断');
                  }}
                  checkedChildren="启用"
                  unCheckedChildren="关闭"
                />
              ),
            },
          ]}
          renderItem={(item) => (
            <List.Item actions={[item.content]}>
              <List.Item.Meta
                title={<Text strong>{item.label}</Text>}
                description={item.description}
              />
            </List.Item>
          )}
        />
      </Card>

      {/* 调度器状态 */}
      <Card
        title={
          <Space>
            <DashboardOutlined />
            <span>调度器状态</span>
          </Space>
        }
      >
        <Descriptions bordered column={{ xs: 1, sm: 2 }}>
          <Descriptions.Item label="调度模式">
            <Tag color={mockSchedulerStatus.mode === 'distributed' ? 'blue' : 'green'}>
              {mockSchedulerStatus.mode === 'distributed' ? '分布式 (Redis)' : '内存模式'}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="队列大小">
            <Text strong>{mockSchedulerStatus.queue_size}</Text>
          </Descriptions.Item>
          <Descriptions.Item label="运行中任务数">
            <Text strong style={{ color: '#52c41a' }}>{mockSchedulerStatus.running_count}</Text>
          </Descriptions.Item>
          <Descriptions.Item label="Redis 连接状态">
            <Badge
              status={mockSchedulerStatus.redis_connected ? 'success' : 'error'}
              text={mockSchedulerStatus.redis_connected ? '已连接' : '未连接'}
            />
          </Descriptions.Item>
        </Descriptions>
      </Card>
    </div>
  );
};

export default Settings;
