import React from 'react';
import { Skeleton, Card, Row, Col, Table } from 'antd';

/**
 * 统计卡片骨架屏
 */
export const StatCardSkeleton = () => (
  <Card className="stat-card">
    <Skeleton active paragraph={{ rows: 1 }} />
  </Card>
);

/**
 * 统计卡片行骨架屏
 * @param {number} count - 卡片数量，默认 4
 */
export const StatCardRowSkeleton = ({ count = 4 }) => (
  <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
    {Array.from({ length: count }).map((_, index) => (
      <Col xs={24} sm={12} lg={24 / count} key={index}>
        <StatCardSkeleton />
      </Col>
    ))}
  </Row>
);

/**
 * 表格骨架屏
 * @param {number} rows - 行数，默认 5
 * @param {number} columns - 列数，默认 5
 */
export const TableSkeleton = ({ rows = 5, columns = 5 }) => (
  <Card>
    <Table
      dataSource={Array.from({ length: rows }).map((_, i) => ({ key: i }))}
      columns={Array.from({ length: columns }).map((_, i) => ({
        key: i,
        title: <Skeleton.Input active size="small" style={{ width: 80 }} />,
        render: () => <Skeleton.Input active size="small" style={{ width: 100 + Math.random() * 50 }} />,
      }))}
      pagination={false}
      showHeader={true}
    />
  </Card>
);

/**
 * 评测列表骨架屏
 */
export const EvaluationListSkeleton = () => (
  <div>
    {/* 筛选栏骨架屏 */}
    <Card style={{ marginBottom: 16 }}>
      <Row gutter={[16, 12]}>
        <Col xs={24} sm={8} md={6}>
          <Skeleton.Input active style={{ width: '100%' }} />
        </Col>
        <Col xs={12} sm={6} md={4}>
          <Skeleton.Input active style={{ width: '100%' }} />
        </Col>
        <Col xs={12} sm={6} md={4}>
          <Skeleton.Input active style={{ width: '100%' }} />
        </Col>
        <Col xs={24} sm={8} md={6}>
          <Skeleton.Input active style={{ width: '100%' }} />
        </Col>
      </Row>
    </Card>
    {/* 表格骨架屏 */}
    <TableSkeleton rows={8} columns={7} />
  </div>
);

/**
 * 评测详情骨架屏
 */
export const EvaluationDetailSkeleton = () => (
  <div>
    {/* 概览卡片骨架屏 */}
    <Card style={{ marginBottom: 16 }}>
      <Skeleton active paragraph={{ rows: 2 }} />
    </Card>
    
    {/* 三阶段进度骨架屏 */}
    <Card style={{ marginBottom: 16 }}>
      <Row gutter={16}>
        {[1, 2, 3].map((i) => (
          <Col xs={24} sm={8} key={i}>
            <Card size="small">
              <Skeleton active paragraph={{ rows: 1 }} />
            </Card>
          </Col>
        ))}
      </Row>
    </Card>
    
    {/* 雷达图和任务列表骨架屏 */}
    <Row gutter={16}>
      <Col xs={24} lg={10}>
        <Card style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'center', padding: 20 }}>
            <Skeleton.Image active style={{ width: 280, height: 280 }} />
          </div>
        </Card>
      </Col>
      <Col xs={24} lg={14}>
        <TableSkeleton rows={6} columns={4} />
      </Col>
    </Row>
  </div>
);

/**
 * Agent 列表骨架屏
 */
export const AgentListSkeleton = () => (
  <div>
    <Card style={{ marginBottom: 16 }}>
      <Row gutter={[16, 12]} justify="space-between">
        <Col xs={24} sm={12}>
          <Skeleton.Input active style={{ width: 200 }} />
        </Col>
        <Col>
          <Skeleton.Button active />
        </Col>
      </Row>
    </Card>
    <TableSkeleton rows={6} columns={6} />
  </div>
);

/**
 * 报告中心骨架屏
 */
export const ReportCenterSkeleton = () => (
  <div>
    <Card style={{ marginBottom: 16 }}>
      <Row gutter={16}>
        <Col xs={24} sm={8}>
          <Skeleton.Input active style={{ width: '100%' }} />
        </Col>
        <Col xs={24} sm={8}>
          <Skeleton.Input active style={{ width: '100%' }} />
        </Col>
        <Col xs={24} sm={8}>
          <Skeleton.Button active style={{ width: '100%' }} />
        </Col>
      </Row>
    </Card>
    <TableSkeleton rows={5} columns={5} />
  </div>
);

/**
 * 设置页面骨架屏
 */
export const SettingsSkeleton = () => (
  <div>
    {[1, 2, 3, 4].map((i) => (
      <Card key={i} style={{ marginBottom: 16 }}>
        <Skeleton active paragraph={{ rows: 3 }} />
      </Card>
    ))}
  </div>
);

/**
 * 仪表盘骨架屏
 */
export const DashboardSkeleton = () => (
  <div>
    <StatCardRowSkeleton count={4} />
    <StatCardRowSkeleton count={4} />
    <Row gutter={16}>
      <Col xs={24} lg={10}>
        <Card style={{ marginBottom: 16 }}>
          <div style={{ height: 200, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
            <Skeleton.Image active style={{ width: 200, height: 160 }} />
          </div>
        </Card>
      </Col>
      <Col xs={24} lg={14}>
        <TableSkeleton rows={8} columns={6} />
      </Col>
    </Row>
  </div>
);

export default {
  StatCardSkeleton,
  StatCardRowSkeleton,
  TableSkeleton,
  EvaluationListSkeleton,
  EvaluationDetailSkeleton,
  AgentListSkeleton,
  ReportCenterSkeleton,
  SettingsSkeleton,
  DashboardSkeleton,
};
