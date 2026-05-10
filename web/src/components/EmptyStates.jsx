import React from 'react';
import { Empty, Result, Button } from 'antd';
import {
  FileSearchOutlined,
  RobotOutlined,
  FileTextOutlined,
  SearchOutlined,
  PlusOutlined,
} from '@ant-design/icons';

export const EmptyStates = {
  noEvaluations: (onCreate) => (
    <div className="empty-state">
      <FileSearchOutlined className="empty-state-icon" />
      <h3 className="empty-state-title">暂无评测记录</h3>
      <p className="empty-state-description">创建您的第一个评测任务，开始评估Agent能力</p>
      {onCreate && (
        <Button type="primary" icon={<PlusOutlined />} onClick={onCreate}>
          创建评测
        </Button>
      )}
    </div>
  ),

  noAgents: (onRegister) => (
    <div className="empty-state">
      <RobotOutlined className="empty-state-icon" />
      <h3 className="empty-state-title">暂无注册的Agent</h3>
      <p className="empty-state-description">注册您的第一个金融AI Agent</p>
      {onRegister && (
        <Button type="primary" icon={<PlusOutlined />} onClick={onRegister}>
          注册Agent
        </Button>
      )}
    </div>
  ),

  noReports: () => (
    <div className="empty-state">
      <FileTextOutlined className="empty-state-icon" />
      <h3 className="empty-state-title">暂无评测报告</h3>
      <p className="empty-state-description">完成评测后可生成报告</p>
    </div>
  ),

  noSearchResults: (onClear) => (
    <div className="empty-state">
      <SearchOutlined className="empty-state-icon" />
      <h3 className="empty-state-title">未找到匹配结果</h3>
      <p className="empty-state-description">尝试其他关键词或筛选条件</p>
      {onClear && (
        <Button onClick={onClear}>清除筛选</Button>
      )}
    </div>
  ),

  evaluationFailed: (onRetry) => (
    <Result
      status="error"
      title="评测执行失败"
      subTitle="请检查Agent配置和网络连接后重试"
      extra={[
        <Button type="primary" key="retry" onClick={onRetry}>
          重试
        </Button>,
      ]}
    />
  ),
};

export default EmptyStates;
