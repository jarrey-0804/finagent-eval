import React from 'react';
import { Tag } from 'antd';

const statusConfig = {
  pending: { color: 'default', label: '等待中', icon: 'clock-circle' },
  running: { color: 'processing', label: '运行中', icon: 'loading' },
  completed: { color: 'success', label: '已完成', icon: 'check-circle' },
  failed: { color: 'error', label: '失败', icon: 'close-circle' },
  cancelled: { color: 'warning', label: '已取消', icon: 'stop' },
  // 三阶段流水线状态
  static_eval: { color: 'blue', label: '静态评估', icon: 'file-text' },
  dynamic_eval: { color: 'orange', label: '动态评估', icon: 'thunderbolt' },
  trust_eval: { color: 'purple', label: '可信度评估', icon: 'safety-certificate' },
};

const StatusTag = ({ status }) => {
  const config = statusConfig[status] || statusConfig['pending'];

  return (
    <Tag color={config.color}>
      {config.label}
    </Tag>
  );
};

export default StatusTag;
