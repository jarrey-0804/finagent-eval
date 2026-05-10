import React, { useState, useEffect, createContext, useContext } from 'react';
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu, message, ConfigProvider, Result, Button, Switch } from 'antd';
import {
  DashboardOutlined,
  FileSearchOutlined,
  RobotOutlined,
  FileTextOutlined,
  SettingOutlined,
  BarChartOutlined,
  MoonOutlined,
  SunOutlined,
  FundOutlined,
  SafetyCertificateOutlined,
  BulbOutlined,
} from '@ant-design/icons';
import zhCN from 'antd/locale/zh_CN';
import Dashboard from './pages/Dashboard';
import EvaluationList from './pages/EvaluationList';
import EvaluationDetail from './pages/EvaluationDetail';
import AgentCompare from './pages/AgentCompare';
import AgentManagement from './pages/AgentManagement';
import ReportCenter from './pages/ReportCenter';
import Settings from './pages/Settings';
import BenchmarkPage from './pages/BenchmarkPage';
import CompliancePage from './pages/CompliancePage';
import ImprovementPage from './pages/ImprovementPage';
import ErrorBoundary from './components/ErrorBoundary';

const { Sider, Content } = Layout;

const menuItems = [
  { key: '/', icon: <DashboardOutlined />, label: '仪表盘' },
  { key: '/evaluations', icon: <FileSearchOutlined />, label: '评测管理' },
  { key: '/agents', icon: <RobotOutlined />, label: 'Agent管理' },
  { key: '/compare', icon: <BarChartOutlined />, label: 'Agent对比' },
  { key: '/benchmark', icon: <FundOutlined />, label: '行业基准' },
  { key: '/compliance', icon: <SafetyCertificateOutlined />, label: '合规认证' },
  { key: '/improvement', icon: <BulbOutlined />, label: '改进建议' },
  { key: '/reports', icon: <FileTextOutlined />, label: '报告中心' },
  { key: '/settings', icon: <SettingOutlined />, label: '系统设置' },
];

// Theme context
export const ThemeContext = createContext({ theme: 'light', toggleTheme: () => {} });
export const useTheme = () => useContext(ThemeContext);

// Theme provider wrapper
const ThemeProvider = ({ children }) => {
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('theme') || 'light';
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  const toggleTheme = () => setTheme(t => t === 'light' ? 'dark' : 'light');

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
};

// 全局错误处理
const setupGlobalErrorHandler = () => {
  // 处理未捕获的 Promise rejection
  window.addEventListener('unhandledrejection', (event) => {
    console.error('Unhandled promise rejection:', event.reason);

    // 如果是 API 错误，显示错误消息
    const error = event.reason;
    if (error?.response) {
      const status = error.response.status;
      const message_text = error.response.data?.message || error.message;

      if (status === 401) {
        message.error('登录已过期，请重新登录');
      } else if (status === 403) {
        message.error('无权限执行此操作');
      } else if (status === 404) {
        message.error('请求的资源不存在');
      } else if (status === 429) {
        message.warning('请求过于频繁，请稍后再试');
      } else if (status >= 500) {
        message.error('服务器错误，请稍后再试');
      } else {
        message.error(message_text || '请求失败');
      }
    } else if (error?.message) {
      message.error(error.message);
    }
  });

  // 处理全局 JavaScript 错误
  window.addEventListener('error', (event) => {
    console.error('Global error:', event.error);
  });
};

// 404 页面组件
const NotFoundPage = () => {
  const navigate = useNavigate();
  return (
    <Result
      status="404"
      title="页面不存在"
      subTitle="您访问的页面不存在或已被删除"
      extra={
        <Button type="primary" onClick={() => navigate('/')}>
          返回首页
        </Button>
      }
    />
  );
};

// 主题切换组件
const ThemeToggle = () => {
  const { theme, toggleTheme } = useTheme();

  return (
    <div style={{
      padding: '16px',
      borderTop: '1px solid #f0f0f0',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: '8px'
    }}>
      <SunOutlined />
      <Switch
        checked={theme === 'dark'}
        onChange={toggleTheme}
        checkedChildren={<MoonOutlined />}
        unCheckedChildren={<SunOutlined />}
        size="small"
      />
      <MoonOutlined />
    </div>
  );
};

const App = () => {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  // 初始化全局错误处理
  useEffect(() => {
    setupGlobalErrorHandler();
  }, []);

  const selectedKey = location.pathname.startsWith('/evaluations/')
    ? '/evaluations'
    : location.pathname;

  return (
    <ThemeProvider>
      <ConfigProvider locale={zhCN}>
        <Layout style={{ minHeight: '100vh' }}>
          <Sider
            collapsible
            collapsed={collapsed}
            onCollapse={setCollapsed}
            theme="light"
            style={{
              borderRight: '1px solid #f0f0f0',
            }}
          >
            <div style={{
              height: 64,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              borderBottom: '1px solid #f0f0f0',
            }}>
              <h2 style={{ margin: 0, fontSize: collapsed ? 14 : 16, color: '#1677ff' }}>
                {collapsed ? 'FAE' : 'FinAgent Eval'}
              </h2>
            </div>
            <Menu
              mode="inline"
              selectedKeys={[selectedKey]}
              items={menuItems}
              onClick={({ key }) => navigate(key)}
              style={{ borderRight: 'none' }}
            />
            <ThemeToggle />
          </Sider>
          <Layout>
            <Content style={{ margin: 24, minHeight: 280 }}>
              <ErrorBoundary>
                <Routes>
                  <Route path="/" element={<Dashboard />} />
                  <Route path="/evaluations" element={<EvaluationList />} />
                  <Route path="/evaluations/:id" element={<EvaluationDetail />} />
                  <Route path="/compare" element={<AgentCompare />} />
                  <Route path="/benchmark" element={<BenchmarkPage />} />
                  <Route path="/compliance" element={<CompliancePage />} />
                  <Route path="/improvement" element={<ImprovementPage />} />
                  <Route path="/agents" element={<AgentManagement />} />
                  <Route path="/reports" element={<ReportCenter />} />
                  <Route path="/settings" element={<Settings />} />
                  <Route path="*" element={<NotFoundPage />} />
                </Routes>
              </ErrorBoundary>
            </Content>
          </Layout>
        </Layout>
      </ConfigProvider>
    </ThemeProvider>
  );
};

export default App;
