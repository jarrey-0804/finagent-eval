import React, { useState, useEffect } from 'react';
import {
  Card, Form, Select, Button, Modal, List, Tag, Typography,
  Space, message, Spin, Descriptions,
} from 'antd';
import {
  FileTextOutlined, DownloadOutlined, EyeOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import { EmptyStates } from '../components/EmptyStates';

const { Title, Text, Paragraph } = Typography;

// 模拟评测列表
const mockEvaluations = [
  { id: 'eval-001', agent: '智能投顾Agent', date: '2025-01-15', score: 85.2, rating: 'A' },
  { id: 'eval-002', agent: '量化研究Agent', date: '2025-01-15', score: 72.1, rating: 'B' },
  { id: 'eval-003', agent: '风控分析Agent', date: '2025-01-15', score: null, rating: null },
  { id: 'eval-004', agent: '交易执行Agent', date: '2025-01-15', score: 45.0, rating: 'D' },
  { id: 'eval-005', agent: '财务分析Agent', date: '2025-01-14', score: 91.5, rating: 'S' },
];

// 模拟已有报告
const mockReports = [
  {
    id: 'rpt-001',
    evaluationId: 'eval-001',
    agent: '智能投顾Agent',
    format: 'json',
    generatedAt: '2025-01-15 16:00:00',
    size: '128 KB',
  },
  {
    id: 'rpt-002',
    evaluationId: 'eval-002',
    agent: '量化研究Agent',
    format: 'markdown',
    generatedAt: '2025-01-15 14:00:00',
    size: '85 KB',
  },
  {
    id: 'rpt-003',
    evaluationId: 'eval-005',
    agent: '财务分析Agent',
    format: 'html',
    generatedAt: '2025-01-14 17:30:00',
    size: '256 KB',
  },
];

// 模拟报告内容
const mockReportContent = {
  markdown: `# 评测报告 - 智能投顾Agent

## 概要

- **评测时间**: 2025-01-15 14:30 ~ 15:45
- **评测模式**: 完整评测 (11个维度)
- **总体评分**: 85.2 / 100
- **总体评级**: A级

## 维度评分

| 维度 | 得分 | 状态 |
|------|------|------|
| 准确性 | 88 | 通过 |
| 完整性 | 82 | 通过 |
| 推理能力 | 79 | 通过 |
| 工具使用 | 90 | 通过 |
| 专业性 | 85 | 通过 |
| 合规性 | 92 | 通过 |
| 风险意识 | 86 | 通过 |
| 鲁棒性 | 78 | 通过 |
| 安全性 | 88 | 通过 |
| 透明度 | 80 | 通过 |
| 一致性 | 84 | 通过 |

## 建议

1. 推理能力有提升空间，建议优化多步推理链路
2. 建议加强极端市场环境下的风险提示
3. 工具调用表现优秀，继续保持`,

  html: `<div style="font-family: sans-serif; padding: 20px;">
    <h1>评测报告 - 智能投顾Agent</h1>
    <h2>概要</h2>
    <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse;">
      <tr><td>评测时间</td><td>2025-01-15 14:30 ~ 15:45</td></tr>
      <tr><td>评测模式</td><td>完整评测 (11个维度)</td></tr>
      <tr><td>总体评分</td><td><strong>85.2 / 100</strong></td></tr>
      <tr><td>总体评级</td><td><span style="color: #52c41a; font-weight: bold;">A级</span></td></tr>
    </table>
    <h2>建议</h2>
    <ol>
      <li>推理能力有提升空间</li>
      <li>建议加强极端市场环境下的风险提示</li>
    </ol>
  </div>`,
};

const ReportCenter = () => {
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewContent, setPreviewContent] = useState('');
  const [previewTitle, setPreviewTitle] = useState('');
  const [form] = Form.useForm();

  useEffect(() => {
    const timer = setTimeout(() => {
      setReports(mockReports);
      setLoading(false);
    }, 500);
    return () => clearTimeout(timer);
  }, []);

  const handleGenerate = () => {
    form.validateFields().then((values) => {
      setGenerating(true);
      setTimeout(() => {
        const newReport = {
          id: `rpt-${String(reports.length + 1).padStart(3, '0')}`,
          evaluationId: values.evaluation_id,
          agent: mockEvaluations.find((e) => e.id === values.evaluation_id)?.agent || '-',
          format: values.format,
          generatedAt: dayjs().format('YYYY-MM-DD HH:mm:ss'),
          size: values.format === 'html' ? '256 KB' : values.format === 'markdown' ? '85 KB' : '128 KB',
        };
        setReports([newReport, ...reports]);
        setGenerating(false);
        form.resetFields();
        message.success('报告生成成功');
      }, 1500);
    });
  };

  const handlePreview = (report) => {
    const content = report.format === 'markdown'
      ? mockReportContent.markdown
      : report.format === 'html'
        ? mockReportContent.html
        : JSON.stringify({ summary: { overall_score: 85.2, overall_rating: 'A' } }, null, 2);

    setPreviewContent(content);
    setPreviewTitle(`${report.agent} - ${report.format.toUpperCase()}报告`);
    setPreviewOpen(true);
  };

  const handleDownload = (report) => {
    message.success(`正在下载报告: ${report.id}`);
  };

  const formatLabels = { json: 'JSON', markdown: 'Markdown', html: 'HTML' };
  const formatColors = { json: 'orange', markdown: 'blue', html: 'green' };

  return (
    <div>
      <div className="page-header">
        <Title level={4}>报告中心</Title>
        <p>生成、预览和下载评测报告</p>
      </div>

      {/* 生成报告 */}
      <Card title="生成新报告" style={{ marginBottom: 16 }}>
        <Form form={form} layout="inline" style={{ flexWrap: 'wrap', gap: 16 }}>
          <Form.Item
            name="evaluation_id"
            label="选择评测"
            rules={[{ required: true, message: '请选择评测' }]}
          >
            <Select
              placeholder="请选择已完成的评测"
              style={{ width: 240 }}
              options={mockEvaluations
                .filter((e) => e.score !== null)
                .map((e) => ({
                  label: `${e.agent} (${e.id}) - ${e.score}分`,
                  value: e.id,
                }))}
            />
          </Form.Item>
          <Form.Item
            name="format"
            label="报告格式"
            initialValue="markdown"
            rules={[{ required: true, message: '请选择格式' }]}
          >
            <Select
              style={{ width: 160 }}
              options={[
                { label: 'Markdown', value: 'markdown' },
                { label: 'HTML', value: 'html' },
                { label: 'JSON', value: 'json' },
              ]}
            />
          </Form.Item>
          <Form.Item>
            <Button
              type="primary"
              icon={<ThunderboltOutlined />}
              loading={generating}
              onClick={handleGenerate}
            >
              生成报告
            </Button>
          </Form.Item>
        </Form>
      </Card>

      {/* 报告列表 */}
      <Card title={`报告列表 (${reports.length})`}>
        <Spin spinning={loading}>
          {reports.length === 0 ? (
            EmptyStates.noReports()
          ) : (
            <List
              dataSource={reports}
              renderItem={(item) => (
                <List.Item
                  actions={[
                    <Button
                      key="preview"
                      type="link"
                      icon={<EyeOutlined />}
                      onClick={() => handlePreview(item)}
                    >
                      预览
                    </Button>,
                    <Button
                      key="download"
                      type="link"
                      icon={<DownloadOutlined />}
                      onClick={() => handleDownload(item)}
                    >
                      下载
                    </Button>,
                  ]}
                >
                  <List.Item.Meta
                    avatar={<FileTextOutlined style={{ fontSize: 24, color: '#1677ff' }} />}
                    title={
                      <Space>
                        <Text strong>{item.agent}</Text>
                        <Tag color={formatColors[item.format]}>{formatLabels[item.format]}</Tag>
                      </Space>
                    }
                    description={
                      <Space split="|" size="small">
                        <Text type="secondary">ID: {item.id}</Text>
                        <Text type="secondary">评测: {item.evaluationId}</Text>
                        <Text type="secondary">生成时间: {item.generatedAt}</Text>
                        <Text type="secondary">大小: {item.size}</Text>
                      </Space>
                    }
                  />
                </List.Item>
              )}
            />
          )}
        </Spin>
      </Card>

      {/* 预览弹窗 */}
      <Modal
        title={previewTitle}
        open={previewOpen}
        onCancel={() => setPreviewOpen(false)}
        footer={[
          <Button key="close" onClick={() => setPreviewOpen(false)}>关闭</Button>,
          <Button key="download" type="primary" icon={<DownloadOutlined />}>下载</Button>,
        ]}
        width={720}
        destroyOnClose
      >
        <div
          style={{
            maxHeight: 500,
            overflow: 'auto',
            background: '#fafafa',
            padding: 16,
            borderRadius: 8,
            border: '1px solid #f0f0f0',
          }}
        >
          {previewContent.includes('<') && previewContent.includes('>') ? (
            <div dangerouslySetInnerHTML={{ __html: previewContent }} />
          ) : (
            <pre style={{ whiteSpace: 'pre-wrap', margin: 0, fontSize: 13 }}>
              {previewContent}
            </pre>
          )}
        </div>
      </Modal>
    </div>
  );
};

export default ReportCenter;
